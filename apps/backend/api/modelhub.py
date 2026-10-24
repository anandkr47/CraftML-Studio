"""
Model Hub API Routes
Handles model search, download, and management from HuggingFace
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from huggingface_hub import HfApi, hf_hub_download, snapshot_download, list_models
from typing import Optional, List
import logging

from core.config import settings
from models.requests import ModelSearchRequest, ModelDownloadRequest
from models.responses import ModelsSearchResponse, ModelInfo, LocalModelsResponse, LocalModelInfo

logger = logging.getLogger(__name__)

router = APIRouter()

# HuggingFace API client
hf_api = HfApi()


@router.get("/search", response_model=ModelsSearchResponse)
def search_models(query: str, limit: int = 20, filter_tags: Optional[str] = None):
    """
    Search for models on HuggingFace Hub
    
    Args:
        query: Search query
        limit: Maximum number of results
        filter_tags: Comma-separated tags to filter by
        
    Returns:
        List of matching models
    """
    try:
        # Parse filter tags
        tags = filter_tags.split(',') if filter_tags else None
        
        # Search models
        models = list(hf_api.list_models(
            search=query,
            limit=limit,
            filter=tags
        ))
        
        # Convert to response format
        model_infos = []
        for model in models[:limit]:
            model_infos.append(ModelInfo(
                model_id=model.modelId,
                name=model.modelId.split('/')[-1] if '/' in model.modelId else model.modelId,
                downloads=getattr(model, 'downloads', 0),
                likes=getattr(model, 'likes', 0),
                tags=list(model.tags) if hasattr(model, 'tags') else [],
                last_modified=str(model.lastModified) if hasattr(model, 'lastModified') else None
            ))
        
        return ModelsSearchResponse(
            models=model_infos,
            total=len(model_infos),
            query=query
        )
    except Exception as e:
        logger.error(f"Model search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


def get_hf_token() -> Optional[str]:
    """
    Get stored HuggingFace token if available
    
    Returns:
        Decrypted token or None
    """
    try:
        from pathlib import Path
        token_file = Path.home() / ".craftml" / "settings" / "hf_token.enc"
        
        if not token_file.exists():
            return None
        
        # Import encryption key and decrypt
        key_file = Path.home() / ".craftml" / "settings" / ".key"
        if not key_file.exists():
            return None
        
        from cryptography.fernet import Fernet
        key = key_file.read_bytes()
        cipher = Fernet(key)
        
        encrypted_token = token_file.read_bytes()
        token = cipher.decrypt(encrypted_token).decode()
        
        return token
    except Exception as e:
        logger.error(f"Failed to retrieve HF token: {e}")
        return None


@router.post("/download")
def download_model(request: ModelDownloadRequest):
    """
    Download a model from the Hugging Face Hub into the local models directory.

    Runs in the threadpool (this is a plain ``def``) so a long download doesn't block the
    server.  With ``filename`` only that file is fetched, which is what you want for GGUF repos.
    """
    try:
        models_dir = Path(settings.models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)

        output_path = models_dir / request.model_name.replace('/', '_')
        logger.info(f"Downloading {request.model_name} ({request.filename or 'full repo'}) to {output_path}")

        hf_token = get_hf_token()
        if request.filename:
            hf_hub_download(
                repo_id=request.model_name,
                filename=request.filename,
                revision=request.revision,
                local_dir=str(output_path),
                token=hf_token,
            )
        else:
            snapshot_download(
                repo_id=request.model_name,
                revision=request.revision,
                local_dir=str(output_path),
                ignore_patterns=["*.gguf", "*.msgpack", "*.h5", "*.onnx", "original/*"],
                token=hf_token,
            )

        size_mb = sum(f.stat().st_size for f in output_path.rglob('*') if f.is_file()) / (1024 ** 2)
        return {
            "status": "completed",
            "model_name": request.model_name,
            "local_path": str(output_path),
            "size_mb": round(size_mb, 2),
            "message": "Model downloaded successfully",
        }
    except Exception as e:
        logger.error(f"Model download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/local", response_model=LocalModelsResponse)
async def list_local_models():
    """
    List locally stored models
    
    Returns:
        List of local models
    """
    try:
        models_dir = Path(settings.models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
        
        local_models = []
        
        # Scan models directory
        for model_dir in models_dir.iterdir():
            if model_dir.is_dir():
                # Get model size
                size_bytes = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
                size_mb = size_bytes / (1024 ** 2)
                
                # Check if it's a valid model (has config.json or similar)
                model_type = None
                if (model_dir / 'config.json').exists():
                    model_type = 'transformers'
                elif (model_dir / 'pytorch_model.bin').exists():
                    model_type = 'pytorch'
                
                local_models.append(LocalModelInfo(
                    name=model_dir.name,
                    path=str(model_dir),
                    size_mb=round(size_mb, 2),
                    created_at=str(model_dir.stat().st_mtime),
                    model_type=model_type
                ))
        
        return LocalModelsResponse(
            models=local_models,
            total=len(local_models)
        )
    except Exception as e:
        logger.error(f"Failed to list local models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/local/{model_name}")
async def delete_local_model(model_name: str):
    """
    Delete a local model
    
    Args:
        model_name: Name of the model to delete
        
    Returns:
        Deletion confirmation
    """
    try:
        models_dir = Path(settings.models_dir)
        model_path = models_dir / model_name
        
        if not model_path.exists():
            raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
        
        # Delete model directory
        import shutil
        shutil.rmtree(model_path)
        
        logger.info(f"Deleted model: {model_name}")
        
        return {
            "deleted": True,
            "model_name": model_name,
            "message": "Model deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/local/{model_name}/info")
async def get_local_model_info(model_name: str):
    """
    Get detailed information about a local model
    
    Args:
        model_name: Name of the model
        
    Returns:
        Model metadata
    """
    try:
        models_dir = Path(settings.models_dir)
        model_path = models_dir / model_name
        
        if not model_path.exists():
            raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
        
        # Get model size
        size_bytes = sum(f.stat().st_size for f in model_path.rglob('*') if f.is_file())
        size_mb = size_bytes / (1024 ** 2)
        
        # Try to load config
        config = {}
        config_path = model_path / 'config.json'
        if config_path.exists():
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
        
        # List files
        files = [str(f.relative_to(model_path)) for f in model_path.rglob('*') if f.is_file()]
        
        return {
            "name": model_name,
            "path": str(model_path),
            "size_mb": round(size_mb, 2),
            "num_files": len(files),
            "files": files[:20],  # Limit to first 20 files
            "config": config,
            "created_at": str(model_path.stat().st_mtime)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
