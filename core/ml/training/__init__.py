"""
Model Training Module
Hardware detection for PEFT (LoRA / QLoRA) fine-tuning
Supports CUDA, ROCm, Metal, and CPU
"""

from core.ml.training.hardware_detector import hardware_detector, HardwareDetector

__all__ = [
    'hardware_detector',
    'HardwareDetector',
]
