"""
Pydantic Request Models for API Validation
"""

from pydantic import BaseModel, Field, validator, model_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


# ============================================================================
# Training Request Models
# ============================================================================

class LoRAConfig(BaseModel):
    """LoRA configuration"""
    r: int = Field(default=16, ge=1, le=256, description="LoRA rank")
    lora_alpha: int = Field(default=32, ge=1, le=512, description="LoRA alpha")
    lora_dropout: float = Field(default=0.05, ge=0.0, le=0.5, description="LoRA dropout")
    target_modules: Optional[List[str]] = Field(
        default=None,
        description="Modules to apply LoRA (None = auto-detect)"
    )


class TrainingConfig(BaseModel):
    """Training configuration"""
    num_epochs: int = Field(default=3, ge=1, le=100, description="Number of training epochs")
    batch_size: int = Field(default=4, ge=1, le=128, description="Training batch size")
    learning_rate: float = Field(default=2e-4, gt=0, le=1e-2, description="Learning rate")
    warmup_steps: int = Field(default=100, ge=0, description="Warmup steps")
    save_steps: int = Field(default=100, ge=1, description="Save checkpoint every N steps")
    logging_steps: int = Field(default=10, ge=1, description="Log every N steps")
    gradient_accumulation_steps: int = Field(default=1, ge=1, description="Gradient accumulation")
    use_4bit: bool = Field(default=True, description="Use 4-bit quantization")
    use_8bit: bool = Field(default=False, description="Use 8-bit quantization (LoRA on CUDA)")
    max_seq_length: int = Field(default=512, ge=64, le=8192, description="Maximum tokens per training example")


class TrainingStartRequest(BaseModel):
    """Request model for starting a training job"""
    model_name: Optional[str] = Field(default=None, description="Base model name from HuggingFace or local path")
    dataset_path: Optional[str] = Field(default=None, description="Path to training dataset")
    output_dir: Optional[str] = Field(default=None, description="Output directory for model")
    lora_config: Optional[LoRAConfig] = Field(default=None, description="LoRA configuration")
    training_config: Optional[TrainingConfig] = Field(default=None, description="Training configuration")
    
    # Training method selection
    training_method: Optional[Literal["qlora", "lora", "full"]] = Field(
        default="qlora",
        description="Training method: QLoRA (4-bit, fastest), LoRA (fast), or Full (best quality)"
    )
    
    @validator('dataset_path')
    def validate_dataset_path(cls, v):
        """Validate dataset path if provided"""
        if v and len(v.strip()) > 0:
            return v.strip()
        return v
    
    @model_validator(mode='after')
    def validate_training_config(self):
        """Validate training configuration consistency"""
        if not self.dataset_path:
            raise ValueError("dataset_path is required")
        
        if not self.model_name:
            raise ValueError("model_name is required")
        
        return self


# ============================================================================
# Compression Request Models
# ============================================================================

class CompressionStartRequest(BaseModel):
    """Request model for starting a compression job"""
    model_id: str = Field(..., description="Local model to compress (fine-tuned, downloaded or LoRA adapter)")
    method: Literal["gguf", "int4", "int8", "gptq", "awq"] = Field(default="gguf", description="Compression method")
    quantization: Optional[str] = Field(default=None, description="GGUF quantization type, e.g. Q4_K_M")
    benchmark: bool = Field(default=True, description="Measure perplexity/speed before and after")


# ============================================================================
# Deployment Request Models
# ============================================================================

class LocalDeploymentRequest(BaseModel):
    """Start the local OpenAI-compatible API server"""
    model_id: Optional[str] = Field(default=None, description="Model to preload (any local model id)")
    port: int = Field(default=5001, ge=1024, le=65535, description="Port for API server")
    api_key: Optional[str] = Field(default=None, description="Require this bearer token on requests")
    allow_lan: bool = Field(default=False, description="Listen on all interfaces (requires api_key)")


class HuggingFaceDeploymentRequest(BaseModel):
    """Push a local model to the Hugging Face Hub"""
    model_id: str = Field(..., description="Local model id (fine-tuned model, downloaded model or GGUF)")
    repo_name: str = Field(..., description="Repository name (username/model-name)")
    hf_token: Optional[str] = Field(default=None, description="HF token (defaults to the one saved in Settings)")
    private: bool = Field(default=False, description="Make repository private")
    description: Optional[str] = Field(default=None, description="Introductory text for the model card")

# ============================================================================
# Model Hub Request Models
# ============================================================================

class ModelSearchRequest(BaseModel):
    """Request model for searching models"""
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")
    filter_tags: Optional[List[str]] = Field(default=None, description="Filter by tags")


class ModelDownloadRequest(BaseModel):
    """Request model for downloading a model"""
    model_name: str = Field(..., description="Model name from HuggingFace")
    revision: Optional[str] = Field(default=None, description="Model revision/branch")
    filename: Optional[str] = Field(default=None, description="Download only this file (e.g. a .gguf from a GGUF repo)")
