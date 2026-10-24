"""
WebSocket API for Real-time Updates
Provides live streaming of logs and metrics
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import contextlib
import logging

from services import jobs

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
    """
    Stream system resource metrics in real-time
    
    Args:
        websocket: WebSocket connection
    """
    await websocket.accept()
    logger.info("Client connected to system monitor stream")
    
    try:
        from services.monitoring.resource import get_system_metrics
        
        while True:
            # Get current metrics
            metrics = get_system_metrics()
            
            # Send to client
            await websocket.send_json({
                "type": "system_metrics",
                "timestamp": asyncio.get_event_loop().time(),
                "data": metrics
            })
            
            # Wait 2 seconds before next update
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        logger.info("Client disconnected from system monitor")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
