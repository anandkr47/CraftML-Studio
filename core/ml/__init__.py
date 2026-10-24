"""
Core ML Module
Training, compression, deployment, and utilities for ML models
"""

# Training
from core.ml.training import hardware_detector, HardwareDetector

# Compression
from core.ml.compression import quantize_model, ModelQuantizer

# Deployment
from core.ml.deployment import (
    deploy_local,
    deploy_to_huggingface,
    LocalModelServer,
    HuggingFaceDeployer
)

# Utils
from core.ml.utils import (
    get_gpu_info,
    get_cpu_info,
    get_memory_info,
    get_all_metrics,
    ResourceMonitor,
    MetricsTracker,
    calculate_model_size,
    calculate_perplexity
)

__all__ = [
    # Training
    'hardware_detector',
    'HardwareDetector',
    
    # Compression
    'quantize_model',
    'ModelQuantizer',
    
    # Deployment
    'deploy_local',
    'deploy_to_huggingface',
    'LocalModelServer',
    'HuggingFaceDeployer',
    
    # Utils
    'get_gpu_info',
    'get_cpu_info',
    'get_memory_info',
    'get_all_metrics',
    'ResourceMonitor',
    'MetricsTracker',
    'calculate_model_size',
    'calculate_perplexity',
]
