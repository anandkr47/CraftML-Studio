"""
Settings API
Hugging Face token management. The token lives in the encrypted SecretStore and is never
returned by any endpoint (the old ``GET /hf-token`` that exposed it in plaintext is gone).
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import hf_auth

router = APIRouter()
logger = logging.getLogger(__name__)


class HFTokenRequest(BaseModel):
    """Request model for saving a HuggingFace token"""
    token: str = Field(..., min_length=10, description="HuggingFace access token")


class HFTokenStatus(BaseModel):
    """Response model for token status"""
    is_authenticated: bool
    username: str | None = None
    token_preview: str | None = None


def verify_hf_token(token: str) -> dict:
    """Verify a token with a test API call; returns user info if valid."""
    try:
        from huggingface_hub import whoami

        user_info = whoami(token=token)
        return {"valid": True, "username": user_info.get("name", "Unknown")}
    except Exception as e:
        logger.error(f"Token verification failed: {type(e).__name__}")
        return {"valid": False, "error": str(e)}


@router.post("/hf-token")
def save_hf_token(request: HFTokenRequest):
    """Verify and save a HuggingFace access token (encrypted)."""
    token = request.token.strip()
    if not token.startswith("hf_"):
        raise HTTPException(status_code=400, detail="Invalid token format. HuggingFace tokens start with 'hf_'")

    verification = verify_hf_token(token)
    if not verification.get("valid"):
        raise HTTPException(
            status_code=401, detail=f"Invalid token: {verification.get('error', 'Could not verify token')}"
        )

    hf_auth.save_hf_token(token, verification.get("username"))
    logger.info("HuggingFace token saved for user: %s", verification.get("username"))
    return {"success": True, "message": "Token saved successfully", "username": verification.get("username")}


@router.get("/hf-token/status", response_model=HFTokenStatus)
def get_hf_token_status():
    """Token status and user name (never the token itself)."""
    return HFTokenStatus(**hf_auth.status())


@router.delete("/hf-token")
def delete_hf_token():
    hf_auth.delete_hf_token()
    logger.info("HuggingFace token deleted")
    return {"success": True, "message": "Token deleted successfully"}
