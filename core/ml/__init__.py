"""
Core ML Module
Training, compression, deployment, and utilities for ML models
"""

# Training
from core.ml.training import hardware_detector, HardwareDetector

# Compression
from core.ml.compression import quantize_model, ModelQuantizer

# Deployment
from core.ml.deployment import deploy_to_huggingface, HuggingFaceDeployer

# Utils
from core.ml.utils import (
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
    'deploy_to_huggingface',
    'HuggingFaceDeployer',
    
    # Utils
    'MetricsTracker',
    'calculate_model_size',
    'calculate_perplexity',
]
