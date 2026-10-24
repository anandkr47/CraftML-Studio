"""
GGUF conversion and quantization with llama.cpp.

Conversion uses llama.cpp's ``convert_hf_to_gguf.py`` (found via LLAMA_CPP_DIR or
``<user data>/tools/llama.cpp``; ``setup_llama_cpp`` clones it).  Q8_0 and F16 come
straight out of the converter; other types are quantized with the ``llama-quantize``
binary when present, otherwise with the llama-cpp-python bindings.
"""

import ctypes
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.config import settings
from core.ml.compression.presets import GGUF_QUANTS

logger = logging.getLogger(__name__)

LLAMA_CPP_REPO = "https://github.com/ggml-org/llama.cpp.git"
CONVERT_SCRIPT = "convert_hf_to_gguf.py"
DIRECT_OUTTYPES = {"Q8_0": "q8_0", "F16": "f16"}


class GgufError(RuntimeError):
    """GGUF tooling is missing or a conversion step failed."""


def _tools_dir() -> Path:
    return Path(settings.user_data_dir) / "tools" / "llama.cpp"


def llama_cpp_dir() -> Optional[Path]:
    """Directory containing the converter script, if llama.cpp is set up."""
    candidates = [Path(p) for p in (os.environ.get("LLAMA_CPP_DIR"),) if p] + [_tools_dir()]
    return next((c for c in candidates if (c / CONVERT_SCRIPT).exists()), None)


def setup_llama_cpp() -> Path:
    """Clone llama.cpp (shallow) into the app's tools directory."""
    existing = llama_cpp_dir()
    if existing:
        return existing
    if not shutil.which("git"):
        raise GgufError("git is required to download llama.cpp. Install git, or set LLAMA_CPP_DIR to an existing checkout.")
    dest = _tools_dir()
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", LLAMA_CPP_REPO, str(dest)], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise GgufError(f"Cloning llama.cpp failed: {result.stderr.strip()[-400:]}")
    return dest


def tooling_status() -> Dict[str, Any]:
    directory = llama_cpp_dir()
    try:
        import llama_cpp  # noqa: F401

        has_bindings = True
    except ImportError:
        has_bindings = False
    return {
        "converter": str(directory) if directory else None,
        "quantize_binary": _quantize_binary(directory),
        "python_bindings": has_bindings,
        "ready": directory is not None,
    }


def _quantize_binary(directory: Optional[Path]) -> Optional[str]:
    found = shutil.which("llama-quantize")
    if found:
        return found
    if directory:
        for rel in ("build/bin/llama-quantize", "build/bin/Release/llama-quantize.exe", "llama-quantize"):
            if (directory / rel).exists():
                return str(directory / rel)
    return None


def _python() -> str:
    # In a frozen desktop build sys.executable is the app itself, not an interpreter.
    return (shutil.which("python3") or shutil.which("python") or sys.executable) if getattr(sys, "frozen", False) else sys.executable


def _run(cmd, log: Optional[Callable[[str], None]]) -> None:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tail = []
    for line in proc.stdout:  # type: ignore[union-attr]
        line = line.rstrip()
        if line:
            tail = (tail + [line])[-15:]
            if log:
                log(line)
    if proc.wait() != 0:
        raise GgufError("llama.cpp step failed:\n" + "\n".join(tail))


def _quantize(f16_path: str, output_path: str, quantization: str, directory: Optional[Path],
              log: Optional[Callable[[str], None]]) -> None:
    binary = _quantize_binary(directory)
    if binary:
        _run([binary, f16_path, output_path, quantization], log)
        return
    try:
        import llama_cpp
    except ImportError as exc:
        raise GgufError(
            f"Quantizing to {quantization} needs llama-cpp-python (pip install llama-cpp-python) "
            "or the llama-quantize binary. Q8_0 and F16 don't need either."
        ) from exc
    params = llama_cpp.llama_model_quantize_default_params()
    params.ftype = GGUF_QUANTS[quantization]["ftype"]
    if llama_cpp.llama_model_quantize(f16_path.encode(), output_path.encode(), ctypes.byref(params)) != 0:
        raise GgufError(f"llama.cpp failed to quantize to {quantization}")


def convert_to_gguf(
    model_dir: str,
    output_file: str,
    quantization: str = "Q4_K_M",
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Convert a Hugging Face model directory to a quantized GGUF file."""
    quantization = quantization.upper()
    if quantization not in GGUF_QUANTS and quantization != "F16":
        raise GgufError(f"Unknown GGUF quantization '{quantization}'")

    directory = llama_cpp_dir()
    if directory is None:
        raise GgufError(
            "llama.cpp is not set up. Use 'Set up llama.cpp' on the Compress page, "
            "or set LLAMA_CPP_DIR to a llama.cpp checkout."
        )

    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    direct = DIRECT_OUTTYPES.get(quantization)
    convert_target = out if direct else out.with_name(out.stem + ".f16.gguf")

    _run(
        [_python(), str(directory / CONVERT_SCRIPT), model_dir, "--outfile", str(convert_target),
         "--outtype", direct or "f16"],
        log,
    )
    if not direct:
        try:
            _quantize(str(convert_target), str(out), quantization, directory, log)
        finally:
            convert_target.unlink(missing_ok=True)

    return {
        "status": "success",
        "output_path": str(out),
        "compression_type": f"gguf_{quantization.lower()}",
        "size_mb": round(out.stat().st_size / 1024 ** 2, 2),
    }
