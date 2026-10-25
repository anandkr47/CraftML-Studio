# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the backend sidecar (one-folder build; works on macOS, Windows and Linux).

    pyinstaller --noconfirm --clean craftml-backend.spec      # -> dist/craftml-backend/

One-folder rather than one-file: the bundle holds PyTorch, and a one-file build would unpack
gigabytes to a temp directory on every launch. scripts/build_desktop.* pack the folder into
apps/desktop/src-tauri/bin/backend.tar.gz (scripts/pack_sidecar.py).
"""
import importlib.util
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve()  # noqa: F821 - provided by PyInstaller
BACKEND = ROOT / "apps" / "backend"
sys.path[:0] = [str(BACKEND), str(ROOT)]  # so collect_submodules() below can see the app packages

datas = [
    (str(ROOT / "resources"), "resources"),
    # Read as files at runtime (remote-worker bundle, Modal entry point), not imported:
    (str(ROOT / "core" / "cloud" / "worker"), "core/cloud/worker"),
    (str(ROOT / "core" / "cloud" / "events.py"), "core/cloud"),
    (str(ROOT / "core" / "data" / "finetune_dataset.py"), "core/data"),
    (str(BACKEND / "services" / "training" / "efficient_trainer.py"), "services/training"),
]
binaries = []
hiddenimports = (
    collect_submodules("api") + collect_submodules("services") + collect_submodules("db")
    + collect_submodules("models") + collect_submodules("core")
    # chosen at runtime by name
    + collect_submodules("uvicorn") + collect_submodules("websockets") + collect_submodules("keyring.backends")
)


def optional(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


# Packages that load submodules, native libraries or data files dynamically.
for package in (
    "transformers", "peft", "accelerate", "datasets", "sentence_transformers", "tokenizers",
    "safetensors", "huggingface_hub", "sqlite_vec", "gguf", "sentencepiece", "pydantic",
    "llama_cpp", "bitsandbytes",
):
    if optional(package):
        d, b, h = collect_all(package)
        datas += d
        binaries += b
        hiddenimports += h
for package in ("docx",):  # document templates
    if optional(package):
        datas += collect_data_files(package)

a = Analysis(
    [str(BACKEND / "run_server.py")],
    pathex=[str(BACKEND), str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "notebook", "pytest"],
    noarchive=False,
    optimize=0,
    # transformers/peft inspect their own source at runtime (docstrings, signatures)
    module_collection_mode={"transformers": "pyz+py", "peft": "pyz+py"},
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="craftml-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX breaks torch's native libraries and trips antivirus heuristics
    console=True,  # the desktop shell hides the window (CREATE_NO_WINDOW) and captures output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[], name="craftml-backend")
