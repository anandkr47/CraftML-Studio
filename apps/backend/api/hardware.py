"""
Hardware Detection API
Provides hardware information and training recommendations
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from core.ml.training import hardware_detector

router = APIRouter()


class HardwareInfo(BaseModel):
    """Hardware information response"""
    platform: str
    device_type: str
    device_name: str
    backend: str
    cuda_available: bool
    rocm_available: bool
    mps_available: bool
    gpu_count: int
    total_vram_gb: float
    recommended_strategy: str


class TrainingRecommendation(BaseModel):
    """Training configuration recommendation"""
    device: str
    device_map: Optional[str]
    strategy: str
    use_4bit: bool
    use_8bit: bool
    fp16: bool
    bf16: bool
    use_flash_attention: bool
    gradient_checkpointing: bool
    per_device_train_batch_size: int
    gradient_accumulation_steps: int


@router.get("/info", response_model=HardwareInfo)
async def get_hardware_info():
    """
    Get detected hardware information
    
    Returns:
        Hardware details and capabilities
    """
    return HardwareInfo(**hardware_detector.device_info)


@router.get("/recommend", response_model=TrainingRecommendation)
async def get_training_recommendation(strategy: Optional[str] = None):
    """
    Get recommended training configuration
    
    Args:
        strategy: Override strategy (lora, qlora, full)
        
    Returns:
        Recommended training configuration
    """
    config = hardware_detector.get_training_config(strategy=strategy)
    
    # Convert torch.dtype to string for JSON
    if "compute_dtype" in config:
        config["compute_dtype"] = str(config["compute_dtype"])
    
    return TrainingRecommendation(**config)


@router.get("/backends")
async def list_backends():
    """
    List available ML backends
    
    Returns:
        Available backends and their status
    """
    return {
        "backends": {
            "cuda": {
                "available": hardware_detector.device_info["cuda_available"],
                "description": "NVIDIA GPUs",
                "platforms": ["Windows", "Linux"]
            },
            "rocm": {
                "available": hardware_detector.device_info["rocm_available"],
                "description": "AMD GPUs",
                "platforms": ["Linux"]
            },
            "metal": {
                "available": hardware_detector.device_info["mps_available"],
                "description": "Apple Silicon (M1/M2/M3)",
                "platforms": ["macOS"]
            },
            "cpu": {
                "available": True,
                "description": "CPU-based training",
                "platforms": ["All"]
            }
        },
        "current_backend": hardware_detector.device_info["backend"]
    }


@router.get("/strategies")
async def list_strategies():
    """
    List available training strategies
    
    Returns:
        Training strategies and their requirements
    """
    vram = hardware_detector.device_info["total_vram_gb"]
    
    return {
        "strategies": {
            "lora": {
                "name": "LoRA (Low-Rank Adaptation)",
                "description": "Parameter-efficient fine-tuning",
                "vram_required_gb": 8,
                "recommended": vram >= 8 and vram < 16,
                "speed": "Fast",
                "quality": "Good"
            },
            "qlora": {
                "name": "QLoRA (Quantized LoRA)",
                "description": "4-bit quantized LoRA for low VRAM",
                "vram_required_gb": 4,
                "recommended": vram < 8 and vram > 0,
                "speed": "Medium",
                "quality": "Good"
            },
            "full": {
                "name": "Full Fine-tuning",
                "description": "Train all model parameters",
                "vram_required_gb": 16,
                "recommended": vram >= 16,
                "speed": "Slow",
                "quality": "Best"
            }
        },
        "recommended": hardware_detector.device_info["recommended_strategy"],
        "your_vram_gb": vram
    }

