"""
Model Compression Module
Quantization for model compression
"""

from core.ml.compression.quantization import quantize_model, ModelQuantizer

__all__ = [
    'quantize_model',
    'ModelQuantizer',
]
