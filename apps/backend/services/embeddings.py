"""
Local embedding generation (sentence-transformers).

Used by /v1/embeddings and the knowledge base.  The model is loaded lazily on
first use; the default is a small CPU-friendly BGE model.
"""

import threading
from typing import List, Optional

from core.config import settings
from core.utils import setup_logger

logger = setup_logger("embeddings", log_file=str(settings.logs_dir / "embeddings.log"))

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

_model = None
_model_name: Optional[str] = None
_lock = threading.Lock()


def _get_model(name: str):
    global _model, _model_name
    with _lock:
        if _model is None or _model_name != name:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model {name}")
            _model = SentenceTransformer(name)
            _model_name = name
        return _model


def embed(texts: List[str], model_name: str = DEFAULT_EMBEDDING_MODEL) -> List[List[float]]:
    """Return L2-normalised embeddings, one vector per input text."""
    if not texts:
        return []
    vectors = _get_model(model_name).encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def dimension(model_name: str = DEFAULT_EMBEDDING_MODEL) -> int:
    return int(_get_model(model_name).get_sentence_embedding_dimension())
