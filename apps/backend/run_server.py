"""
Backend entry point, used both from source and as the packaged sidecar (PyInstaller one-folder build).

    python run_server.py [--host 127.0.0.1] [--port 17860] [--log-level info] [--console]

``--run-python-script <script.py> [args...]`` / ``--run-python-module <module> [args...]`` run a
Python script or module with this interpreter and exit (see core/utils/subproc.py).
A packaged app has no separate Python, so tools such as llama.cpp's ``convert_hf_to_gguf.py`` are
run through it (they then see the bundled torch/numpy/transformers).

Everything happens under ``if __name__ == "__main__"``: multiprocessing children (spawn start
method, and every child of a frozen app) re-run this file, and must neither start a server nor run
the app's startup, which would mark the parent's running jobs as interrupted.
"""

import multiprocessing
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """PyInstaller keeps bundled modules and data under sys._MEIPASS (the _internal folder)."""
    return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))


def setup_import_path() -> None:
    if FROZEN:
        paths = [bundle_dir()]
    else:
        here = Path(__file__).resolve().parent
        paths = [here.parents[1], here]  # repository root (core/) and apps/backend
    for path in reversed([str(p) for p in paths]):
        if path not in sys.path:
            sys.path.insert(0, path)


def run_helper(mode: str, target: str, args) -> None:
    import runpy

    sys.argv = [target, *args]
    if mode == "--run-python-script":
        sys.path.insert(0, str(Path(target).resolve().parent))
        runpy.run_path(target, run_name="__main__")
    else:
        runpy.run_module(target, run_name="__main__", alter_sys=True)


def prepare_user_dirs(settings) -> None:
    """Create the data directories; on first run copy bundled resources (never overwriting)."""
    import shutil

    for directory in (settings.user_data_dir, settings.models_dir, settings.datasets_dir, settings.logs_dir):
        directory.mkdir(parents=True, exist_ok=True)
    bundled = bundle_dir() / "resources"
    user_resources = settings.user_data_dir / "resources"
    if bundled.is_dir():
        for item in bundled.iterdir():
            target = user_resources / item.name
            if target.exists():
                continue
            user_resources.mkdir(parents=True, exist_ok=True)
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)


def allocate_console() -> bool:
    """Attach to the parent console (or open one) for a packaged Windows build run with --console."""
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    try:
        if kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
            return True
        if kernel32.AllocConsole():
            sys.stdout = open("CONOUT$", "w")
            sys.stderr = open("CONOUT$", "w")
            return True
    except OSError:
        pass
    return False


def watch_parent() -> None:
    """
    Exit when the desktop app that launched us is gone.

    The app stops the backend on a normal quit, but a crash, ``kill -9`` or a forced logout
    gives it no chance, and an orphaned backend would keep the port (and any loaded model's
    memory). ``CRAFTML_PARENT_PID`` is set by the launcher; PID reuse is ruled out by also
    comparing the process start time.
    """
    raw = os.environ.get("CRAFTML_PARENT_PID", "")
    if not raw.isdigit():
        return
    import threading
    import time

    import psutil

    try:
        parent = psutil.Process(int(raw))
        born = parent.create_time()
    except psutil.Error:
        os._exit(0)

    def alive() -> bool:
        try:
            return parent.is_running() and parent.create_time() == born
        except psutil.Error:
            return False

    def loop() -> None:
        while alive():
            time.sleep(2)
        os._exit(0)

    threading.Thread(target=loop, name="parent-watchdog", daemon=True).start()


def main() -> None:
    import argparse

    setup_import_path()
    if len(sys.argv) >= 3 and sys.argv[1] in ("--run-python-script", "--run-python-module"):
        run_helper(sys.argv[1], sys.argv[2], sys.argv[3:])
        return

    parser = argparse.ArgumentParser(description="CraftML Studio Backend Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CRAFTML_PORT", "17860")),
                        help="Port to bind to (default: 17860, or $CRAFTML_PORT)")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"],
                        help="Log level (default: info)")
    parser.add_argument("--console", action="store_true", help="Show output (for standalone testing)")
    args = parser.parse_args()

    if args.console and sys.platform == "win32" and FROZEN and not allocate_console():
        print("Warning: could not allocate a console window; output may not be visible.")

    from core.config import settings

    if FROZEN:
        prepare_user_dirs(settings)

    # Standalone (not launched by the desktop app, which sets CRAFTML_ENV=prod) or --console: be chatty.
    is_standalone = args.console or os.environ.get("CRAFTML_ENV") != "prod"
    if is_standalone:
        print("=" * 70)
        print("CraftML Studio Backend Server")
        print("=" * 70)
        print("Running as:", "packaged build" if FROZEN else "development (source)")
        print(f"User data directory: {settings.user_data_dir}")
        print(f"Starting server on http://{args.host}:{args.port}")
        print("=" * 70, flush=True)

    watch_parent()

    # Networks with broken IPv6 would otherwise stall every Hugging Face download for minutes.
    from core.utils.net import start_ipv6_probe

    start_ipv6_probe()

    import uvicorn

    from main import app  # app startup: database, interrupted-job cleanup, cloud reconcile

    # The desktop shell and UI expect 127.0.0.1:17860 (see apps/desktop/src-tauri/src/backend_process.rs)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        access_log=is_standalone,
        workers=1,
        loop="asyncio",
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()  # frozen builds: handle multiprocessing child invocations and exit
    main()
