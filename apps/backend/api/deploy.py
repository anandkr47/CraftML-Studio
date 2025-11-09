"""
Deployment API Routes
Handles model deployment endpoints with Pydantic validation
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from services.deployment_service import (
    start_deployment,
    stop_deployment,
    get_status,
    get_endpoints,
    list_deployments
)
from models.requests import LocalDeploymentRequest, HuggingFaceDeploymentRequest
from models.responses import (
    LocalDeploymentResponse,
    HuggingFaceDeploymentResponse,
    DeploymentsListResponse
)

router = APIRouter()


@router.post("/local", response_model=LocalDeploymentResponse)
async def deploy_local_api(request: LocalDeploymentRequest, background_tasks: BackgroundTasks):
    """
    Deploy model as local API server
    
    Args:
        request: Local deployment configuration
        background_tasks: FastAPI background tasks
        
    Returns:
        Deployment ID and endpoint URLs
    """
    try:
        # Start deployment
        deployment_id = start_deployment({
            "type": "local",
            "model_path": request.model_path,
            "port": request.port,
            "device": request.device
        })
        
        # Get deployment info
        deployment_info = get_status(deployment_id)
        
        if deployment_info.get("status") == "failed":
            raise HTTPException(
                status_code=500,
                detail=deployment_info.get("error", "Deployment failed")
            )
        
        return LocalDeploymentResponse(
            deployment_id=deployment_id,
            url=deployment_info.get("url", f"http://127.0.0.1:{request.port}"),
            endpoints=deployment_info.get("endpoints", {
                "generate": f"http://127.0.0.1:{request.port}/generate",
                "health": f"http://127.0.0.1:{request.port}/health"
            }),
            status=deployment_info.get("status", "running")
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")


@router.post("/huggingface", response_model=HuggingFaceDeploymentResponse)
async def deploy_huggingface_api(
    request: HuggingFaceDeploymentRequest,
    background_tasks: BackgroundTasks
):
    """
    Deploy model to HuggingFace Hub
    
    Args:
        request: HuggingFace deployment configuration
        background_tasks: FastAPI background tasks
        
    Returns:
        Deployment ID and repository URL
    """
    try:
        # Start deployment
        deployment_id = start_deployment({
            "type": "huggingface",
            "model_path": request.model_path,
            "repo_name": request.repo_name,
            "hf_token": request.hf_token,
            "private": request.private,
            "create_space": request.create_space
        })
        
        # Get deployment info
        deployment_info = get_status(deployment_id)
        
        if deployment_info.get("status") == "failed":
            raise HTTPException(
                status_code=500,
                detail=deployment_info.get("error", "Deployment failed")
            )
        
        result = deployment_info.get("result", {})
        
        return HuggingFaceDeploymentResponse(
            deployment_id=deployment_id,
            repo_url=result.get("url", f"https://huggingface.co/{request.repo_name}"),
            status=result.get("status", "uploaded"),
            space_url=result.get("space", {}).get("space_url") if request.create_space else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")


@router.get("/list", response_model=DeploymentsListResponse)
async def list_active_deployments():
    """
    List all active deployments
    
    Returns:
        List of deployments
    """
    try:
        result = list_deployments()
        deployments = result.get("deployments", [])
        
        return DeploymentsListResponse(
            deployments=deployments,
            total=len(deployments)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop/{deployment_id}")
async def stop_deployment_api(deployment_id: str):
    """
    Stop a running deployment
    
    Args:
        deployment_id: Deployment identifier
        
    Returns:
        Stop confirmation
    """
    try:
        success = stop_deployment(deployment_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Deployment {deployment_id} not found"
            )
        
        return {
            "stopped": True,
            "deployment_id": deployment_id,
            "message": "Deployment stopped successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/endpoints")
async def get_active_endpoints():
    """
    Get all active deployment endpoints
    
    Returns:
        List of active endpoints
    """
    try:
        return get_endpoints()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{deployment_id}")
async def deployment_status(deployment_id: str):
    """
    Get deployment status
    
    Args:
        deployment_id: Deployment identifier
        
    Returns:
        Deployment status
    """
    try:
        status = get_status(deployment_id)
        
        if status.get("status") == "not_found":
            raise HTTPException(
                status_code=404,
                detail=f"Deployment {deployment_id} not found"
            )
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
