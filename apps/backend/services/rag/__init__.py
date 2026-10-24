"""Local retrieval-augmented generation: ingest documents, search chunks."""

from pathlib import Path
from typing import Any, Dict, List

from services import embeddings

from . import store
from .chunking import chunk_text
from .loaders import SUPPORTED_EXTENSIONS, UnsupportedDocument, extract_text

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "UnsupportedDocument",
    "build_context_prompt",
    "ingest",
    "search",
    "store",
]


def ingest(filename: str, data: bytes) -> Dict[str, Any]:
    """Extract, chunk, embed and store one document."""
    text = extract_text(filename, data)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError(f"No readable text found in '{filename}'")
    vectors = embeddings.embed(chunks)
    return store.add_document(Path(filename).name, Path(filename).suffix.lower().lstrip("."), len(data), chunks, vectors)


def search(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    if not query.strip():
        return []
    return store.search(embeddings.embed([query])[0], top_k)


def build_context_prompt(system_prompt: str, sources: List[Dict[str, Any]]) -> str:
    """Append numbered source excerpts to the system prompt."""
    if not sources:
        return system_prompt
    blocks = "\n\n".join(
        f"[{i}] ({s['document']}, chunk {s['chunk_index']})\n{s['text']}" for i, s in enumerate(sources, 1)
    )
    instructions = (
        "Answer using the context below when it is relevant, and cite the sources you use as [1], [2], etc. "
        "If the context does not contain the answer, say so instead of guessing.\n\nContext:\n" + blocks
    )
    return f"{system_prompt.strip()}\n\n{instructions}" if system_prompt.strip() else instructions
