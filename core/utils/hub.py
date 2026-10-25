"""
Load Hugging Face models from the local cache before going online.

``from_pretrained("org/model")`` asks the Hub for the latest revision even when the model
is already downloaded. For a local-first app that means a model that worked yesterday
fails (or hangs, on networks with broken IPv6) when the network is down. Loading with
``local_files_only=True`` first avoids that; the network is used only when the files
aren't cached yet.
"""

from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def cached_first(load: Callable[..., T], name_or_path: str, /, **kwargs: Any) -> T:
    """``load(name_or_path, **kwargs)``, served from the local cache when possible."""
    if Path(name_or_path).exists():  # a local directory never touches the network
        return load(name_or_path, **kwargs)
    try:
        return load(name_or_path, local_files_only=True, **kwargs)
    except (OSError, ValueError):  # not (fully) cached: transformers / hub raise these
        return load(name_or_path, **kwargs)
