"""
Redis-Backed Deduplication Engine
Combines text hashing with semantic similarity for efficient deduplication
"""

import hashlib
import json
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
import logging

from core.utils import setup_logger

logger = setup_logger("redis_dedup_engine", log_file="logs/dedup_engine.log")


class RedisHashStore:
    """
    Redis-backed hash storage for fast duplicate detection
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        """
        Initialize Redis hash store
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            import redis
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis hash store")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using in-memory fallback.")
            self.redis_client = None
    
    def _get_hash_key(self, namespace: str) -> str:
        """Get Redis key for hash set"""
        return f"dedup:hashes:{namespace}"
    
    def _get_metadata_key(self, namespace: str, text_hash: str) -> str:
        """Get Redis key for hash metadata"""
        return f"dedup:meta:{namespace}:{text_hash}"
    
    def add_hash(
        self,
        text: str,
        namespace: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None
    ) -> Tuple[str, bool]:
        """
        Add text hash to store
        
        Args:
            text: Text to hash
            namespace: Namespace for organization
            metadata: Optional metadata to store with hash
            ttl: Optional TTL in seconds
            
        Returns:
            Tuple of (hash, is_new)
        """
        text_hash = self._compute_hash(text)
        
        if self.redis_client:
            try:
                # Check if hash exists
                hash_key = self._get_hash_key(namespace)
                is_new = self.redis_client.sadd(hash_key, text_hash) == 1
                
                # Store metadata if provided
                if metadata and is_new:
                    meta_key = self._get_metadata_key(namespace, text_hash)
                    metadata_with_timestamp = {
                        **metadata,
                        'added_at': datetime.now().isoformat(),
                        'text_hash': text_hash
                    }
                    self.redis_client.set(
                        meta_key,
                        json.dumps(metadata_with_timestamp),
                        ex=ttl
                    )
                
                # Set TTL on hash set if specified
                if ttl and is_new:
                    self.redis_client.expire(hash_key, ttl)
                
                return text_hash, is_new
                
            except Exception as e:
                logger.error(f"Redis add_hash failed: {e}")
                return text_hash, True  # Assume new on error
        else:
            # In-memory fallback
            return text_hash, True
    
    def check_hash(self, text: str, namespace: str = "default") -> bool:
        """
        Check if text hash exists
        
        Args:
            text: Text to check
            namespace: Namespace to check in
            
        Returns:
            True if hash exists (duplicate), False otherwise
        """
        text_hash = self._compute_hash(text)
        
        if self.redis_client:
            try:
                hash_key = self._get_hash_key(namespace)
                return self.redis_client.sismember(hash_key, text_hash)
            except Exception as e:
                logger.error(f"Redis check_hash failed: {e}")
                return False
        else:
            return False
    
    def get_metadata(self, text_hash: str, namespace: str = "default") -> Optional[Dict[str, Any]]:
        """
        Get metadata for a hash
        
        Args:
            text_hash: Hash to lookup
            namespace: Namespace
            
        Returns:
            Metadata dict or None
        """
        if self.redis_client:
            try:
                meta_key = self._get_metadata_key(namespace, text_hash)
                data = self.redis_client.get(meta_key)
                return json.loads(data) if data else None
            except Exception as e:
                logger.error(f"Redis get_metadata failed: {e}")
                return None
        else:
            return None
    
    def remove_hash(self, text: str, namespace: str = "default") -> bool:
        """
        Remove hash from store
        
        Args:
            text: Text whose hash to remove
            namespace: Namespace
            
        Returns:
            True if removed, False otherwise
        """
        text_hash = self._compute_hash(text)
        
        if self.redis_client:
            try:
                hash_key = self._get_hash_key(namespace)
                meta_key = self._get_metadata_key(namespace, text_hash)
                
                self.redis_client.srem(hash_key, text_hash)
                self.redis_client.delete(meta_key)
                return True
            except Exception as e:
                logger.error(f"Redis remove_hash failed: {e}")
                return False
        else:
            return False
    
    def get_hash_count(self, namespace: str = "default") -> int:
        """
        Get count of hashes in namespace
        
        Args:
            namespace: Namespace to count
            
        Returns:
            Number of hashes
        """
        if self.redis_client:
            try:
                hash_key = self._get_hash_key(namespace)
                return self.redis_client.scard(hash_key)
            except Exception as e:
                logger.error(f"Redis get_hash_count failed: {e}")
                return 0
        else:
            return 0
    
    def clear_namespace(self, namespace: str = "default") -> bool:
        """
        Clear all hashes in namespace
        
        Args:
            namespace: Namespace to clear
            
        Returns:
            True if cleared, False otherwise
        """
        if self.redis_client:
            try:
                hash_key = self._get_hash_key(namespace)
                # Get all hashes to delete metadata
                hashes = self.redis_client.smembers(hash_key)
                
                # Delete metadata
                for text_hash in hashes:
                    meta_key = self._get_metadata_key(namespace, text_hash)
                    self.redis_client.delete(meta_key)
                
                # Delete hash set
                self.redis_client.delete(hash_key)
                return True
            except Exception as e:
                logger.error(f"Redis clear_namespace failed: {e}")
                return False
        else:
            return False
    
    def _compute_hash(self, text: str) -> str:
        """
        Compute hash of text
        
        Args:
            text: Text to hash
            
        Returns:
            Hash string
        """
        # Use SHA256 for better collision resistance than MD5
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def close(self):
        """Close Redis connection"""
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Redis connection closed")
            except:
                pass


