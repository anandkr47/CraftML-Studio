"""Knowledge Base API: document ingestion, listing, deletion and search."""

from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from services import rag

router = APIRouter()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=4, ge=1, le=20)


@router.post("/documents")
def upload_documents(files: List[UploadFile] = File(...)):
    """Ingest one or more PDF / DOCX / Markdown / TXT files."""
    added, errors = [], []
    for upload in files:
        try:
            data = upload.file.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise ValueError("File is larger than 50 MB")
            added.append(rag.ingest(upload.filename or "document.txt", data))
        except (rag.UnsupportedDocument, ValueError) as exc:
            errors.append({"file": upload.filename, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001 - e.g. corrupt PDF, embedding model unavailable
            errors.append({"file": upload.filename, "error": f"Ingestion failed: {exc}"})
    if not added and errors:
        raise HTTPException(status_code=400, detail=errors[0]["error"])
    return {"documents": added, "errors": errors}


@router.get("/documents")
def list_documents():
    return {
        "documents": rag.store.list_documents(),
        "stats": rag.store.stats(),
        "supported": sorted(rag.SUPPORTED_EXTENSIONS),
    }


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    if not rag.store.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "id": doc_id}


@router.post("/search")
def search(body: SearchRequest):
    try:
        return {"results": rag.search(body.query, body.top_k)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")
