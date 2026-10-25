"""
Run Python helpers in a child process, from source or from the packaged app.

A packaged backend has no separate interpreter (``sys.executable`` is the backend itself), so
``apps/backend/run_server.py`` accepts ``--run-python-script`` / ``--run-python-module`` and runs
them with the bundled libraries. From source the current interpreter is used directly.
"""

import os
import subprocess
import sys
from typing import Dict, List

# Child processes of the (windowless) desktop app must not pop up console windows on Windows.
NO_WINDOW: Dict[str, int] = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def python_script_cmd(script: str) -> List[str]:
    """Command that runs ``script`` (a file path) with this backend's Python and libraries."""
    return [sys.executable, "--run-python-script", script] if frozen() else [sys.executable, script]


def python_module_cmd(module: str) -> List[str]:
    """Command that runs ``module`` as ``__main__`` with this backend's Python and libraries."""
    return [sys.executable, "--run-python-module", module] if frozen() else [sys.executable, "-m", module]


def child_env(app_modules: bool = False) -> Dict[str, str]:
    """
    Environment for such children: UTF-8, unbuffered output. ``app_modules`` also passes this
    process's import path, so the child can import the backend's own modules from source.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    if app_modules and not frozen():
        env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p and os.path.isdir(p))
    return env
