"""
Pydantic Response Models for API
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


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
# Crawler Response Models
# ============================================================================

class CrawlerProgress(BaseModel):
    """Crawler progress information"""
    pages_crawled: int
    pages_total: int
    current_url: Optional[str] = None


class CrawlerStatusResponse(BaseModel):
    """Crawler status response"""
    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: Optional[CrawlerProgress] = None
    error: Optional[str] = None


class CrawledPage(BaseModel):
    """Single crawled page"""
    url: str
    title: str
    content: str
    timestamp: float
    depth: int
    content_hash: str


class CrawlerPreviewResponse(BaseModel):
    """Crawler data preview"""
    job_id: str
    pages: List[CrawledPage]
    total: int


# ============================================================================
# Compression Response Models
# ============================================================================

class CompressionResult(BaseModel):
    """Compression result information"""
    original_size_mb: Optional[float] = None
    compressed_size_mb: Optional[float] = None
    compression_ratio: Optional[str] = None
    method: str


class CompressionStatusResponse(BaseModel):
    """Compression status response"""
    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[CompressionResult] = None
    error: Optional[str] = None


class ModelComparisonResponse(BaseModel):
    """Model comparison response"""
    model_a: Dict[str, Any]
    model_b: Dict[str, Any]
    compression_ratio: str
    size_reduction_mb: float
    size_reduction_percent: float


# ============================================================================
# Deployment Response Models
# ============================================================================

class DeploymentEndpoints(BaseModel):
    """Deployment endpoint URLs"""
    generate: str
    health: str


class LocalDeploymentResponse(BaseModel):
    """Local deployment response"""
    deployment_id: str
    url: str
    endpoints: DeploymentEndpoints
    status: str = "running"


class HuggingFaceDeploymentResponse(BaseModel):
    """HuggingFace deployment response"""
    deployment_id: str
    repo_url: str
    status: str
    space_url: Optional[str] = None


class DeploymentSummary(BaseModel):
    """Deployment summary"""
    deployment_id: str
    type: str
    status: str
    started_at: str
    url: Optional[str] = None


class DeploymentsListResponse(BaseModel):
    """List of deployments"""
    deployments: List[DeploymentSummary]
    total: int


# ============================================================================
# Dataset Response Models
# ============================================================================

class DatasetSummary(BaseModel):
    """Dataset summary information"""
    dataset_id: str
    name: str
    format: str
    size_mb: float
    num_samples: Optional[int] = None
    created_at: str


class DatasetsListResponse(BaseModel):
    """List of datasets"""
    datasets: List[DatasetSummary]
    total: int


class DatasetUploadResponse(BaseModel):
    """Dataset upload response"""
    dataset_id: str
    filename: str
    size_mb: float
    format: str
    num_samples: Optional[int] = None
    uploaded_at: Optional[str] = None
    path: Optional[str] = None


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


# ============================================================================
# Monitoring Response Models
# ============================================================================

class GPUInfo(BaseModel):
    """GPU information"""
    id: int
    name: str
    memory_total: float
    memory_used: float
    memory_free: float
    memory_util: float
    gpu_util: float
    temperature: float


class SystemInfo(BaseModel):
    """System information"""
    platform: str
    platform_release: str
    platform_version: str
    architecture: str
    processor: str
    hostname: str


class ResourceMetricsResponse(BaseModel):
    """Resource metrics response"""
    timestamp: float
    system: SystemInfo
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    disk: Dict[str, Any]
    gpus: List[GPUInfo]

