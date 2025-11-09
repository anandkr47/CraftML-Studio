"""Compression plugins"""

from .custom_quantizer import register as register_custom_quantizer

PLUGINS = {
    "custom_quantizer": register_custom_quantizer,
}

__all__ = ["PLUGINS"]

