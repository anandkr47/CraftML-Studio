"""
Model Conversion API Routes
Handles model format conversion (GGUF, ONNX, SafeTensors)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from core.ml.deployment import model_converter

router = APIRouter()


class ConversionRequest(BaseModel):
    """Request for model conversion"""
    model_path: str = Field(..., description="Path to source model")
    output_format: str = Field(..., description="Target format (gguf, onnx, safetensors)")
    output_path: str = Field(..., description="Output path")
    
    # GGUF options
    quantization: Optional[str] = Field(default="Q4_K_M", description="GGUF quantization type")
    
    # ONNX options
    opset_version: Optional[int] = Field(default=14, description="ONNX opset version")
    optimize: Optional[bool] = Field(default=True, description="Apply ONNX optimizations")


class ConversionResponse(BaseModel):
    """Response from model conversion"""
    status: str
    output_path: Optional[str] = None
    format: Optional[str] = None
    size_mb: Optional[float] = None
    error: Optional[str] = None


@router.post("/convert", response_model=ConversionResponse)
async def convert_model(request: ConversionRequest):
    """
    Convert model to specified format
    
    Args:
        request: Conversion parameters
        
    Returns:
        Conversion result
    """
    try:
        result = model_converter.convert(
            model_path=request.model_path,
            output_format=request.output_format,
            output_path=request.output_path,
            quantization=request.quantization,
            opset_version=request.opset_version,
            optimize=request.optimize
        )
        
        return ConversionResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supported-formats")
async def get_supported_formats():
    """
    Get list of supported conversion formats
    
    Returns:
        List of supported formats
    """
    return {
        "formats": model_converter.supported_formats,
        "details": {
            "gguf": {
                "description": "GGUF format for llama.cpp/Ollama",
                "quantizations": ["Q4_K_M", "Q5_K_M", "Q8_0", "f16"],
                "use_case": "Local inference with llama.cpp"
            },
            "onnx": {
                "description": "ONNX format for cross-platform inference",
                "optimizations": True,
                "use_case": "CPU inference, web deployment"
            },
            "safetensors": {
                "description": "SafeTensors format for secure model loading",
                "use_case": "Modern Hugging Face models"
            }
        }
    }

