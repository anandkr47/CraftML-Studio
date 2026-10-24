"""
Deployment API
Local OpenAI-compatible server and Hugging Face export.
"""

from fastapi import APIRouter, HTTPException

from models.requests import HuggingFaceDeploymentRequest, LocalDeploymentRequest
from models.responses import (
    DeploymentsListResponse,
    HuggingFaceDeploymentResponse,
    LocalDeploymentResponse,
)
from services import api_server, deployment_service as svc
from services.inference import InferenceError

router = APIRouter()


@router.post("/local", response_model=LocalDeploymentResponse)
def deploy_local_api(request: LocalDeploymentRequest):
    """Start the local OpenAI-compatible API server."""
    try:
        deployment_id = svc.start_local(request.model_id, request.port, request.api_key, request.allow_lan)
    except (api_server.ServerError, InferenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    info = svc.get_status(deployment_id)
    return LocalDeploymentResponse(
        deployment_id=deployment_id,
        url=info["url"],
        base_url=info["base_url"],
        endpoints=info["endpoints"],
        auth_required=info["result"].get("auth_required", False),
    )


@router.post("/huggingface", response_model=HuggingFaceDeploymentResponse)
def deploy_huggingface_api(request: HuggingFaceDeploymentRequest):
    """Start a Hugging Face export; poll /status/{deployment_id} for completion."""
    try:
        deployment_id = svc.start_huggingface(
            request.model_id, request.repo_name, request.hf_token, request.private, request.description
        )
    except (InferenceError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return HuggingFaceDeploymentResponse(deployment_id=deployment_id, status="running")


@router.get("/list", response_model=DeploymentsListResponse)
def list_active_deployments():
    deployments = svc.list_deployments()["deployments"]
    return DeploymentsListResponse(deployments=deployments, total=len(deployments))


@router.post("/stop/{deployment_id}")
def stop_deployment_api(deployment_id: str):
    if not svc.stop_deployment(deployment_id):
        raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")
    return {"stopped": True, "deployment_id": deployment_id}


@router.get("/endpoints")
def get_active_endpoints():
    return svc.get_endpoints()


@router.get("/status/{deployment_id}")
def deployment_status(deployment_id: str):
    status = svc.get_status(deployment_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")
    return status
