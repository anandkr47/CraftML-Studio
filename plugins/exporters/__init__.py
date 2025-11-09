"""Model exporter plugins"""

from .onnx_exporter import register as register_onnx_exporter

PLUGINS = {
    "onnx_exporter": register_onnx_exporter,
}

__all__ = ["PLUGINS"]

