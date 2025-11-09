"""
Settings API Routes
Handles application settings including HuggingFace token management
"""

import os
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Settings directory
SETTINGS_DIR = Path.home() / ".craftml" / "settings"
SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

# Encryption key file
KEY_FILE = SETTINGS_DIR / ".key"
TOKEN_FILE = SETTINGS_DIR / "hf_token.enc"

# Initialize or load encryption key
if not KEY_FILE.exists():
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
else:
    key = KEY_FILE.read_bytes()

cipher = Fernet(key)


class HFTokenRequest(BaseModel):
    """Request model for saving HuggingFace token"""
    token: str = Field(..., min_length=10, description="HuggingFace access token")


class HFTokenStatus(BaseModel):
    """Response model for token status"""
    is_authenticated: bool
    username: str | None = None
    token_preview: str | None = None


def encrypt_token(token: str) -> bytes:
    """Encrypt a token"""
    return cipher.encrypt(token.encode())


def decrypt_token(encrypted_token: bytes) -> str:
    """Decrypt a token"""
    return cipher.decrypt(encrypted_token).decode()


def verify_hf_token(token: str) -> dict:
    """
    Verify HuggingFace token by making a test API call
    Returns user info if valid
    """
    try:
        from huggingface_hub import whoami
        user_info = whoami(token=token)
        return {
            "valid": True,
            "username": user_info.get("name", "Unknown"),
            "email": user_info.get("email"),
        }
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return {"valid": False, "error": str(e)}


@router.post("/hf-token")
async def save_hf_token(request: HFTokenRequest):
    """
    Save HuggingFace access token (encrypted)
    
    Args:
        request: Token request with the access token
        
    Returns:
        Success status and user info
    """
    try:
        token = request.token.strip()
        
        # Validate token format
        if not token.startswith("hf_"):
            raise HTTPException(
                status_code=400,
                detail="Invalid token format. HuggingFace tokens start with 'hf_'"
            )
        
        # Verify token with HuggingFace
        verification = verify_hf_token(token)
        if not verification.get("valid"):
            raise HTTPException(
                status_code=401,
                detail=f"Invalid token: {verification.get('error', 'Could not verify token')}"
            )
        
        # Encrypt and save token
        encrypted_token = encrypt_token(token)
        TOKEN_FILE.write_bytes(encrypted_token)
        
        # Save metadata
        metadata = {
            "username": verification.get("username"),
            "email": verification.get("email"),
            "token_preview": f"{token[:8]}...{token[-4:]}",
        }
        metadata_file = SETTINGS_DIR / "hf_metadata.json"
        metadata_file.write_text(json.dumps(metadata))
        
        logger.info(f"HuggingFace token saved for user: {verification.get('username')}")
        
        return {
            "success": True,
            "message": "Token saved successfully",
            "username": verification.get("username"),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving HF token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save token: {str(e)}")


@router.get("/hf-token/status", response_model=HFTokenStatus)
async def get_hf_token_status():
    """
    Get HuggingFace token status
    
    Returns:
        Token status and user info (if authenticated)
    """
    try:
        if not TOKEN_FILE.exists():
            return HFTokenStatus(is_authenticated=False)
        
        # Load metadata
        metadata_file = SETTINGS_DIR / "hf_metadata.json"
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text())
        else:
            metadata = {}
        
        return HFTokenStatus(
            is_authenticated=True,
            username=metadata.get("username"),
            token_preview=metadata.get("token_preview"),
        )
        
    except Exception as e:
        logger.error(f"Error getting HF token status: {e}")
        return HFTokenStatus(is_authenticated=False)


@router.get("/hf-token")
async def get_hf_token():
    """
    Get decrypted HuggingFace token (for internal use)
    
    Returns:
        Decrypted token
    """
    try:
        if not TOKEN_FILE.exists():
            raise HTTPException(status_code=404, detail="No token found")
        
        encrypted_token = TOKEN_FILE.read_bytes()
        token = decrypt_token(encrypted_token)
        
        return {"token": token}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving HF token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve token: {str(e)}")


@router.delete("/hf-token")
async def delete_hf_token():
    """
    Delete HuggingFace token
    
    Returns:
        Success status
    """
    try:
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
        
        metadata_file = SETTINGS_DIR / "hf_metadata.json"
        if metadata_file.exists():
            metadata_file.unlink()
        
        logger.info("HuggingFace token deleted")
        
        return {
            "success": True,
            "message": "Token deleted successfully"
        }
        
    except Exception as e:
        logger.error(f"Error deleting HF token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete token: {str(e)}")

