"""
Dataset API Routes
Handles dataset management endpoints
"""

import sys
from pathlib import Path

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import shutil
import uuid
from typing import Optional
from datetime import datetime

from core.data.formatter import DatasetFormatter
from core.config import settings
from models.requests import DatasetConvertRequest
from models.responses import (
    DatasetsListResponse,
    DatasetSummary,
    DatasetUploadResponse
)

router = APIRouter()

# In-memory dataset registry (replace with database in production)
datasets_registry: dict = {}


@router.get("/list", response_model=DatasetsListResponse)
async def list_datasets():
    """
    List all available datasets
    
    Returns:
        List of datasets with metadata
    """
    try:
        datasets_dir = Path(settings.datasets_dir)
        datasets = []
        
        # Scan datasets directory for all supported formats
        if datasets_dir.exists():
            # Scan for JSON, JSONL, CSV, and TXT files
            for pattern in ["*.json", "*.jsonl", "*.csv", "*.txt"]:
                for dataset_file in datasets_dir.glob(pattern):
                    size_mb = dataset_file.stat().st_size / (1024 ** 2)
                    file_format = dataset_file.suffix[1:]  # Remove dot
                    
                    # Count samples based on format
                    num_samples = None
                    try:
                        if file_format in ['jsonl']:
                            with open(dataset_file, 'r', encoding='utf-8') as f:
                                num_samples = sum(1 for _ in f)
                        elif file_format == 'json':
                            import json
                            with open(dataset_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                if isinstance(data, list):
                                    num_samples = len(data)
                        elif file_format == 'csv':
                            with open(dataset_file, 'r', encoding='utf-8') as f:
                                num_samples = sum(1 for _ in f) - 1  # Subtract header
                    except:
                        num_samples = None
                    
                    datasets.append(DatasetSummary(
                        dataset_id=dataset_file.stem,
                        name=dataset_file.name,
                        format=file_format,
                        size_mb=round(size_mb, 2),
                        num_samples=num_samples,
                        created_at=datetime.fromtimestamp(
                            dataset_file.stat().st_mtime
                        ).isoformat()
                    ))
        
        return DatasetsListResponse(
            datasets=datasets,
            total=len(datasets)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=DatasetUploadResponse)
async def upload_dataset(file: UploadFile = File(...)):
    """
    Upload a dataset file
    
    Args:
        file: Dataset file (JSONL, CSV, or text)
        
    Returns:
        Upload confirmation with dataset ID
    """
    try:
        # Validate file type
        allowed_extensions = ['.json', '.jsonl', '.csv', '.txt']
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
        
        output_path = datasets_dir / f"{dataset_id}{file_ext}"
        
        with open(output_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get file size
        size_mb = output_path.stat().st_size / (1024 ** 2)
        
        # Register dataset
        datasets_registry[dataset_id] = {
            "dataset_id": dataset_id,
            "filename": file.filename,
            "path": str(output_path),
            "format": file_ext[1:],  # Remove dot
            "size_mb": size_mb,
            "uploaded_at": datetime.now().isoformat()
        }
        
        return DatasetUploadResponse(
            dataset_id=dataset_id,
            filename=file.filename,
            size_mb=round(size_mb, 2),
            format=file_ext[1:]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str):
    """
    Delete a dataset
    
    Args:
        dataset_id: Dataset identifier
        
    Returns:
        Deletion confirmation
    """
    try:
        datasets_dir = Path(settings.datasets_dir)
        
        # Find and delete dataset file
        deleted = False
        for dataset_file in datasets_dir.glob(f"{dataset_id}.*"):
            dataset_file.unlink()
            deleted = True
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
        
        # Remove from registry
        if dataset_id in datasets_registry:
            del datasets_registry[dataset_id]
        
        return {
            "deleted": True,
            "dataset_id": dataset_id,
            "message": "Dataset deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/convert")
async def convert_dataset_format(request: DatasetConvertRequest):
    """
    Convert dataset to different format
    
    Args:
        request: Conversion parameters
        
    Returns:
        Converted dataset information
    """
    try:
        # Find dataset
        datasets_dir = Path(settings.datasets_dir)
        dataset_files = list(datasets_dir.glob(f"{request.dataset_id}.*"))
        
        if not dataset_files:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {request.dataset_id} not found"
            )
        
        input_path = dataset_files[0]
        
        # Load data based on current format
        import json
        data = []
        
        with open(input_path, 'r', encoding='utf-8') as f:
            if input_path.suffix == '.jsonl':
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
            elif input_path.suffix == '.txt':
                data = [{"text": line.strip()} for line in f if line.strip()]
        
        # Format dataset
        from core.data.formatter import format_dataset
        
        output_path = format_dataset(
            data=data,
            output_path=request.output_path,
            format_type=request.output_format
        )
        
        return {
            "status": "success",
            "input_path": str(input_path),
            "output_path": output_path,
            "format": request.output_format,
            "num_samples": len(data)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{dataset_id}")
async def download_dataset(dataset_id: str):
    """
    Download a dataset file
    
    Args:
        dataset_id: Dataset identifier
        
    Returns:
        File download
    """
    try:
        datasets_dir = Path(settings.datasets_dir)
        dataset_files = list(datasets_dir.glob(f"{dataset_id}.*"))
        
        if not dataset_files:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {dataset_id} not found"
            )
        
        return FileResponse(
            path=dataset_files[0],
            filename=dataset_files[0].name,
            media_type="application/octet-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_id}/info")
async def get_dataset_info(dataset_id: str):
    """
    Get detailed information about a dataset
    
    Args:
        dataset_id: Dataset identifier
        
    Returns:
        Dataset metadata and statistics
    """
    try:
        datasets_dir = Path(settings.datasets_dir)
        dataset_files = list(datasets_dir.glob(f"{dataset_id}.*"))
        
        if not dataset_files:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {dataset_id} not found"
            )
        
        dataset_file = dataset_files[0]
        
        # Gather metadata
        size_mb = dataset_file.stat().st_size / (1024 ** 2)
        
        # Count samples and get statistics
        num_samples = 0
        total_chars = 0
        
        import json
        with open(dataset_file, 'r', encoding='utf-8') as f:
            if dataset_file.suffix == '.jsonl':
                for line in f:
                    if line.strip():
                        num_samples += 1
                        try:
                            data = json.loads(line)
                            # Count characters in all fields
                            total_chars += len(json.dumps(data))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Skipping invalid JSON line: {e}")
                            continue
        
        avg_chars = total_chars / num_samples if num_samples > 0 else 0
        
        return {
            "dataset_id": dataset_id,
            "name": dataset_file.name,
            "path": str(dataset_file),
            "format": dataset_file.suffix[1:],
            "size_mb": round(size_mb, 2),
            "num_samples": num_samples,
            "avg_chars_per_sample": round(avg_chars),
            "created_at": datetime.fromtimestamp(dataset_file.stat().st_mtime).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
