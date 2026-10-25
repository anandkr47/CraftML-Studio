#!/usr/bin/env python3
"""
CraftML remote worker. Runs on the GPU host, inside the extracted bundle.

Reads a job file, trains with the same EfficientTrainer the desktop app uses, and reports
progress as versioned event lines (see events.py) on stdout and in ``events.jsonl``.
Optionally serves those events over HTTP (``--serve``) for hosts the app can't SSH into.

Environment: HF_TOKEN (Hugging Face access), CRAFTML_WORKER_STUB=1 (simulate training; tests/CI).
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import events  # noqa: E402  (shipped next to this file)

MAX_BUFFERED_EVENTS = 50_000
TELEMETRY_INTERVAL = 10.0


class EventSink:
    """Thread-safe: prints each event, appends it to events.jsonl, keeps a bounded buffer for HTTP."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._buffer = []
        self._dropped = 0
        self.done = False

    def emit(self, event_type: str, **fields) -> None:
        line = events.encode(event_type, **fields)
        with self._lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
            with open(self.path, "a", encoding="ascii") as handle:
                handle.write(line + "\n")
            self._buffer.append(line)
            if len(self._buffer) > MAX_BUFFERED_EVENTS:
                drop = len(self._buffer) - MAX_BUFFERED_EVENTS
                del self._buffer[:drop]
                self._dropped += drop

    def read(self, after: int):
        with self._lock:
            start = max(0, after - self._dropped)
            return self._buffer[start:], self._dropped + len(self._buffer)


def serve(sink: EventSink, port: int, token: str) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the event stream clean
            pass

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            return hmac.compare_digest(header.encode(), f"Bearer {token}".encode())

        def do_GET(self):
            if not self._authorized():
                self.send_response(401)
                self.end_headers()
                return
            url = urlparse(self.path)
            if url.path == "/health":
                body = {"ok": True}
            elif url.path == "/events":
                after = int(parse_qs(url.query).get("after", ["0"])[0])
                lines, nxt = sink.read(after)
                body = {"events": lines, "next": nxt, "done": sink.done}
            else:
                self.send_response(404)
                self.end_headers()
                return
            payload = json.dumps(body).encode("ascii")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def start_telemetry(sink: EventSink, stop: threading.Event) -> None:
    try:
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    except Exception:
        return

    def loop() -> None:
        while not stop.wait(TELEMETRY_INTERVAL):
            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                sink.emit(
                    "telemetry",
                    vram_gb=round(mem.used / 1024 ** 3, 3),
                    vram_total_gb=round(mem.total / 1024 ** 3, 3),
                    gpu_util=float(util.gpu),
                )
            except Exception:
                return

    threading.Thread(target=loop, daemon=True).start()


def fetch_dataset(job: dict, workdir: Path) -> str:
    repo = (job.get("hf") or {}).get("dataset_repo")
    filename = job["dataset_filename"]
    if repo:
        from huggingface_hub import hf_hub_download

        return hf_hub_download(
            repo_id=repo, filename=filename, repo_type="dataset", token=os.environ.get("HF_TOKEN"),
            local_dir=str(workdir / "data"),
        )
    return str(workdir / filename)


def upload_adapter(job: dict, final_dir: Path, sink: EventSink) -> None:
    repo = (job.get("hf") or {}).get("adapter_repo")
    if not repo:
        return
    from huggingface_hub import HfApi

    api = HfApi(token=os.environ.get("HF_TOKEN"))
    api.create_repo(repo_id=repo, private=True, exist_ok=True)
    api.upload_folder(folder_path=str(final_dir), repo_id=repo)
    sink.emit("artifact", kind="hf", repo=repo)


def run_stub(job: dict, workdir: Path, sink: EventSink, cancelled) -> dict:
    """Simulated training: exercises the whole event protocol without a GPU."""
    sink.emit("log", message="Stub worker: simulating training ✓ entraînement")
    total = 5
    for step in range(1, total + 1):
        if cancelled():
            return {"status": "stopped"}
        time.sleep(float(os.environ.get("CRAFTML_STUB_DELAY", "0.05")))
        sink.emit("progress", current_epoch=1, total_epochs=1, current_step=step, total_steps=total,
                  loss=round(2.0 / step, 4), learning_rate=2e-4, epoch=step / total, vram_gb=1.5)
    final = workdir / "output" / "final"
    final.mkdir(parents=True, exist_ok=True)
    (final / "adapter_config.json").write_text(
        json.dumps({"base_model_name_or_path": job["model_name"], "peft_type": "LORA"}), encoding="utf-8"
    )
    (final / "adapter_model.safetensors").write_bytes(b"stub")
    return {"status": "completed", "output_dir": str(final)}


def run_real(job: dict, workdir: Path, sink: EventSink, cancelled) -> dict:
    from services.training.efficient_trainer import start_efficient_training

    dataset_path = fetch_dataset(job, workdir)

    def on_progress(job_id=None, current_epoch=0, total_epochs=0, current_step=0, total_steps=0,
                    loss=0.0, metrics=None):
        extra = metrics or {}
        sink.emit("progress", current_epoch=current_epoch, total_epochs=total_epochs,
                  current_step=current_step, total_steps=total_steps, loss=loss,
                  learning_rate=extra.get("learning_rate"), epoch=extra.get("epoch"),
                  vram_gb=extra.get("vram_gb"))

    def on_log(job_id, message):
        if not message.startswith("STATUS:"):
            sink.emit("log", message=message)

    result = start_efficient_training(
        job_id=job["job_id"], model_name=job["model_name"], dataset_path=dataset_path,
        output_dir=str(workdir / "output"), training_method=job.get("training_method", "qlora"),
        lora_config=job.get("lora_config"), training_config=job.get("training_config"),
        progress_callback=on_progress, log_callback=on_log, should_cancel=cancelled, run_async=False,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", default="job.json")
    parser.add_argument("--serve", type=int, default=0, help="serve events over HTTP on this port")
    args = parser.parse_args()

    job_file = Path(args.job).resolve()
    job = json.loads(job_file.read_text(encoding="utf-8"))
    workdir = job_file.parent  # events.jsonl, CANCEL, output/ and any uploaded dataset live here

    sink = EventSink(workdir / "events.jsonl")
    cancel_file = workdir / "CANCEL"
    cancelled = cancel_file.exists
    server = serve(sink, args.serve, os.environ.get("CRAFTML_EVENT_TOKEN", "")) if args.serve else None
    stop_telemetry = threading.Event()

    status, error = "failed", None
    try:
        sink.emit("status", status="running")
        start_telemetry(sink, stop_telemetry)
        stub = os.environ.get("CRAFTML_WORKER_STUB") == "1"
        result = (run_stub if stub else run_real)(job, workdir, sink, cancelled)

        outcome = result.get("status")
        if outcome == "completed":
            final = workdir / "output" / "final"
            sink.emit("artifact", kind="path", path="output/final")
            upload_adapter(job, final, sink)
            status = "completed"
        elif outcome == "stopped":
            status = "stopped"
        else:
            error = result.get("error") or "Training failed"
    except BaseException as exc:  # noqa: BLE001 - always report
        error = f"{type(exc).__name__}: {exc}"
        sink.emit("log", level="error", message=traceback.format_exc()[-1500:])
    finally:
        stop_telemetry.set()
        sink.emit("status", status=status, error=error)
        sink.done = True
        if server:
            time.sleep(float(os.environ.get("CRAFTML_SERVE_GRACE", "20")))  # let the app collect the tail
            server.shutdown()
    return 0 if status in ("completed", "stopped") else 1


if __name__ == "__main__":
    sys.exit(main())
