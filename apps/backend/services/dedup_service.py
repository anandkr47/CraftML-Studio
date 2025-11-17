"""
Deduplication Service
Handles text deduplication using FAISS and similarity matching
"""

import sys
from pathlib import Path
import hashlib
from typing import List, Set, Dict, Any
import logging

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.utils import setup_logger
from core.config import settings

logger = setup_logger("dedup_service", log_file=str(settings.logs_dir / "dedup_service.log"))


def deduplicate_by_hash(texts: List[str]) -> List[str]:
    """
    Deduplicate texts using MD5 hashing
    
    Args:
        texts: List of text strings
        
    Returns:
        Deduplicated list
    """
    seen_hashes: Set[str] = set()
    unique_texts = []
    
    for text in texts:
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        if text_hash not in seen_hashes:
            seen_hashes.add(text_hash)
            unique_texts.append(text)
    
    logger.info(f"Deduplicated {len(texts)} texts to {len(unique_texts)} unique texts")
    return unique_texts


def deduplicate_by_similarity(texts: List[str], threshold: float = 0.9) -> List[str]:
    """
    Deduplicate texts using semantic similarity (requires sentence-transformers)
    
    Args:
        texts: List of text strings
        threshold: Similarity threshold (0-1)
        
    Returns:
        Deduplicated list
    """
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        
        logger.info(f"Deduplicating {len(texts)} texts using similarity threshold {threshold}")
        
        # Load model
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Encode texts
        embeddings = model.encode(texts, show_progress_bar=True)
        
        # Find duplicates
        unique_indices = []
        seen_indices = set()
        
        for i, embedding in enumerate(embeddings):
            if i in seen_indices:
                continue
            
            unique_indices.append(i)
            
            # Check similarity with remaining texts
            for j in range(i + 1, len(embeddings)):
                if j in seen_indices:
                    continue
                
                similarity = cosine_similarity([embedding], [embeddings[j]])[0][0]
                
                if similarity >= threshold:
                    seen_indices.add(j)
        
        unique_texts = [texts[i] for i in unique_indices]
        
        logger.info(f"Similarity deduplication: {len(texts)} -> {len(unique_texts)} texts")
        return unique_texts
        
    except ImportError:
        logger.warning("sentence-transformers not installed, falling back to hash deduplication")
        return deduplicate_by_hash(texts)
    except Exception as e:
        logger.error(f"Similarity deduplication failed: {e}")
        return deduplicate_by_hash(texts)


def deduplicate_with_faiss(
    texts: List[str],
    threshold: float = 0.9,
    batch_size: int = 1000
) -> List[str]:
    """
    Deduplicate texts using FAISS for fast similarity search
    
    Args:
        texts: List of text strings
        threshold: Similarity threshold (0-1)
        batch_size: Batch size for encoding
        
    Returns:
        Deduplicated list
    """
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        import faiss
        
        logger.info(f"Deduplicating {len(texts)} texts using FAISS (threshold={threshold})")
        
        # Load model
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Encode texts in batches
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        embeddings = embeddings.astype('float32')
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Create FAISS index
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)  # Inner product = cosine sim for normalized vectors
        index.add(embeddings)
        
        # Search for duplicates
        k = min(100, len(texts))  # Search up to 100 neighbors
        similarities, indices = index.search(embeddings, k)
        
        # Find unique texts
        unique_indices = []
        seen_indices = set()
        
        for i in range(len(texts)):
            if i in seen_indices:
                continue
            
            unique_indices.append(i)
            
            # Mark similar texts as seen
            for j, sim in zip(indices[i], similarities[i]):
                if j != i and sim >= threshold:
                    seen_indices.add(int(j))
        
        unique_texts = [texts[i] for i in unique_indices]
        
        logger.info(f"FAISS deduplication: {len(texts)} -> {len(unique_texts)} texts")
        return unique_texts
        
    except ImportError as e:
        logger.warning(f"FAISS not available: {e}, falling back to similarity deduplication")
        return deduplicate_by_similarity(texts, threshold)
    except Exception as e:
        logger.error(f"FAISS deduplication failed: {e}")
        return deduplicate_by_similarity(texts, threshold)


def deduplicate_dataset(
    data: List[Dict[str, Any]],
    field: str = "content",
    method: str = "hash"
) -> List[Dict[str, Any]]:
    """
    Deduplicate a dataset based on a specific field
    
    Args:
        data: List of data dictionaries
        field: Field to use for deduplication
        method: Deduplication method ('hash', 'similarity', or 'faiss')
        
    Returns:
        Deduplicated dataset
    """
    # Extract texts
    texts = [item.get(field, "") for item in data]
    
    # Deduplicate
    if method == "faiss":
        unique_texts = deduplicate_with_faiss(texts)
    elif method == "similarity":
        unique_texts = deduplicate_by_similarity(texts)
    else:
        unique_texts = deduplicate_by_hash(texts)
    
    # Filter original data
    unique_texts_set = set(unique_texts)
    unique_data = [item for item in data if item.get(field, "") in unique_texts_set]
    
    return unique_data
