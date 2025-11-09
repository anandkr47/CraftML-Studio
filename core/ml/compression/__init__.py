"""
Model Compression Module
Quantization, pruning, and distillation for model compression
"""

from core.ml.compression.quantization import quantize_model, ModelQuantizer
from core.ml.compression.pruning import prune_model, ModelPruner
from core.ml.compression.distillation import distill_model, KnowledgeDistiller

__all__ = [
    'quantize_model',
    'ModelQuantizer',
    'prune_model',
    'ModelPruner',
    'distill_model',
    'KnowledgeDistiller'
]
