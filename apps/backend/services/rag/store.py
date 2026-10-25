"""
Knowledge-base vector store on SQLite.

Chunks and their embeddings (float32 blobs) live in ``kb_chunks``.  When the
sqlite-vec extension is available, a ``vec0`` virtual table indexes them for
KNN search; otherwise search falls back to a brute-force dot product.
"""

import struct
from typing import Any, Dict, List, Sequence

from sqlalchemy import func

from db.models import KbChunk, KbDocument, SessionLocal, engine, iso_utc

EMBEDDING_DIM = 384  # BAAI/bge-small-en-v1.5


def pack(vector: Sequence[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def vec_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT vec_version()")
        return True
    except Exception:  # noqa: BLE001
        return False


def _ensure_vec_table(conn) -> None:
    conn.exec_driver_sql(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[{EMBEDDING_DIM}])"
    )


def _ensure_meta(conn) -> None:
    conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS kb_meta (key TEXT PRIMARY KEY, value TEXT)")


def _mark_index_dirty(conn) -> None:
    """Record that kb_chunks changed while the vector index couldn't be updated."""
    _ensure_meta(conn)
    conn.exec_driver_sql("INSERT OR REPLACE INTO kb_meta(key, value) VALUES ('vec_dirty', '1')")


def _sync_vec_index(conn) -> None:
    """
    Make the vec0 index match ``kb_chunks``.

    They can drift if chunks were added or deleted while the extension couldn't load (chunk ids,
    which double as index row ids, may then be reused).  Such changes set a dirty marker; a dirty
    marker or a count / max-id mismatch triggers a full rebuild, so the index is never partially
    wrong.  The common case costs two cheap aggregate queries.
    """
    _ensure_vec_table(conn)
    _ensure_meta(conn)
    dirty = conn.exec_driver_sql("SELECT value FROM kb_meta WHERE key = 'vec_dirty'").fetchone()
    chunks = conn.exec_driver_sql("SELECT count(*), coalesce(max(id), 0) FROM kb_chunks").fetchone()
    indexed = conn.exec_driver_sql("SELECT count(*), coalesce(max(rowid), 0) FROM vec_chunks").fetchone()
    if not dirty and tuple(chunks) == tuple(indexed):
        return
    conn.exec_driver_sql("DELETE FROM vec_chunks")
    conn.exec_driver_sql("INSERT INTO vec_chunks(rowid, embedding) SELECT id, embedding FROM kb_chunks")
    conn.exec_driver_sql("DELETE FROM kb_meta WHERE key = 'vec_dirty'")


def _doc_dict(doc: KbDocument) -> Dict[str, Any]:
    return {
        "id": doc.id,
        "name": doc.name,
        "ext": doc.ext,
        "size_bytes": doc.size_bytes,
        "num_chunks": doc.num_chunks,
        "created_at": iso_utc(doc.created_at),
    }


def add_document(
    name: str, ext: str, size_bytes: int, chunks: List[str], vectors: List[List[float]]
) -> Dict[str, Any]:
    use_vec = vec_available()
    with SessionLocal() as db:
        doc = KbDocument(name=name, ext=ext, size_bytes=size_bytes, num_chunks=len(chunks))
        db.add(doc)
        db.flush()
        if use_vec:
            _sync_vec_index(db.connection())  # repair drift before adding (our new rows aren't in kb_chunks yet)

        rows = [
            KbChunk(document_id=doc.id, chunk_index=i, text=text, embedding=pack(vec))
            for i, (text, vec) in enumerate(zip(chunks, vectors))
        ]
        db.add_all(rows)
        db.flush()

        if not use_vec:
            _mark_index_dirty(db.connection())
        else:
            conn = db.connection()
            for row in rows:
                # replace, never collide: a stale index row may hold a reused id
                conn.exec_driver_sql("DELETE FROM vec_chunks WHERE rowid = ?", (row.id,))
                conn.exec_driver_sql(
                    "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)", (row.id, row.embedding)
                )
        db.commit()
        return _doc_dict(doc)


def list_documents() -> List[Dict[str, Any]]:
    with SessionLocal() as db:
        return [_doc_dict(d) for d in db.query(KbDocument).order_by(KbDocument.created_at.desc()).all()]


def stats() -> Dict[str, Any]:
    with SessionLocal() as db:
        docs = db.query(func.count(KbDocument.id)).scalar()
        chunks = db.query(func.count(KbChunk.id)).scalar()
    return {"documents": docs, "chunks": chunks, "vector_index": "sqlite-vec" if vec_available() else "brute-force"}


def delete_document(doc_id: int) -> bool:
    with SessionLocal() as db:
        doc = db.get(KbDocument, doc_id)
        if not doc:
            return False
        ids = [r[0] for r in db.query(KbChunk.id).filter(KbChunk.document_id == doc_id).all()]
        if ids and vec_available():
            conn = db.connection()
            _ensure_vec_table(conn)
            conn.exec_driver_sql(
                f"DELETE FROM vec_chunks WHERE rowid IN ({','.join('?' * len(ids))})", tuple(ids)
            )
        elif ids:
            _mark_index_dirty(db.connection())  # index rows for these ids survive until the next rebuild
        db.query(KbChunk).filter(KbChunk.document_id == doc_id).delete()
        db.delete(doc)
        db.commit()
        return True


def search(query_vector: Sequence[float], top_k: int = 4) -> List[Dict[str, Any]]:
    """Most similar chunks as ``{document, chunk_index, text, score}`` (cosine, higher is better)."""
    if vec_available():
        with engine.begin() as conn:
            _sync_vec_index(conn)
            hits = conn.exec_driver_sql(
                "SELECT rowid, distance FROM vec_chunks WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                (pack(query_vector), top_k),
            ).fetchall()
        # Vectors are unit length, so cosine = 1 - L2^2 / 2.
        scored = [(rowid, 1.0 - (dist * dist) / 2.0) for rowid, dist in hits]
    else:
        import numpy as np

        with SessionLocal() as db:
            rows = db.query(KbChunk.id, KbChunk.embedding).all()
        if not rows:
            return []
        matrix = np.vstack([np.frombuffer(blob, dtype=np.float32) for _, blob in rows])
        sims = matrix @ np.asarray(query_vector, dtype=np.float32)
        best = np.argsort(-sims)[:top_k]
        scored = [(rows[i][0], float(sims[i])) for i in best]

    if not scored:
        return []

    with SessionLocal() as db:
        chunks = {c.id: c for c in db.query(KbChunk).filter(KbChunk.id.in_([i for i, _ in scored])).all()}
        names = {d.id: d.name for d in db.query(KbDocument).all()}

    return [
        {
            "document": names.get(chunks[i].document_id, "?"),
            "chunk_index": chunks[i].chunk_index,
            "text": chunks[i].text,
            "score": round(score, 4),
        }
        for i, score in scored
        if i in chunks
    ]
