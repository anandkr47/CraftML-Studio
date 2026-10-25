"""Worker bundle contents and the worker running from an extracted bundle (incl. a legacy Windows console)."""

import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


from core.cloud import events
from core.cloud.bundle import ROOT_DIR, build_bundle, collect_files


def extract(bundle, dest: Path) -> Path:
    with tarfile.open(fileobj=io.BytesIO(bundle.data)) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:  # Python without extraction filters
            tar.extractall(dest)
    return dest / ROOT_DIR


def test_bundle_contains_the_trainer_dataset_loader_and_worker():
    names = set(collect_files())
    assert {"services/training/efficient_trainer.py", "core/data/finetune_dataset.py", "worker_main.py",
            "bootstrap.sh", "requirements.txt", "events.py"} <= names
    assert {"core/__init__.py", "services/training/__init__.py"} <= names  # importable package layout


def test_bundle_is_reproducible_and_hash_matches():
    import hashlib

    first, second = build_bundle(), build_bundle()
    assert first.sha256 == second.sha256 == hashlib.sha256(first.data).hexdigest()
    assert first.filename == f"craftml-worker-{first.sha256[:12]}.tar.gz"


def test_text_files_are_normalised_to_lf_and_modes_are_sane():
    crlf = {"worker_main.py": b"print('x')\r\nprint('y')\r\n", "bootstrap.sh": b"#!/bin/sh\r\necho hi\r\n"}
    assert all(b"\r" not in data for name, data in collect_files(crlf).items() if name in crlf)

    with tarfile.open(fileobj=io.BytesIO(build_bundle(crlf).data)) as tar:
        modes = {m.name: m.mode for m in tar.getmembers()}
        assert modes[f"{ROOT_DIR}/bootstrap.sh"] == 0o755 and modes[f"{ROOT_DIR}/events.py"] == 0o644
        assert all(m.issym() is False and m.mtime == 0 for m in tar.getmembers())  # no symlinks, fixed mtimes


def test_requirements_are_pinned():
    text = collect_files()["requirements.txt"].decode()
    lines = [l for l in text.splitlines() if l and not l.startswith("#")]
    assert lines and all("==" in l for l in lines)


def run_worker(workdir: Path, job: dict, extra_env=None):
    (workdir / "job.json").write_text(json.dumps(job), encoding="utf-8")
    env = dict(os.environ, CRAFTML_WORKER_STUB="1", CRAFTML_STUB_DELAY="0", **(extra_env or {}))
    return subprocess.run(
        [sys.executable, str(workdir / ROOT_DIR / "worker_main.py"), "--job", str(workdir / "job.json")],
        capture_output=True, env=env, timeout=60,
    )


JOB = {"job_id": "train_x", "model_name": "org/base", "dataset_filename": "data.jsonl"}


def test_worker_stub_emits_the_full_event_stream(tmp_path):
    extract(build_bundle(), tmp_path)
    # PYTHONIOENCODING=cp1252 mimics a legacy Windows console: events must still survive.
    result = run_worker(tmp_path, JOB, {"PYTHONIOENCODING": "cp1252"})
    assert result.returncode == 0, result.stderr.decode()

    decoded = [events.decode(line) for line in result.stdout.decode("ascii").splitlines()]
    kinds = [e["type"] for e in decoded if e]
    assert kinds[0] == "status" and kinds[-1] == "status" and kinds.count("progress") == 5
    assert decoded[-1]["status"] == "completed"
    assert any("entraînement" in (e.get("message") or "") for e in decoded if e)

    losses = [e["loss"] for e in decoded if e and e["type"] == "progress"]
    assert losses == sorted(losses, reverse=True)
    adapter = json.loads((tmp_path / "output/final/adapter_config.json").read_text())
    assert adapter["base_model_name_or_path"] == "org/base"
    assert len((tmp_path / "events.jsonl").read_text().splitlines()) == len(decoded)


def test_worker_honours_the_cancel_file(tmp_path):
    extract(build_bundle(), tmp_path)
    (tmp_path / "CANCEL").write_text("")
    result = run_worker(tmp_path, JOB)
    statuses = [e["status"] for e in map(events.decode, result.stdout.decode().splitlines()) if e and e["type"] == "status"]
    assert result.returncode == 0 and statuses[-1] == "stopped"
    assert not (tmp_path / "output/final").exists()


def test_worker_reports_failure_with_nonzero_exit(tmp_path):
    extract(build_bundle(), tmp_path)
    broken = dict(JOB)
    del broken["model_name"]  # stub reads it -> KeyError
    result = run_worker(tmp_path, broken)
    last = [e for e in map(events.decode, result.stdout.decode().splitlines()) if e][-1]
    assert result.returncode == 1 and last["type"] == "status" and last["status"] == "failed" and "KeyError" in last["error"]


def test_worker_pins_match_the_apps_tested_lock():
    """Local and remote training must run the same library versions (one trainer, tested once)."""
    lock_file = ROOT / "apps" / "backend" / "requirements.lock.txt"
    lock = {}
    for line in lock_file.read_text().splitlines():
        if "==" in line and not line.startswith("#"):
            name, version = line.split("==", 1)
            lock[name.lower().replace("_", "-")] = version
    worker = collect_files()["requirements.txt"].decode()
    for line in (l for l in worker.splitlines() if l and not l.startswith("#")):
        name, version = line.split("==", 1)
        assert lock.get(name.lower().replace("_", "-")) == version, f"{name} differs from the app's lock"
