"""
System Monitor API: live telemetry, history, OOM alerts and context-fit checks.
"""

from fastapi import APIRouter, HTTPException, Query

from services.inference import InferenceError
from services.monitoring import alerts, telemetry

router = APIRouter()


@router.get("/snapshot")
def snapshot():
    """Current CPU / RAM / GPU readings plus any active alerts."""
    reading = telemetry.sample()
    return {**reading, "alerts": alerts.evaluate(reading)}


@router.get("/history")
def history(limit: int = Query(60, ge=1, le=telemetry.HISTORY_SECONDS)):
    return {"points": telemetry.history(limit)}


@router.get("/context-check")
def context_check(model_id: str, context: int = Query(..., ge=1, le=1_000_000)):
    """Estimate whether ``context`` tokens fit in memory for a local model."""
    try:
        return alerts.check_context_fit(model_id, context, telemetry.sample())
    except InferenceError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