class HybridDeduplicationEngine:
    """
    Hybrid deduplication engine combining hash-based and semantic similarity
    Uses Redis for fast hash lookup and FAISS for semantic deduplication
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/1",
        use_redis: bool = True,
        use_semantic: bool = True
    ):
        """
        Initialize deduplication engine
        
        Args:
            redis_url: Redis connection URL
            use_redis: Enable Redis-backed hash storage
            use_semantic: Enable semantic similarity checks
        """
        self.use_redis = use_redis
        self.use_semantic = use_semantic
        
        # Initialize Redis hash store
        self.hash_store = RedisHashStore(redis_url) if use_redis else None
        
        # Initialize semantic model (lazy loading)
        self.semantic_model = None
        
        logger.info(f"Dedup engine initialized (redis={use_redis}, semantic={use_semantic})")
    
    def deduplicate(
        self,
        texts: List[str],
        namespace: str = "default",
        semantic_threshold: float = 0.85,
        strategy: str = "hybrid"
    ) -> Dict[str, Any]:
        """
        Deduplicate texts using hybrid approach
        
        Args:
            texts: List of texts to deduplicate
            namespace: Redis namespace for hash storage
            semantic_threshold: Similarity threshold for semantic dedup
            strategy: 'hash', 'semantic', or 'hybrid'
            
        Returns:
            Dict with unique texts and statistics
        """
        if not texts:
            return {
                'unique_texts': [],
                'stats': {
                    'total': 0,
                    'unique': 0,
                    'duplicates': 0,
                    'hash_duplicates': 0,
                    'semantic_duplicates': 0
                }
            }
        
        logger.info(f"Starting deduplication of {len(texts)} texts (strategy={strategy})")
        
        stats = {
            'total': len(texts),
            'hash_duplicates': 0,
            'semantic_duplicates': 0
        }
        
        # Step 1: Hash-based deduplication
        if strategy in ['hash', 'hybrid']:
            texts, hash_dupes = self._deduplicate_by_hash(texts, namespace)
            stats['hash_duplicates'] = hash_dupes
            logger.info(f"Hash dedup: {len(texts)} unique after removing {hash_dupes} duplicates")
        
        # Step 2: Semantic deduplication
        if strategy in ['semantic', 'hybrid'] and self.use_semantic and len(texts) > 1:
            texts, semantic_dupes = self._deduplicate_by_semantic(texts, semantic_threshold)
            stats['semantic_duplicates'] = semantic_dupes
            logger.info(f"Semantic dedup: {len(texts)} unique after removing {semantic_dupes} duplicates")
        
        stats['unique'] = len(texts)
        stats['duplicates'] = stats['hash_duplicates'] + stats['semantic_duplicates']
        
        return {
            'unique_texts': texts,
            'stats': stats
        }
    
    def _deduplicate_by_hash(
        self,
        texts: List[str],
        namespace: str
    ) -> Tuple[List[str], int]:
        """
        Deduplicate using hash storage
        
        Args:
            texts: Texts to deduplicate
            namespace: Redis namespace
            
        Returns:
            Tuple of (unique texts, duplicate count)
        """
        unique_texts = []
        duplicates = 0
        
        if self.hash_store and self.use_redis:
            # Use Redis
            for text in texts:
                text_hash, is_new = self.hash_store.add_hash(
                    text,
                    namespace=namespace,
                    metadata={'length': len(text)}
                )
                
                if is_new:
                    unique_texts.append(text)
                else:
                    duplicates += 1
        else:
            # Use in-memory set
            seen_hashes = set()
            for text in texts:
                text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
                
                if text_hash not in seen_hashes:
                    seen_hashes.add(text_hash)
                    unique_texts.append(text)
                else:
                    duplicates += 1
        
        return unique_texts, duplicates
    
    def _deduplicate_by_semantic(
        self,
        texts: List[str],
        threshold: float
    ) -> Tuple[List[str], int]:
        """
        Deduplicate using semantic similarity
        
        Args:
            texts: Texts to deduplicate
            threshold: Similarity threshold
            
        Returns:
            Tuple of (unique texts, duplicate count)
        """
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
            
            # Load model if not loaded
            if self.semantic_model is None:
                logger.info("Loading semantic model (all-MiniLM-L6-v2)")
                self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Encode texts
            embeddings = self.semantic_model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False
            ).astype('float32')
            
            # Normalize for cosine similarity
            faiss.normalize_L2(embeddings)
            
            # Create FAISS index
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatIP(dimension)
            index.add(embeddings)
            
            # Find duplicates
            k = min(100, len(texts))
            similarities, indices = index.search(embeddings, k)
            
            unique_indices = []
            seen_indices = set()
            duplicates = 0
            
            for i in range(len(texts)):
                if i in seen_indices:
                    continue
                
                unique_indices.append(i)
                
                # Mark similar texts as duplicates
                for j, sim in zip(indices[i], similarities[i]):
                    if j != i and sim >= threshold and j not in seen_indices:
                        seen_indices.add(int(j))
                        duplicates += 1
            
            unique_texts = [texts[i] for i in unique_indices]
            
            return unique_texts, duplicates
            
        except Exception as e:
            logger.error(f"Semantic deduplication failed: {e}")
            return texts, 0
    
    def check_duplicate(
        self,
        text: str,
        namespace: str = "default",
        check_semantic: bool = False,
        semantic_threshold: float = 0.85
    ) -> Dict[str, Any]:
        """
        Check if a single text is a duplicate
        
        Args:
            text: Text to check
            namespace: Redis namespace
            check_semantic: Also check semantic similarity
            semantic_threshold: Similarity threshold
            
        Returns:
            Dict with duplicate status and details
        """
        result = {
            'is_duplicate': False,
            'hash_duplicate': False,
            'semantic_duplicate': False,
            'text_hash': None,
            'similarity': None
        }
        
        # Check hash
        if self.hash_store and self.use_redis:
            result['hash_duplicate'] = self.hash_store.check_hash(text, namespace)
            result['is_duplicate'] = result['hash_duplicate']
            result['text_hash'] = self.hash_store._compute_hash(text)
        
        # TODO: Implement semantic check against stored embeddings
        # This would require storing embeddings in Redis or a vector DB
        
        return result
    
    def get_stats(self, namespace: str = "default") -> Dict[str, Any]:
        """
        Get deduplication statistics
        
        Args:
            namespace: Redis namespace
            
        Returns:
            Statistics dict
        """
        stats = {
            'namespace': namespace,
            'hash_count': 0,
            'redis_connected': self.hash_store is not None and self.hash_store.redis_client is not None,
            'semantic_enabled': self.use_semantic,
            'model_loaded': self.semantic_model is not None
        }
        
        if self.hash_store:
            stats['hash_count'] = self.hash_store.get_hash_count(namespace)
        
        return stats
    
    def clear(self, namespace: str = "default") -> bool:
        """
        Clear deduplication data for namespace
        
        Args:
            namespace: Namespace to clear
            
        Returns:
            True if successful
        """
        if self.hash_store:
            return self.hash_store.clear_namespace(namespace)
        return True
    
    def close(self):
        """Close connections"""
        if self.hash_store:
            self.hash_store.close()


# Global deduplication engine instance
dedup_engine = HybridDeduplicationEngine()

