"""
Deduplication API Routes
Provides endpoints for text and dataset deduplication
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field
from services.redis_dedup_engine import dedup_engine

router = APIRouter()


class DeduplicationRequest(BaseModel):
    """Request for text deduplication"""
    texts: List[str] = Field(..., min_items=1, description="Texts to deduplicate")
    namespace: str = Field(default="default", description="Redis namespace")
    semantic_threshold: float = Field(default=0.85, ge=0.0, le=1.0, description="Semantic similarity threshold")
    strategy: str = Field(default="hybrid", description="Strategy: hash, semantic, or hybrid")


class DuplicateCheckRequest(BaseModel):
    """Request to check if text is duplicate"""
    text: str = Field(..., description="Text to check")
    namespace: str = Field(default="default", description="Redis namespace")
    check_semantic: bool = Field(default=False, description="Also check semantic similarity")
    semantic_threshold: float = Field(default=0.85, ge=0.0, le=1.0)


class DeduplicationResponse(BaseModel):
    """Response from deduplication"""
    unique_texts: List[str]
    stats: dict


class DuplicateCheckResponse(BaseModel):
    """Response from duplicate check"""
    is_duplicate: bool
    hash_duplicate: bool
    semantic_duplicate: bool
    text_hash: Optional[str]
    similarity: Optional[float]


class StatsResponse(BaseModel):
    """Deduplication statistics"""
    namespace: str
    hash_count: int
    redis_connected: bool
    semantic_enabled: bool
    model_loaded: bool


@router.post("/deduplicate", response_model=DeduplicationResponse)
async def deduplicate_texts(request: DeduplicationRequest):
    """
    Deduplicate a list of texts
    
    Args:
        request: Deduplication parameters
        
    Returns:
        Unique texts and statistics
    """
    try:
        result = dedup_engine.deduplicate(
            texts=request.texts,
            namespace=request.namespace,
            semantic_threshold=request.semantic_threshold,
            strategy=request.strategy
        )
        
        return DeduplicationResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check", response_model=DuplicateCheckResponse)
async def check_duplicate(request: DuplicateCheckRequest):
    """
    Check if a single text is a duplicate
    
    Args:
        request: Duplicate check parameters
        
    Returns:
        Duplicate status and details
    """
    try:
        result = dedup_engine.check_duplicate(
            text=request.text,
            namespace=request.namespace,
            check_semantic=request.check_semantic,
            semantic_threshold=request.semantic_threshold
        )
        
        return DuplicateCheckResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats(namespace: str = Query("default", description="Redis namespace")):
    """
    Get deduplication statistics for a namespace
    
    Args:
        namespace: Redis namespace
        
    Returns:
        Statistics
    """
    try:
        stats = dedup_engine.get_stats(namespace=namespace)
        return StatsResponse(**stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_namespace(namespace: str = Query("default", description="Redis namespace")):
    """
    Clear all hashes in a namespace
    
    Args:
        namespace: Namespace to clear
        
    Returns:
        Success status
    """
    try:
        success = dedup_engine.clear(namespace=namespace)
        
        if success:
            return {
                'status': 'success',
                'message': f'Namespace "{namespace}" cleared successfully'
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to clear namespace")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Check deduplication engine health
    
    Returns:
        Health status
    """
    try:
        stats = dedup_engine.get_stats()
        
        return {
            'status': 'healthy' if stats['redis_connected'] else 'degraded',
            'redis_connected': stats['redis_connected'],
            'semantic_enabled': stats['semantic_enabled'],
            'model_loaded': stats['model_loaded'],
            'message': 'Deduplication engine operational'
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'message': 'Deduplication engine error'
        }

