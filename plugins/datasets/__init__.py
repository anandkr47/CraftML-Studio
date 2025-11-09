"""Dataset loader plugins"""

from .custom_loader import register as register_custom_loader

PLUGINS = {
    "custom_loader": register_custom_loader,
}

__all__ = ["PLUGINS"]

