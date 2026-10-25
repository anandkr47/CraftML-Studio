"""
Runs inside a Modal container (shipped as a single file; stdlib + huggingface_hub only).

Downloads the run assets from the private HF dataset repo, verifies the bundle checksum, runs the
same worker the other providers use, and forwards its event lines through ``emit`` (a Modal Queue's
``put`` in production).  Returns the worker's exit code.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

PREFIX = "@@craftml "
MAX_LOG_LINE = 2000


def _event(kind: str, **fields) -> str:
    payload = {"v": 1, "type": kind}
    payload.update({k: v for k, v in fields.items() if v is not None})
    return PREFIX + json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _fail(emit: Callable[[str], None], message: str) -> int:
    emit(_event("status", status="failed", error=message))
    return 1


def run_job(
    emit: Callable[[str], None], dataset_repo: str, dataset_filename: str, max_seconds: int,
    workdir: Optional[str] = None,
) -> int:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return _fail(emit, "huggingface_hub is missing from the Modal image")

    work = Path(workdir or tempfile.mkdtemp(prefix="craftml-"))
    work.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN")
    emit(_event("log", message="Downloading run assets…"))
    try:
        for name in ("bundle.tar.gz", "bundle.sha256", "job.json", dataset_filename):
            hf_hub_download(repo_id=dataset_repo, filename=name, repo_type="dataset", token=token, local_dir=str(work))
    except Exception as exc:  # noqa: BLE001
        return _fail(emit, f"Could not download the run assets: {type(exc).__name__}")

    expected = (work / "bundle.sha256").read_text().split()[0]
    actual = hashlib.sha256((work / "bundle.tar.gz").read_bytes()).hexdigest()
    if expected != actual:
        return _fail(emit, "Bundle checksum mismatch")
    with tarfile.open(work / "bundle.tar.gz") as tar:
        try:
            tar.extractall(work, filter="data")  # Python 3.12+: refuse links/absolute paths
        except TypeError:
            tar.extractall(work)

    env = {**os.environ, "CRAFTML_JOB_FILE": str(work / "job.json"), "CRAFTML_USE_VENV": "0", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        ["bash", str(work / "craftml_worker" / "bootstrap.sh")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=env, cwd=str(work / "craftml_worker"),
    )
    timed_out = threading.Event()

    def watchdog() -> None:
        timed_out.set()
        proc.terminate()

    timer = threading.Timer(max_seconds, watchdog)
    timer.start()
    saw_terminal = False
    try:
        for raw in proc.stdout:  # type: ignore[union-attr]
            line = raw.rstrip("\n")
            if line.startswith(PREFIX):
                emit(line)
                if '"type":"status"' in line and any(f'"status":"{s}"' in line for s in ("completed", "failed", "stopped")):
                    saw_terminal = True
            elif line.strip():
                emit(_event("log", message=line[:MAX_LOG_LINE]))
        code = proc.wait()
    finally:
        timer.cancel()
    if timed_out.is_set():
        return _fail(emit, f"Stopped after the {max_seconds // 60}-minute runtime limit")
    if code != 0 and not saw_terminal:
        return _fail(emit, f"The worker exited with code {code}")
    return code


if __name__ == "__main__":  # manual debugging: python modal_entry.py <repo> <filename> <max_seconds>
    sys.exit(run_job(print, sys.argv[1], sys.argv[2], int(sys.argv[3])))
