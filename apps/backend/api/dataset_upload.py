"""
Dataset Upload API
Allow users to import their own datasets for training
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pathlib import Path
import shutil
import uuid
from typing import Optional
from datetime import datetime

from core.config import settings
from models.responses import DatasetUploadResponse

router = APIRouter()


@router.post("/upload", response_model=DatasetUploadResponse)
async def upload_training_dataset(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Upload a dataset file for training
    
    Supports JSONL, CSV, and TXT formats
    
    Args:
        file: Dataset file
        name: Optional dataset name
        description: Optional description
        
    Returns:
        Upload confirmation with dataset ID
    """
    try:
        # Validate file type
        allowed_extensions = ['.jsonl', '.csv', '.txt', '.json']
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Allowed: {allowed_extensions}"
            )
        
        # Generate dataset ID
        dataset_id = f"dataset_{uuid.uuid4().hex[:8]}"
        
        # Save file
        datasets_dir = Path(settings.datasets_dir)
        datasets_dir.mkdir(parents=True, exist_ok=True)
        
        # Use provided name or generate one
        if name:
            filename = f"{dataset_id}_{name}{file_ext}"
        else:
            filename = f"{dataset_id}{file_ext}"
        
        output_path = datasets_dir / filename
        
        # Save uploaded file
        with open(output_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get file size
        size_mb = output_path.stat().st_size / (1024 ** 2)
        
        # Count samples (for JSONL)
        num_samples = 0
        if file_ext == '.jsonl':
            try:
                with open(output_path, 'r') as f:
                    num_samples = sum(1 for line in f if line.strip())
            except:
                num_samples = None
        
        return DatasetUploadResponse(
            dataset_id=dataset_id,
            filename=filename,
            size_mb=round(size_mb, 2),
            format=file_ext[1:],  # Remove dot
            num_samples=num_samples,
            uploaded_at=datetime.now().isoformat(),
            path=str(output_path)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/list")
async def list_uploaded_datasets():
    """
    List all uploaded datasets
    
    Returns:
        List of available datasets
    """
    try:
        datasets_dir = Path(settings.datasets_dir)
        datasets = []
        
        if datasets_dir.exists():
            for dataset_file in datasets_dir.glob("dataset_*"):
                if dataset_file.is_file():
                    size_mb = dataset_file.stat().st_size / (1024 ** 2)
                    
                    datasets.append({
                        "dataset_id": dataset_file.stem,
                        "filename": dataset_file.name,
                        "size_mb": round(size_mb, 2),
                        "format": dataset_file.suffix[1:],
                        "path": str(dataset_file),
                        "created_at": datetime.fromtimestamp(
                            dataset_file.stat().st_mtime
                        ).isoformat()
                    })
        
        return {
            "datasets": datasets,
            "total": len(datasets)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{dataset_id}")
async def delete_uploaded_dataset(dataset_id: str):
    """
    Delete an uploaded dataset
    
    Args:
        dataset_id: Dataset identifier
        
    Returns:
        Deletion confirmation
    """
    try:
        datasets_dir = Path(settings.datasets_dir)
        
        # Find dataset file
        deleted = False
        for dataset_file in datasets_dir.glob(f"{dataset_id}*"):
            if dataset_file.is_file():
                dataset_file.unlink()
                deleted = True
                break
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {dataset_id} not found"
            )
        
        return {
            "deleted": True,
            "dataset_id": dataset_id,
            "message": "Dataset deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

