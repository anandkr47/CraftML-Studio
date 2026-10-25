"""
Pydantic Response Models for API
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# ============================================================================
# Generic Job Response Models
# ============================================================================

class JobResponse(BaseModel):
    """Generic job creation response"""
    job_id: str
    status: str
    message: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Generic job status response"""
    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================================
# Generic Success/Error Models
# ============================================================================

class SuccessResponse(BaseModel):
    """Generic success response"""
    status: str = "success"
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Generic error response"""
    status: str = "error"
    message: str
    code: Optional[str] = None
    details: Optional[str] = None


# ============================================================================
# Training Response Models
# ============================================================================

class TrainingProgress(BaseModel):
    """Training progress information"""
    current_epoch: int
    total_epochs: int
    current_step: int
    total_steps: int
    loss: Optional[float] = None
    learning_rate: Optional[float] = None


class TrainingStatusResponse(BaseModel):
    """Training status response"""
    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: Optional[TrainingProgress] = None
    params: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TrainingJobSummary(BaseModel):
    """Training job summary"""
    job_id: str
    base_model: Optional[str] = None
    model_name: Optional[str] = None
    status: str
    started_at: Optional[str]
    completed_at: Optional[str] = None
    dataset_id: Optional[int] = None
    progress: Optional[str] = None
    error: Optional[str] = None
    epochs: Optional[int] = None
    current_epoch: Optional[int] = None


class TrainingJobsResponse(BaseModel):
    """List of training jobs"""
    jobs: List[TrainingJobSummary]
    total: int


class TrainingJobCountsResponse(BaseModel):
    """Training job statistics"""
    total: int
    running: int
    completed: int
    failed: int
    cancelled: int = 0
    pending: int = 0


# ============================================================================
# Compression Response Models
# ============================================================================

class CompressionStatusResponse(BaseModel):
    """Compression job status; ``result`` holds the before/after report once finished"""
    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================================
# Deployment Response Models
# ============================================================================

class LocalDeploymentResponse(BaseModel):
    """Local API server response"""
    deployment_id: str
    url: str
    base_url: str
    endpoints: Dict[str, str]
    auth_required: bool = False
    status: str = "running"


class HuggingFaceDeploymentResponse(BaseModel):
    """Hugging Face export started (poll /api/deploy/status/{id} for the result)"""
    deployment_id: str
    status: str
    repo_url: Optional[str] = None


class DeploymentSummary(BaseModel):
    """Deployment summary"""
    deployment_id: str
    type: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    url: Optional[str] = None
    base_url: Optional[str] = None
    endpoints: Dict[str, str] = {}
    model_id: Optional[str] = None
    repo_url: Optional[str] = None
    error: Optional[str] = None


class DeploymentsListResponse(BaseModel):
    """List of deployments"""
    deployments: List[DeploymentSummary]
    total: int


# ============================================================================
# Model Hub Response Models
# ============================================================================

class ModelInfo(BaseModel):
    """Model information from HuggingFace"""
    model_id: str
    name: str
    downloads: Optional[int] = None
    likes: Optional[int] = None
    tags: Optional[List[str]] = None
    last_modified: Optional[str] = None


class ModelsSearchResponse(BaseModel):
    """Model search results"""
    models: List[ModelInfo]
    total: int
    query: str


class LocalModelInfo(BaseModel):
    """Local model information"""
    name: str
    path: str
    size_mb: float
    created_at: str
    model_type: Optional[str] = None


class LocalModelsResponse(BaseModel):
    """List of local models"""
    models: List[LocalModelInfo]
    total: int


