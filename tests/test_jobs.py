"""
Tests for the unified job store (services/jobs.py) and legacy migration.
Uses an isolated user-data directory so the real database is never touched.
"""

import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CRAFTML_ENV"] = "prod"
os.environ["CRAFTML_USER_DATA_DIR"] = tempfile.mkdtemp(prefix="craftml-test-")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import pytest
from sqlalchemy import text

from db.models import Base, engine, init_db
from services import jobs


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield


def test_create_and_get():
    job_id = jobs.create("finetune", {"model_name": "gpt2"})
    job = jobs.get(job_id)
    assert job["job_type"] == "finetune"
    assert job["status"] == "pending"
    assert job["params"] == {"model_name": "gpt2"}


def test_unknown_job_type_rejected():
    with pytest.raises(ValueError):
        jobs.create("crawl", {})


def test_update_sets_timestamps_and_progress():
    job_id = jobs.create("compress", {})
    jobs.update(job_id, status="running", progress={"current_step": 1})
    running = jobs.get(job_id)
    assert running["started_at"] and not running["completed_at"]
    assert running["progress"] == {"current_step": 1}

    jobs.update(job_id, status="completed", result={"ok": True})
    done = jobs.get(job_id)
    assert done["completed_at"] and done["result"] == {"ok": True}


def test_logs_are_ordered_and_paginated():
    job_id = jobs.create("finetune", {})
    for i in range(5):
        jobs.append_log(job_id, f"line {i}")
    page = jobs.get_logs(job_id, limit=2, offset=2)
    assert page["total"] == 5
    assert [l.split("] ", 1)[1] for l in page["logs"]] == ["line 2", "line 3"]


def test_counts_and_filtering():
    a = jobs.create("finetune", {})
    jobs.create("compress", {})
    jobs.update(a, status="failed", error="boom")
    assert jobs.counts()["total"] == 2
    assert jobs.counts("finetune")["failed"] == 1
    compress = jobs.list_jobs(job_type="compress")
    assert len(compress) == 1 and compress[0]["job_id"] != a


def test_delete_refuses_running_jobs():
    job_id = jobs.create("finetune", {}, status="running")
    assert jobs.delete(job_id) is False
    jobs.update(job_id, status="stopped")
    assert jobs.delete(job_id) is True
    assert jobs.get(job_id) is None


def test_run_in_thread_completes_and_fails():
    ok = jobs.create("compress", {})
    jobs.run_in_thread(ok, lambda: {"size": 1}).join(5)
    assert jobs.get(ok)["status"] == "completed"
    assert jobs.get(ok)["result"] == {"size": 1}

    def boom():
        raise RuntimeError("nope")

    bad = jobs.create("compress", {})
    jobs.run_in_thread(bad, boom).join(5)
    failed = jobs.get(bad)
    assert failed["status"] == "failed" and failed["error"] == "nope"


def test_cancel_marks_stopped():
    job_id = jobs.create("finetune", {})
    gate = threading.Event()

    def work():
        gate.wait(5)

    thread = jobs.run_in_thread(job_id, work)
    jobs.request_cancel(job_id)
    gate.set()
    thread.join(5)
    assert jobs.get(job_id)["status"] == "stopped"


def test_fail_interrupted_jobs():
    running = jobs.create("finetune", {}, status="running")
    done = jobs.create("finetune", {}, status="running")
    jobs.update(done, status="completed")
    assert jobs.fail_interrupted_jobs() == 1
    assert jobs.get(running)["status"] == "failed"
    assert jobs.get(done)["status"] == "completed"


def test_legacy_training_jobs_are_migrated():
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE training_jobs (id INTEGER PRIMARY KEY, job_id TEXT, status TEXT, "
            "params TEXT, progress TEXT, error TEXT, created_at TIMESTAMP)"
        ))
        conn.execute(text(
            "INSERT INTO training_jobs (job_id, status, params, created_at) "
            "VALUES ('train_old', 'completed', '{\"model_name\": \"gpt2\"}', CURRENT_TIMESTAMP)"
        ))
    init_db()
    job = jobs.get("train_old")
    assert job["job_type"] == "finetune" and job["params"]["model_name"] == "gpt2"
    with engine.begin() as conn:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert "training_jobs" not in tables


def test_timestamps_carry_an_explicit_utc_offset():
    # The UI parses these with `new Date()`, which treats offset-less ISO strings as local time.
    from datetime import datetime, timedelta, timezone

    job_id = jobs.create("finetune", {})
    created = datetime.fromisoformat(jobs.get(job_id)["created_at"])
    assert created.tzinfo is not None
    assert abs(datetime.now(timezone.utc) - created) < timedelta(minutes=1)


def test_log_lines_use_local_time():
    from datetime import datetime

    job_id = jobs.create("finetune", {})
    jobs.append_log(job_id, "hello")
    line = jobs.get_logs(job_id)["logs"][0]
    stamp = datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S")
    assert abs((datetime.now() - stamp).total_seconds()) < 60 and line.endswith("] hello")
