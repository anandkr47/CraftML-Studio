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
    use_8bit: bool = Field(default=False, description="Use 8-bit quantization")


class TrainingStartRequest(BaseModel):
    """Request model for starting a training job"""
    model_name: Optional[str] = Field(default=None, description="Base model name from HuggingFace or local path")
    dataset_path: Optional[str] = Field(default=None, description="Path to training dataset")
    dataset_id: Optional[int] = Field(default=None, description="Dataset ID (will be resolved to path)")
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
        # Check that either dataset_path or dataset_id is provided
        if not self.dataset_path and not self.dataset_id:
            raise ValueError("Either dataset_path or dataset_id must be provided")
        
        if not self.model_name:
            raise ValueError("model_name is required")
        
        return self


# ============================================================================
# Compression Request Models
# ============================================================================

class CompressionStartRequest(BaseModel):
    """Request model for starting a compression job"""
    model_path: str = Field(..., description="Path to model to compress")
    output_path: str = Field(..., description="Output path for compressed model")
    method: Literal["int8", "int4", "gptq"] = Field(
        default="int4",
        description="Compression method"
    )
    options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Method-specific options"
    )


class ModelCompareRequest(BaseModel):
    """Request model for comparing models"""
    model_a_path: str = Field(..., description="Path to first model")
    model_b_path: str = Field(..., description="Path to second model")


# ============================================================================
# Deployment Request Models
# ============================================================================

class LocalDeploymentRequest(BaseModel):
    """Request model for local deployment"""
    model_path: str = Field(..., description="Path to model")
    port: int = Field(default=5001, ge=1024, le=65535, description="Port for API server")
    device: str = Field(default="auto", description="Device to use (auto, cpu, cuda)")


class HuggingFaceDeploymentRequest(BaseModel):
    """Request model for HuggingFace deployment"""
    model_path: str = Field(..., description="Path to model")
    repo_name: str = Field(..., description="Repository name (username/model-name)")
    hf_token: Optional[str] = Field(default=None, description="HuggingFace API token")
    private: bool = Field(default=False, description="Make repository private")
    create_space: bool = Field(default=False, description="Create HuggingFace Space demo")


# ============================================================================
# Dataset Request Models
# ============================================================================

class DatasetUploadRequest(BaseModel):
    """Request model for dataset upload"""
    name: str = Field(..., description="Dataset name")
    description: Optional[str] = Field(default=None, description="Dataset description")
    format_type: Literal["jsonl", "csv", "text", "parquet"] = "jsonl"


class DatasetConvertRequest(BaseModel):
    """Request model for dataset format conversion"""
    dataset_id: str
    output_format: Literal["jsonl", "csv", "text", "instruction", "conversation"]
    output_path: str


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


# ============================================================================
# Common Response Models
# ============================================================================

class JobResponse(BaseModel):
    """Generic job creation response"""
    job_id: str
    status: str = "pending"
    message: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Generic job status response"""
    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model"""
    status: str = "error"
    message: str
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseModel):
    """Generic success response"""
    status: str = "success"
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


# ============================================================================
# Monitoring Response Models
# ============================================================================

class GPUMetrics(BaseModel):
    """GPU metrics"""
    id: int
    name: str
    memory_total: float
    memory_used: float
    memory_free: float
    memory_util: float
    gpu_util: float
    temperature: float


class CPUMetrics(BaseModel):
    """CPU metrics"""
    cpu_count: int
    cpu_count_physical: int
    cpu_percent: float
    cpu_freq: Optional[Dict[str, Any]]


class MemoryMetrics(BaseModel):
    """Memory metrics"""
    total: int
    available: int
    used: int
    free: int
    percent: float


class SystemMetricsResponse(BaseModel):
    """System metrics response"""
    timestamp: float
    system: Dict[str, Any]
    cpu: CPUMetrics
    memory: MemoryMetrics
    disk: Dict[str, Any]
    gpus: List[GPUMetrics]

