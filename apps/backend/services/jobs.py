"""
Unified job store and runner.

Every long-running operation (fine-tune, compress, deploy) is recorded in the
``job_runs`` table and logs go to ``job_run_logs``.  Work runs on a background
thread; cancellation is cooperative via an in-memory flag.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import func

from core.config import settings
from core.utils import setup_logger
from db.models import Job, JobLog, JobMetric, SessionLocal, iso_utc, local_time, utcnow

logger = setup_logger("jobs", log_file=str(settings.logs_dir / "jobs.log"))

JOB_TYPES = ("finetune", "compress", "deploy")
STATUSES = ("pending", "running", "completed", "failed", "stopped")
TERMINAL_STATUSES = ("completed", "failed", "stopped")

_cancel_flags: Dict[str, threading.Event] = {}


def _dumps(value: Any) -> Optional[str]:
    return None if value is None else json.dumps(value, default=str)


def _loads(value: Optional[str]) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


def _iso(value: Optional[datetime]) -> Optional[str]:
    return iso_utc(value)


def _to_dict(job: Job) -> Dict[str, Any]:
    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "status": job.status,
        "params": _loads(job.params) or {},
        "progress": _loads(job.progress),
        "result": _loads(job.result),
        "error": job.error,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "completed_at": _iso(job.completed_at),
    }


def create(job_type: str, params: Dict[str, Any], status: str = "pending") -> str:
    """Insert a new job record and return its id."""
    if job_type not in JOB_TYPES:
        raise ValueError(f"Unknown job type: {job_type}")

    prefix = {"finetune": "train", "compress": "compress", "deploy": "deploy"}[job_type]
    job_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
    now = utcnow()

    with SessionLocal() as session:
        session.add(
            Job(
                job_id=job_id,
                job_type=job_type,
                status=status,
                params=_dumps(params),
                created_at=now,
                updated_at=now,
                started_at=now if status == "running" else None,
            )
        )
        session.commit()

    _cancel_flags[job_id] = threading.Event()
    return job_id


def update(
    job_id: str,
    status: Optional[str] = None,
    progress: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> bool:
    """Update a job; returns False if it does not exist."""
    with SessionLocal() as session:
        job = session.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return False

        now = utcnow()
        if status:
            job.status = status
            if status == "running" and not job.started_at:
                job.started_at = now
            elif status in TERMINAL_STATUSES:
                job.completed_at = now
        if progress is not None:
            job.progress = _dumps(progress)
        if result is not None:
            job.result = _dumps(result)
        if error:
            job.error = error
        job.updated_at = now
        session.commit()
    return True


def append_log(job_id: str, message: str) -> None:
    with SessionLocal() as session:
        session.add(JobLog(job_id=job_id, message=message))
        session.commit()


def add_metric(
    job_id: str,
    step: int,
    epoch: Optional[float] = None,
    loss: Optional[float] = None,
    learning_rate: Optional[float] = None,
    vram_gb: Optional[float] = None,
) -> None:
    with SessionLocal() as session:
        session.add(
            JobMetric(
                job_id=job_id, step=step, epoch=epoch, loss=loss,
                learning_rate=learning_rate, vram_gb=vram_gb,
            )
        )
        session.commit()


def get_metrics(job_id: str, after_step: int = -1, limit: int = 5000) -> List[Dict[str, Any]]:
    """Metric points with ``step > after_step``, oldest first."""
    with SessionLocal() as session:
        rows = (
            session.query(JobMetric)
            .filter(JobMetric.job_id == job_id, JobMetric.step > after_step)
            .order_by(JobMetric.step)
            .limit(limit)
            .all()
        )
        return [
            {"step": r.step, "epoch": r.epoch, "loss": r.loss,
             "learning_rate": r.learning_rate, "vram_gb": r.vram_gb}
            for r in rows
        ]


def get(job_id: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        job = session.query(Job).filter(Job.job_id == job_id).first()
        return _to_dict(job) if job else None


def list_jobs(
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        query = session.query(Job)
        if job_type:
            query = query.filter(Job.job_type == job_type)
        if status:
            query = query.filter(Job.status == status)
        rows = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
        return [_to_dict(job) for job in rows]


def counts(job_type: Optional[str] = None) -> Dict[str, int]:
    """Job counts by status, plus ``total``."""
    with SessionLocal() as session:
        query = session.query(Job.status, func.count(Job.id))
        if job_type:
            query = query.filter(Job.job_type == job_type)
        found = dict(query.group_by(Job.status).all())

    result = {status: found.get(status, 0) for status in STATUSES}
    result["total"] = sum(found.values())
    return result


def get_logs(job_id: str, limit: int = 1000, offset: int = 0) -> Dict[str, Any]:
    """Log lines in chronological order, formatted ``[timestamp] message``."""
    with SessionLocal() as session:
        total = session.query(func.count(JobLog.id)).filter(JobLog.job_id == job_id).scalar()
        rows = (
            session.query(JobLog)
            .filter(JobLog.job_id == job_id)
            .order_by(JobLog.id)
            .offset(offset)
            .limit(limit)
            .all()
        )
        lines = [f"[{local_time(row.created_at):%Y-%m-%d %H:%M:%S}] {row.message}" for row in rows]
    return {"job_id": job_id, "logs": lines, "total": total}


def delete(job_id: str) -> bool:
    """Delete a job and its logs. Running jobs cannot be deleted."""
    with SessionLocal() as session:
        job = session.query(Job).filter(Job.job_id == job_id).first()
        if not job or job.status in ("pending", "running"):
            return False
        session.query(JobLog).filter(JobLog.job_id == job_id).delete()
        session.query(JobMetric).filter(JobMetric.job_id == job_id).delete()
        session.delete(job)
        session.commit()
    _cancel_flags.pop(job_id, None)
    return True


# ---------------------------------------------------------------------------
# Cancellation and execution
# ---------------------------------------------------------------------------

def request_cancel(job_id: str) -> None:
    _cancel_flags.setdefault(job_id, threading.Event()).set()


def should_cancel(job_id: str) -> bool:
    flag = _cancel_flags.get(job_id)
    return bool(flag and flag.is_set())


def run_in_thread(job_id: str, fn: Callable[[], Optional[Dict[str, Any]]]) -> threading.Thread:
    """
    Run ``fn`` on a background thread and record the outcome.

    ``fn`` returns an optional result dict.  An exception marks the job failed;
    otherwise the job is completed, unless it was cancelled meanwhile.
    """

    def _target() -> None:
        update(job_id, status="running")
        try:
            result = fn()
            if should_cancel(job_id):
                update(job_id, status="stopped", result=result)
            else:
                update(job_id, status="completed", result=result)
        except Exception as exc:  # noqa: BLE001 - surface any failure on the job
            logger.error(f"Job {job_id} failed: {exc}", exc_info=True)
            append_log(job_id, f"ERROR: {exc}")
            if should_cancel(job_id):
                update(job_id, status="stopped")
            else:
                update(job_id, status="failed", error=str(exc))

    thread = threading.Thread(target=_target, name=f"job-{job_id}", daemon=True)
    thread.start()
    return thread


def fail_interrupted_jobs() -> int:
    """Mark jobs left pending/running by a previous process as failed."""
    with SessionLocal() as session:
        stale = session.query(Job).filter(Job.status.in_(("pending", "running"))).all()
        now = utcnow()
        for job in stale:
            job.status = "failed"
            job.error = "Interrupted by application restart"
            job.completed_at = now
            job.updated_at = now
        session.commit()
        return len(stale)
