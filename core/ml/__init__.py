"""
Core ML Module
Training, compression, deployment, and utilities for ML models
"""

# Training
from core.ml.training import (
    LoRATrainer,
    start_lora_training,
    hardware_detector,
    HardwareDetector,
    AccelerateTrainer,
    TrainingConfig
)

# Compression
from core.ml.compression import (
    quantize_model,
    prune_model,
    distill_model,
    ModelQuantizer,
    ModelPruner,
    KnowledgeDistiller
)

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
    'LoRATrainer',
    'start_lora_training',
    'hardware_detector',
    'HardwareDetector',
    'AccelerateTrainer',
    'TrainingConfig',
    
    # Compression
    'quantize_model',
    'prune_model',
    'distill_model',
    'ModelQuantizer',
    'ModelPruner',
    'KnowledgeDistiller',
    
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
