"""
Builds the worker bundle shipped to remote GPU hosts.

The bundle reuses the exact training code the desktop app runs locally
(``EfficientTrainer`` and the dataset loader) plus the worker entry point and event protocol.

Reproducibility: entries are sorted, timestamps/owners fixed, text files normalised to LF
(git ``autocrlf`` on Windows must not break ``bootstrap.sh``).  The SHA-256 is of the final
gzip bytes and is verified on the remote host before extraction, so integrity never
depends on gzip output being identical across platforms.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import sys
import tarfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = "craftml_worker"
TEXT_SUFFIXES = (".py", ".sh", ".txt", ".json")
EXECUTABLE = ("worker_main.py", "bootstrap.sh")

# arcname inside ROOT_DIR -> importable module whose source we ship
MODULE_SOURCES = {
    "services/training/efficient_trainer.py": "services.training.efficient_trainer",
    "core/data/finetune_dataset.py": "core.data.finetune_dataset",
}
WORKER_FILES = ("worker_main.py", "bootstrap.sh", "requirements.txt")
PACKAGE_MARKERS = ("core/__init__.py", "core/data/__init__.py", "services/__init__.py", "services/training/__init__.py")


class BundleError(RuntimeError):
    pass


@dataclass(frozen=True)
class Bundle:
    data: bytes
    sha256: str

    @property
    def filename(self) -> str:
        return f"craftml-worker-{self.sha256[:12]}.tar.gz"


def _search_roots(top: str) -> List[Path]:
    """Directories that may contain the top-level package ``top``, most specific first."""
    roots: List[Path] = []
    spec = importlib.util.find_spec(top)  # top-level lookup never imports the package
    roots += [Path(p) for p in (getattr(spec, "submodule_search_locations", None) or [])]
    repo = Path(__file__).resolve().parents[2]  # source checkout: <repo>/core/cloud/bundle.py
    roots += [repo / top, repo / "apps" / "backend" / top]
    frozen = getattr(sys, "_MEIPASS", None)  # PyInstaller bundle root
    if frozen:
        roots.append(Path(frozen) / top)
    return roots


def _module_source(module_name: str) -> bytes:
    """
    Source of ``module_name``, located without importing it (importing ``core.data`` would pull
    in heavy ML libraries just to find a file).  Works from sys.path, a source checkout, or a
    packaged build that ships the file as data.
    """
    top, *rest = module_name.split(".")
    for root in _search_roots(top):
        candidate = root.joinpath(*rest).with_suffix(".py")
        if rest and candidate.is_file():
            return candidate.read_bytes()
    raise BundleError(
        f"Can't find the source of {module_name}. In a packaged build it must be included as data."
    )


def _normalise(name: str, data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n") if name.endswith(TEXT_SUFFIXES) else data


def collect_files(overrides: Optional[Dict[str, bytes]] = None) -> Dict[str, bytes]:
    """arcname -> bytes for everything in the bundle. ``overrides`` replaces entries (tests)."""
    files: Dict[str, bytes] = {}
    for arcname, module in MODULE_SOURCES.items():
        files[arcname] = _module_source(module)
    package = resources.files("core.cloud.worker")
    for name in WORKER_FILES:
        files[name] = package.joinpath(name).read_bytes()
    files["events.py"] = resources.files("core.cloud").joinpath("events.py").read_bytes()
    for marker in PACKAGE_MARKERS:
        files[marker] = b""
    files.update(overrides or {})
    return {name: _normalise(name, data) for name, data in files.items()}


def build_bundle(overrides: Optional[Dict[str, bytes]] = None) -> Bundle:
    files = collect_files(overrides)

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for name in sorted(files):
            info = tarfile.TarInfo(f"{ROOT_DIR}/{name}")
            info.size = len(files[name])
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o755 if name.endswith(EXECUTABLE) else 0o644
            tar.addfile(info, io.BytesIO(files[name]))

    gz_buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gz_buffer, mtime=0, compresslevel=9) as gz:
        gz.write(tar_buffer.getvalue())
    data = gz_buffer.getvalue()
    return Bundle(data=data, sha256=hashlib.sha256(data).hexdigest())
