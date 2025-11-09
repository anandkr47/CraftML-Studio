"""
Playground API Routes
Handles model inference and interaction
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from services.inference_service import (
    list_available_models,
    load_model,
    unload_model,
    generate_text,
    generate_text_stream,
)

router = APIRouter()


class GenerationRequest(BaseModel):
    """Request model for text generation"""
    model_path: str = Field(..., description="Path to the model")
    prompt: str = Field(..., description="Input prompt")
    max_length: int = Field(default=150, ge=1, le=2048, description="Maximum new tokens to generate")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Nucleus sampling")
    top_k: int = Field(default=50, ge=1, le=200, description="Top-k sampling")
    repetition_penalty: float = Field(default=1.1, ge=1.0, le=2.0, description="Repetition penalty")
    stream: bool = Field(default=False, description="Stream response")


@router.get("/models")
async def get_available_models():
    """
    List all available trained models
    
    Returns:
        List of model information
    """
    try:
        models = list_available_models()
        return {
            "models": models,
            "total": len(models),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load/{model_id}")
async def load_model_endpoint(model_id: str):
    """
    Load a model into memory
    
    Args:
        model_id: Model identifier
    
    Returns:
        Success status
    """
    try:
        from pathlib import Path
        model_path = Path("models") / model_id / "final"
        
        if not model_path.exists():
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        model_data = load_model(str(model_path))
        
        return {
            "success": True,
            "model_id": model_id,
            "device": model_data["device"],
            "message": f"Model {model_id} loaded successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unload/{model_id}")
async def unload_model_endpoint(model_id: str):
    """
    Unload a model from memory
    
    Args:
        model_id: Model identifier
    
    Returns:
        Success status
    """
    try:
        success = unload_model(model_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not loaded")
        
        return {
            "success": True,
            "model_id": model_id,
            "message": f"Model {model_id} unloaded successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_endpoint(request: GenerationRequest):
    """
    Generate text using a loaded model
    
    Args:
        request: Generation parameters
    
    Returns:
        Generated text and metadata
    """
    try:
        if request.stream:
            # Return streaming response
            return StreamingResponse(
                generate_text_stream(
                    model_path=request.model_path,
                    prompt=request.prompt,
                    max_length=request.max_length,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    top_k=request.top_k,
                    repetition_penalty=request.repetition_penalty,
                ),
                media_type="text/event-stream",
            )
        else:
            # Return complete response
            result = generate_text(
                model_path=request.model_path,
                prompt=request.prompt,
                max_length=request.max_length,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                repetition_penalty=request.repetition_penalty,
            )
            
            if not result["success"]:
                raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))
            
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

