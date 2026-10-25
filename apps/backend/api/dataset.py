"""
Dataset API
Upload, inspect and manage fine-tuning datasets (JSONL, JSON, CSV, Parquet, TXT).
Datasets are plain files under the user's datasets directory; the id is the filename.
"""

import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile

from core.config import settings
from core.data import SUPPORTED_EXTENSIONS, DatasetFormatError, inspect_dataset

router = APIRouter()

MAX_UPLOAD_BYTES = 2 * 1024 ** 3


def _datasets_dir() -> Path:
    path = Path(settings.datasets_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve(dataset_id: str) -> Path:
    path = _datasets_dir() / dataset_id
    if path.parent != _datasets_dir() or not path.is_file():  # also blocks path traversal
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return path


def _summary(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    return {
        "id": path.name,
        "name": path.name.split("__", 1)[-1],
        "path": str(path),
        "extension": path.suffix.lstrip("."),
        "size_mb": round(stat.st_size / (1024 ** 2), 3),
        "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


@router.post("/upload")
def upload_dataset(file: UploadFile = File(...)):
    """Save a dataset file and return its inspection (format, columns, preview, problems)."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    safe_name = re.sub(r"[^\w.-]+", "_", Path(file.filename).stem)[:60] or "dataset"
    path = _datasets_dir() / f"{uuid.uuid4().hex[:8]}__{safe_name}{ext}"
    with open(path, "wb") as out:
        shutil.copyfileobj(file.file, out)
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        path.unlink()
        raise HTTPException(status_code=413, detail="File is larger than 2 GB")

    try:
        info = inspect_dataset(str(path))
    except DatasetFormatError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - never leave an unreadable upload behind
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not read {file.filename}: {exc}")
    return {**_summary(path), **info}


@router.get("/list")
def list_datasets():
    files = sorted(_datasets_dir().iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    datasets = [_summary(p) for p in files if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    return {"datasets": datasets, "total": len(datasets)}


@router.get("/{dataset_id}/info")
def dataset_info(dataset_id: str):
    path = _resolve(dataset_id)
    try:
        return {**_summary(path), **inspect_dataset(str(path))}
    except DatasetFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str):
    _resolve(dataset_id).unlink()
    return {"deleted": True, "id": dataset_id}
