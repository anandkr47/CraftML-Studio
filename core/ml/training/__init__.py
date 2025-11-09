"""
Model Training Module
Hardware-aware training with Transformers, Accelerate, and PEFT
Supports CUDA, ROCm, Metal, and CPU
"""

from core.ml.training.finetune_lora import LoRATrainer, start_lora_training
from core.ml.training.hardware_detector import hardware_detector, HardwareDetector
from core.ml.training.accelerate_trainer import AccelerateTrainer, TrainingConfig

__all__ = [
    'LoRATrainer',
    'start_lora_training',
    'hardware_detector',
    'HardwareDetector',
    'AccelerateTrainer',
    'TrainingConfig'
]
