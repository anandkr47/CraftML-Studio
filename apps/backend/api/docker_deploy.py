"""
Docker Deployment API Routes
Handles Docker image creation for model deployment
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from core.ml.deployment import docker_builder

router = APIRouter()


class DockerBuildRequest(BaseModel):
    """Request for Docker image build"""
    model_path: str = Field(..., description="Path to model")
    image_name: str = Field(..., description="Docker image name")
    output_dir: str = Field(..., description="Output directory for Docker files")
    device: str = Field(default="cpu", description="Device type (cpu or gpu)")
    port: int = Field(default=8000, ge=1024, le=65535, description="Port to expose")


class DockerBuildResponse(BaseModel):
    """Response from Docker build"""
    status: str
    image_name: Optional[str] = None
    build_dir: Optional[str] = None
    dockerfile: Optional[str] = None
    docker_compose: Optional[str] = None
    usage: Optional[dict] = None
    error: Optional[str] = None


@router.post("/build", response_model=DockerBuildResponse)
async def build_docker_image(request: DockerBuildRequest):
    """
    Build Docker image for model deployment
    
    Args:
        request: Docker build parameters
        
    Returns:
        Build result with usage instructions
    """
    try:
        # Check if Docker is available
        if not docker_builder.check_docker():
            raise HTTPException(
                status_code=500,
                detail="Docker is not available. Please install Docker."
            )
        
        result = docker_builder.build_image(
            model_path=request.model_path,
            image_name=request.image_name,
            output_dir=request.output_dir,
            device=request.device,
            port=request.port
        )
        
        return DockerBuildResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check")
async def check_docker():
    """
    Check if Docker is available
    
    Returns:
        Docker availability status
    """
    available = docker_builder.check_docker()
    
    return {
        "docker_available": available,
        "message": "Docker is available" if available else "Docker is not installed or not running"
    }


@router.post("/create-files")
async def create_docker_files(
    output_dir: str,
    device: str = "cpu",
    port: int = 8000
):
    """
    Create Docker deployment files without building
    
    Args:
        output_dir: Directory to create files in
        device: Device type (cpu or gpu)
        port: Port to expose
        
    Returns:
        Paths to created files
    """
    try:
        import os
        
        # Create Dockerfile
        dockerfile = docker_builder.create_dockerfile(
            model_path="/path/to/model",  # Placeholder
            output_dir=output_dir,
            device=device,
            port=port
        )
        
        # Create server script
        server = docker_builder.create_inference_server(
            output_dir=output_dir,
            port=port
        )
        
        # Create docker-compose
        compose = docker_builder.create_docker_compose(
            output_dir=output_dir,
            image_name="model-inference",
            port=port,
            device=device
        )
        
        return {
            "status": "success",
            "files": {
                "dockerfile": dockerfile,
                "server": server,
                "docker_compose": compose
            },
            "message": "Docker files created. Update Dockerfile with your model path."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

