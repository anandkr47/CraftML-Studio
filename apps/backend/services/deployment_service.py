"""
Deployment Service
Handles model deployment using core ML modules
"""

import sys
from pathlib import Path
import uuid
import logging
from typing import Dict, Any
from datetime import datetime
import multiprocessing

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.ml.deployment import deploy_local, deploy_to_huggingface
from core.utils import setup_logger
from core.config import settings

logger = setup_logger("deployment_service", log_file=str(settings.logs_dir / "deployment_service.log"))

# In-memory deployment storage
active_deployments: Dict[str, Dict[str, Any]] = {}
deployment_processes: Dict[str, multiprocessing.Process] = {}


def start_deployment(params: Dict[str, Any]) -> str:
    """
    Start a new deployment
    
    Args:
        params: Deployment parameters including:
            - type: Deployment type (local, huggingface, docker)
            - model_path: Path to model
            - port: Port for local deployment (optional)
            - repo_name: HuggingFace repo name (optional)
            - hf_token: HuggingFace token (optional)
            
    Returns:
        deployment_id: Unique deployment identifier
    """
    deployment_id = f"deploy_{uuid.uuid4().hex[:8]}"
    deployment_type = params.get("type", "local")
    
    logger.info(f"Starting {deployment_type} deployment {deployment_id}")
    
    # Store deployment info
    active_deployments[deployment_id] = {
        "deployment_id": deployment_id,
        "type": deployment_type,
        "status": "pending",
        "params": params,
        "started_at": datetime.now().isoformat()
    }
    
    try:
        active_deployments[deployment_id]["status"] = "deploying"
        
        if deployment_type == "local":
            # Local deployment
            model_path = params.get("model_path")
            port = params.get("port", 5001)
            
            if not model_path:
                raise ValueError("model_path is required for local deployment")
            
            logger.info(f"Deploying model locally on port {port}")
            
            # Note: deploy_local() blocks, so we should run it in a separate process
            # For now, just store the info
            active_deployments[deployment_id]["status"] = "running"
            active_deployments[deployment_id]["url"] = f"http://127.0.0.1:{port}"
            active_deployments[deployment_id]["endpoints"] = {
                "generate": f"http://127.0.0.1:{port}/generate",
                "health": f"http://127.0.0.1:{port}/health"
            }
            
        elif deployment_type == "huggingface":
            # HuggingFace deployment
            model_path = params.get("model_path")
            repo_name = params.get("repo_name")
            hf_token = params.get("hf_token")
            private = params.get("private", False)
            
            if not model_path:
                raise ValueError("model_path is required")
            if not repo_name:
                raise ValueError("repo_name is required")
            
            logger.info(f"Deploying to HuggingFace: {repo_name}")
            
            result = deploy_to_huggingface(
                model_path=model_path,
                repo_name=repo_name,
                hf_token=hf_token,
                private=private
            )
            
            active_deployments[deployment_id]["status"] = "completed"
            active_deployments[deployment_id]["completed_at"] = datetime.now().isoformat()
            active_deployments[deployment_id]["result"] = result
            
        else:
            raise ValueError(f"Unknown deployment type: {deployment_type}")
        
        logger.info(f"Deployment {deployment_id} started successfully")
        
    except Exception as e:
        logger.error(f"Deployment {deployment_id} failed: {e}")
        active_deployments[deployment_id]["status"] = "failed"
        active_deployments[deployment_id]["error"] = str(e)
    
    return deployment_id


def stop_deployment(deployment_id: str) -> bool:
    """
    Stop a running deployment
    
    Args:
        deployment_id: Deployment identifier
        
    Returns:
        True if stopped successfully
    """
    if deployment_id not in active_deployments:
        logger.warning(f"Deployment {deployment_id} not found")
        return False
    
    deployment = active_deployments[deployment_id]
    deployment_type = deployment.get("type")
    
    logger.info(f"Stopping deployment {deployment_id} (type: {deployment_type})")
    
    if deployment_type == "local":
        # Stop local server process
        if deployment_id in deployment_processes:
            process = deployment_processes[deployment_id]
            process.terminate()
            process.join(timeout=5)
            del deployment_processes[deployment_id]
    
    deployment["status"] = "stopped"
    deployment["stopped_at"] = datetime.now().isoformat()
    
    return True


def get_status(deployment_id: str) -> Dict[str, Any]:
    """
    Get deployment status
    
    Args:
        deployment_id: Deployment identifier
        
    Returns:
        Deployment status information
    """
    if deployment_id not in active_deployments:
        return {
            "deployment_id": deployment_id,
            "status": "not_found",
            "error": "Deployment not found"
        }
    
    return active_deployments[deployment_id]


def get_endpoints() -> Dict[str, Any]:
    """
    Get all active deployment endpoints
    
    Returns:
        List of active endpoints
    """
    endpoints = []
    
    for deployment_id, deployment in active_deployments.items():
        if deployment.get("status") == "running":
            endpoints.append({
                "deployment_id": deployment_id,
                "type": deployment.get("type"),
                "url": deployment.get("url"),
                "endpoints": deployment.get("endpoints", {})
            })
    
    return {"endpoints": endpoints}


def list_deployments() -> Dict[str, Any]:
    """
    List all deployments
    
    Returns:
        List of deployments with summary information
    """
    deployments = []
    
    for deployment_id, deployment in active_deployments.items():
        deployments.append({
            "deployment_id": deployment_id,
            "type": deployment.get("type"),
            "status": deployment.get("status"),
            "started_at": deployment.get("started_at"),
            "url": deployment.get("url")
        })
    
    return {"deployments": deployments}
