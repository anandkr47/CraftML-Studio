"""
Check that llama.cpp can load a GGUF file, in a child process.

llama.cpp reports unsupported model shapes with ``GGML_ASSERT``, which calls ``abort()``: loaded
in-process, one odd GGUF file would take the whole backend down. So the first time a file is
used it is loaded (and one token evaluated) in a short-lived child process; only if that works is
it loaded in the backend. Results are cached per file (path, size, mtime) and llama-cpp-python
version, so the check runs once per file.

Run as a module (``python -m services.inference.gguf_check <path> <n_ctx>``) it performs the
check itself and exits 0 on success.
"""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, Optional

CHECK_TIMEOUT_S = 900  # a large model on a slow disk takes a while to map
MODULE = "services.inference.gguf_check"

_lock = threading.Lock()


class GgufLoadError(RuntimeError):
    """llama.cpp cannot load this file."""


def _cache_file() -> Path:
    from core.config import settings

    return Path(settings.user_data_dir) / "cache" / "gguf_checks.json"


def _bindings_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("llama_cpp_python")
    except PackageNotFoundError:
        return "unknown"


def _key(path: str, n_ctx: int) -> str:
    st = os.stat(path)
    return f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}|{n_ctx}|{_bindings_version()}"


def _load_cache() -> Dict[str, Optional[str]]:
    try:
        return json.loads(_cache_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(cache: Dict[str, Optional[str]]) -> None:
    target = _cache_file()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        os.replace(tmp, target)
    except OSError:
        pass  # caching is an optimisation


def _check_cmd(path: str, n_ctx: int):
    from core.utils.subproc import python_module_cmd

    return [*python_module_cmd(MODULE), path, str(n_ctx)]


def _failure_message(proc: subprocess.CompletedProcess) -> str:
    lines = [line.strip() for line in (proc.stderr or "").splitlines() if line.strip()]
    reason = next((line for line in lines if "GGML_ASSERT" in line or "error" in line.lower()), lines[-1] if lines else "")
    if "GGML_ASSERT" in reason:
        reason = reason[reason.index("GGML_ASSERT"):]
    crashed = proc.returncode < 0 or proc.returncode in (3, 134, 0xC0000409)  # signal / abort() / Windows fast-fail
    what = "crashed while loading it" if crashed else f"failed to load it (exit code {proc.returncode})"
    return f"llama.cpp {what}; the model's architecture or shape is probably unsupported. {reason}".strip()


def ensure_loadable(path: str, n_ctx: int) -> None:
    """Raise ``GgufLoadError`` if llama.cpp can't load ``path`` (checked out of process, cached)."""
    from core.utils.subproc import NO_WINDOW, child_env

    key = _key(path, n_ctx)
    with _lock:
        cache = _load_cache()
    if key in cache:
        if cache[key]:
            raise GgufLoadError(cache[key])
        return

    try:
        proc = subprocess.run(
            _check_cmd(path, n_ctx), capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=CHECK_TIMEOUT_S, env=child_env(app_modules=True), **NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise GgufLoadError(f"llama.cpp took more than {CHECK_TIMEOUT_S // 60} minutes to load the model") from exc

    error = None if proc.returncode == 0 else _failure_message(proc)
    with _lock:
        cache = _load_cache()
        cache[key] = error
        _save_cache(cache)
    if error:
        raise GgufLoadError(error)


def _main(argv) -> int:
    path, n_ctx = argv[0], int(argv[1])
    from llama_cpp import Llama

    llm = Llama(model_path=path, n_ctx=n_ctx, n_gpu_layers=-1, verbose=False)
    tokens = llm.tokenize(b"Hello", add_bos=True) or [llm.token_bos()]
    llm.eval(tokens[:1])
    llm.close()
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
