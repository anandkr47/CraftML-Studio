"""
Model Compression Module
Quantization (INT8/INT4, GPTQ, AWQ, GGUF) and target-device presets
"""

from core.ml.compression.presets import GGUF_QUANTS, METHODS, PRESETS
from core.ml.compression.quantization import ModelQuantizer, QuantizationError, merge_lora_adapter, quantize_model

__all__ = [
    'GGUF_QUANTS',
    'METHODS',
    'PRESETS',
    'ModelQuantizer',
    'QuantizationError',
    'merge_lora_adapter',
    'quantize_model',
]
