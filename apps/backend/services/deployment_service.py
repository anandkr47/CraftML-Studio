"""
Deployment Service
Records deployments in the unified job store.

Hugging Face pushes run synchronously (the API returns the repo URL).  Local
endpoints are tracked as long-lived "running" jobs until stopped.
"""

from typing import Any, Dict

from core.ml.deployment import deploy_to_huggingface
from core.utils import setup_logger
from core.config import settings
from services import jobs

logger = setup_logger("deployment_service", log_file=str(settings.logs_dir / "deployment_service.log"))

JOB_TYPE = "deploy"


def _view(job: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a job record as a deployment record."""
    result = job["result"] or {}
    view = {
        "deployment_id": job["job_id"],
        "type": job["params"].get("type"),
        "status": job["status"],
        "started_at": job["started_at"] or job["created_at"],
        "completed_at": job["completed_at"],
        "params": job["params"],
        "error": job["error"],
        "result": result,
    }
    for key in ("url", "endpoints"):
        if key in result:
            view[key] = result[key]
    return view


def start_deployment(params: Dict[str, Any]) -> str:
    """
    Start a new deployment.

    Args:
        params: type (local | huggingface), model_path, and for local: port;
            for huggingface: repo_name, hf_token, private.

    Returns:
        deployment_id
    """
    deployment_type = params.get("type", "local")
    # Never persist the token with the job record.
    stored = {k: v for k, v in params.items() if k != "hf_token"}
    deployment_id = jobs.create(JOB_TYPE, stored, status="running")
    logger.info(f"Starting {deployment_type} deployment {deployment_id}")

    try:
        model_path = params.get("model_path")
        if not model_path:
            raise ValueError("model_path is required")

        if deployment_type == "local":
            port = params.get("port", 5001)
            base = f"http://127.0.0.1:{port}"
            jobs.update(
                deployment_id,
                result={
                    "url": base,
                    "endpoints": {"generate": f"{base}/generate", "health": f"{base}/health"},
                },
            )

        elif deployment_type == "huggingface":
            repo_name = params.get("repo_name")
            if not repo_name:
                raise ValueError("repo_name is required")

            result = deploy_to_huggingface(
                model_path=model_path,
                repo_name=repo_name,
                hf_token=params.get("hf_token"),
                private=params.get("private", False),
            )
            jobs.update(deployment_id, status="completed", result=result)

        else:
            raise ValueError(f"Unknown deployment type: {deployment_type}")

    except Exception as e:
        logger.error(f"Deployment {deployment_id} failed: {e}")
        jobs.update(deployment_id, status="failed", error=str(e))

    return deployment_id


def stop_deployment(deployment_id: str) -> bool:
    """Mark a deployment as stopped."""
    job = jobs.get(deployment_id)
    if not job or job["job_type"] != JOB_TYPE:
        return False
    if job["status"] == "running":
        jobs.update(deployment_id, status="stopped")
    return True


def get_status(deployment_id: str) -> Dict[str, Any]:
    job = jobs.get(deployment_id)
    if not job or job["job_type"] != JOB_TYPE:
        return {
            "deployment_id": deployment_id,
            "status": "not_found",
            "error": "Deployment not found",
        }
    return _view(job)


def get_endpoints() -> Dict[str, Any]:
    """Endpoints of all running local deployments."""
    endpoints = [
        {
            "deployment_id": d["deployment_id"],
            "type": d["type"],
            "url": d.get("url"),
            "endpoints": d.get("endpoints", {}),
        }
        for d in map(_view, jobs.list_jobs(job_type=JOB_TYPE, status="running", limit=1000))
    ]
    return {"endpoints": endpoints}


def list_deployments() -> Dict[str, Any]:
    return {
        "deployments": [
            {
                "deployment_id": d["deployment_id"],
                "type": d["type"],
                "status": d["status"],
                "started_at": d["started_at"],
                "url": d.get("url"),
            }
            for d in map(_view, jobs.list_jobs(job_type=JOB_TYPE, limit=1000))
        ]
    }
