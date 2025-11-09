"""
WebSocket API for Real-time Updates
Provides live streaming of logs and metrics
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Active WebSocket connections
active_connections: Dict[str, Set[WebSocket]] = {}


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, job_id: str, websocket: WebSocket):
        """Connect a client to a job's updates"""
        await websocket.accept()
        
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        
        self.active_connections[job_id].add(websocket)
        logger.info(f"WebSocket connected for job {job_id}")
    
    def disconnect(self, job_id: str, websocket: WebSocket):
        """Disconnect a client"""
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
        
        logger.info(f"WebSocket disconnected for job {job_id}")
    
    async def broadcast(self, job_id: str, message: Dict):
        """Broadcast message to all clients watching a job"""
        if job_id not in self.active_connections:
            return
        
        disconnected = set()
        
        for connection in self.active_connections[job_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.add(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(job_id, connection)


manager = ConnectionManager()


@router.websocket("/logs/{job_id}")
async def websocket_logs(websocket: WebSocket, job_id: str):
    """
    Stream real-time logs for a job
    
    Args:
        websocket: WebSocket connection
        job_id: Job identifier
    """
    await manager.connect(job_id, websocket)
    
    try:
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "job_id": job_id,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for client messages (ping/pong)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                # Echo back (keep-alive)
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": asyncio.get_event_loop().time()
                })
                
            except asyncio.TimeoutError:
                # Send keep-alive ping
                await websocket.send_json({
                    "type": "ping",
                    "timestamp": asyncio.get_event_loop().time()
                })
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from logs stream: {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(job_id, websocket)


@router.websocket("/metrics/{job_id}")
async def websocket_metrics(websocket: WebSocket, job_id: str):
    """
    Stream real-time metrics for a job
    
    Args:
        websocket: WebSocket connection
        job_id: Job identifier
    """
    await manager.connect(job_id, websocket)
    
    try:
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "job_id": job_id,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Stream metrics periodically
        while True:
            try:
                # Wait for updates or timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=5.0
                )
                
            except asyncio.TimeoutError:
                # Send periodic update
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time()
                })
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from metrics stream: {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(job_id, websocket)


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


async def send_log_update(job_id: str, log_message: str):
    """
    Send log update to all connected clients
    
    Args:
        job_id: Job identifier
        log_message: Log message to broadcast
    """
    await manager.broadcast(job_id, {
        "type": "log",
        "job_id": job_id,
        "message": log_message,
        "timestamp": asyncio.get_event_loop().time()
    })


async def send_metric_update(job_id: str, metrics: Dict):
    """
    Send metric update to all connected clients
    
    Args:
        job_id: Job identifier
        metrics: Metrics dictionary
    """
    await manager.broadcast(job_id, {
        "type": "metrics",
        "job_id": job_id,
        "data": metrics,
        "timestamp": asyncio.get_event_loop().time()
    })


async def send_status_update(job_id: str, status: str, data: Dict = None):
    """
    Send status update to all connected clients
    
    Args:
        job_id: Job identifier
        status: New status
        data: Additional status data
    """
    message = {
        "type": "status",
        "job_id": job_id,
        "status": status,
        "timestamp": asyncio.get_event_loop().time()
    }
    
    if data:
        message["data"] = data
    
    await manager.broadcast(job_id, message)

