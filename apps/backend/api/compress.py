"""
Compression API
Quantize local models (GGUF, INT8/INT4, GPTQ, AWQ) with device presets and a before/after report.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException

from core.ml.compression.gguf import GgufError, setup_llama_cpp, tooling_status
from models.requests import CompressionStartRequest
from models.responses import CompressionStatusResponse, JobResponse
from services import compression_service as svc
from services.inference import InferenceError

router = APIRouter()


@router.get("/presets")
def get_presets(model_id: Optional[str] = None):
    """Target-device presets (with size estimates for ``model_id``) and the hardware-recommended one."""
    return svc.list_presets(model_id)


@router.post("/start", response_model=JobResponse)
def start_compress(request: CompressionStartRequest):
    try:
        job_id = svc.start_compression(request.model_dump())
    except (ValueError, InferenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JobResponse(job_id=job_id, status="pending", message="Compression job started")


@router.get("/status/{job_id}", response_model=CompressionStatusResponse)
def compress_status(job_id: str):
    status = svc.get_status(job_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return CompressionStatusResponse(**status)


@router.get("/jobs")
def list_compression_jobs():
    return svc.list_jobs()


@router.get("/tooling")
def llama_cpp_tooling():
    """Whether the llama.cpp tooling needed for GGUF is available."""
    return tooling_status()


@router.post("/setup-llama-cpp")
def install_llama_cpp():
    """Download llama.cpp (shallow git clone) into the app's tools directory."""
    try:
        setup_llama_cpp()
    except GgufError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return tooling_status()
