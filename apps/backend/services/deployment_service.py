"""
Deployment Service
  * local: start/stop the OpenAI-compatible API server (services/api_server.py)
  * huggingface: export a local model + generated model card to the Hub

Both are recorded as ``deploy`` jobs in the unified job store.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from core.config import settings
from core.ml.deployment import build_model_card, deploy_to_huggingface
from core.utils import setup_logger
from services import api_server, inference, jobs
from services.inference import ModelInfo

logger = setup_logger("deployment_service", log_file=str(settings.logs_dir / "deployment_service.log"))

JOB_TYPE = "deploy"
SECRET_PARAMS = ("hf_token", "api_key")


def _view(job: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a job record as a deployment record."""
    result = job["result"] or {}
    return {
        "deployment_id": job["job_id"],
        "type": job["params"].get("type"),
        "status": job["status"],
        "started_at": job["started_at"] or job["created_at"],
        "completed_at": job["completed_at"],
        "model_id": job["params"].get("model_id"),
        "params": job["params"],
        "error": job["error"],
        "result": result,
        "url": result.get("url"),
        "base_url": result.get("base_url"),
        "endpoints": result.get("endpoints", {}),
        "repo_url": result.get("repo_url") or (result.get("url") if job["params"].get("type") == "huggingface" else None),
    }


def _model_card_context(info: ModelInfo) -> Dict[str, Any]:
    """Base model and training details for a model card, from the fine-tune job that produced it."""
    base_model: Optional[str] = None
    details: Dict[str, Any] = {}

    job = jobs.get(info.id) if info.id.startswith("train_") else None
    if job and job["job_type"] == "finetune":
        params = job["params"]
        cfg = params.get("training_config") or {}
        lora = params.get("lora_config") or {}
        base_model = params.get("model_name")
        details = {
            "Method": (params.get("training_method") or "qlora").upper(),
            "Dataset": Path(params.get("dataset_path") or "").name or None,
            "Epochs": cfg.get("num_epochs"),
            "Learning rate": cfg.get("learning_rate"),
            "Batch size": cfg.get("batch_size"),
            "LoRA rank / alpha": f"{lora['r']} / {lora['lora_alpha']}" if lora.get("r") else None,
            "Final loss": round(job["progress"]["loss"], 4) if (job["progress"] or {}).get("loss") else None,
        }
        details = {k: v for k, v in details.items() if v not in (None, "")}

    if not base_model and info.kind == "lora":
        try:
            base_model = json.loads((Path(info.path) / "adapter_config.json").read_text()).get("base_model_name_or_path")
        except (OSError, ValueError):
            pass
    return {"base_model": base_model, "training_details": details}


def start_local(
    model_id: Optional[str], port: int, api_key: Optional[str], allow_lan: bool
) -> str:
    """Start the local API server; returns the deployment id."""
    params = {"type": "local", "model_id": model_id, "port": port, "allow_lan": allow_lan}
    deployment_id = jobs.create(JOB_TYPE, params, status="running")
    try:
        info = api_server.start(port=port, api_key=api_key, allow_lan=allow_lan, model_id=model_id)
    except Exception as exc:
        jobs.update(deployment_id, status="failed", error=str(exc))
        raise
    jobs.update(deployment_id, result=info)
    return deployment_id


def start_huggingface(
    model_id: str,
    repo_name: str,
    hf_token: Optional[str] = None,
    private: bool = False,
    description: Optional[str] = None,
) -> str:
    """Export a local model to the Hub on a background thread; returns the deployment id."""
    info = inference.resolve_model(model_id)
    if info.kind in ("hf", "remote"):
        raise ValueError(f"'{model_id}' is not a local model")

    deployment_id = jobs.create(
        JOB_TYPE,
        {"type": "huggingface", "model_id": model_id, "repo_name": repo_name, "private": private},
    )

    def run() -> Dict[str, Any]:
        token = hf_token
        if not token:
            from services.hf_auth import get_hf_token

            token = get_hf_token()

        ctx = _model_card_context(info)
        card = build_model_card(
            repo_name=repo_name,
            kind=info.kind,
            base_model=ctx["base_model"],
            description=description,
            training_details=ctx["training_details"],
            filename=Path(info.path).name if info.kind == "gguf" else None,
        )
        jobs.append_log(deployment_id, f"Uploading {info.path} to {repo_name}")
        result = deploy_to_huggingface(
            model_path=info.path, repo_name=repo_name, hf_token=token, private=private, model_card=card
        )
        if result.get("status") != "success":
            raise RuntimeError(result.get("error", "Upload failed"))
        result["repo_url"] = result["url"]
        jobs.append_log(deployment_id, f"Published at {result['url']}")
        return result

    jobs.run_in_thread(deployment_id, run)
    return deployment_id


def stop_deployment(deployment_id: str) -> bool:
    """Stop a running local server (no-op for finished jobs)."""
    job = jobs.get(deployment_id)
    if not job or job["job_type"] != JOB_TYPE:
        return False
    if job["status"] == "running" and job["params"].get("type") == "local":
        api_server.stop()
        jobs.update(deployment_id, status="stopped")
    return True


def get_status(deployment_id: str) -> Dict[str, Any]:
    job = jobs.get(deployment_id)
    if not job or job["job_type"] != JOB_TYPE:
        return {"deployment_id": deployment_id, "status": "not_found", "error": "Deployment not found"}
    return _view(job)


def get_endpoints() -> Dict[str, Any]:
    """Live endpoint info for the running local server (if any)."""
    live = api_server.status()
    return {"endpoints": [live] if live else [], "server": live}


def list_deployments() -> Dict[str, Any]:
    return {"deployments": [_view(j) for j in jobs.list_jobs(job_type=JOB_TYPE, limit=1000)]}
