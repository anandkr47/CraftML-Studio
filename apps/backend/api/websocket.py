"""
WebSocket API for Real-time Updates
Provides live streaming of logs and metrics
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import contextlib
import logging

from services import jobs
from services.monitoring import alerts, telemetry

logger = logging.getLogger(__name__)

router = APIRouter()

POLL_INTERVAL = 1.0


@router.websocket("/logs/{job_id}")
async def websocket_logs(websocket: WebSocket, job_id: str):
    """Stream a job's log lines as they are written."""
    await websocket.accept()
    offset = 0
    last_status = None

    try:
        await websocket.send_json({"type": "connected", "job_id": job_id})

        while True:
            job = await asyncio.to_thread(jobs.get, job_id)
            if job is None:
                await websocket.send_json({"type": "error", "message": "Job not found"})
                break

            chunk = await asyncio.to_thread(jobs.get_logs, job_id, 500, offset)
            if chunk["logs"]:
                offset += len(chunk["logs"])
                await websocket.send_json({"type": "log", "job_id": job_id, "lines": chunk["logs"]})

            if job["status"] != last_status:
                last_status = job["status"]
                await websocket.send_json({"type": "status", "job_id": job_id, "status": last_status})

            if job["status"] in jobs.TERMINAL_STATUSES and not chunk["logs"]:
                break

            await asyncio.sleep(POLL_INTERVAL)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from logs stream: {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()


@router.websocket("/metrics/{job_id}")
async def websocket_metrics(websocket: WebSocket, job_id: str):
    """Stream a job's status and progress whenever they change."""
    await websocket.accept()
    last = None

    try:
        await websocket.send_json({"type": "connected", "job_id": job_id})

        while True:
            job = await asyncio.to_thread(jobs.get, job_id)
            if job is None:
                await websocket.send_json({"type": "error", "message": "Job not found"})
                break

            snapshot = (job["status"], job["progress"], job["error"])
            if snapshot != last:
                last = snapshot
                await websocket.send_json({
                    "type": "progress",
                    "job_id": job_id,
                    "status": job["status"],
                    "progress": job["progress"],
                    "error": job["error"],
                })

            if job["status"] in jobs.TERMINAL_STATUSES:
                break

            await asyncio.sleep(POLL_INTERVAL)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from metrics stream: {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()


@router.websocket("/monitor")
async def websocket_system_monitor(websocket: WebSocket):
    """Stream telemetry (with alerts) every two seconds."""
    await websocket.accept()
    try:
        while True:
            reading = await asyncio.to_thread(telemetry.sample)
            reading["alerts"] = await asyncio.to_thread(alerts.evaluate, reading)
            await websocket.send_json({"type": "metrics", **reading})
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"System monitor stream error: {e}")
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()
