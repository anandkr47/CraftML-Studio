"""
AI-based Content Filtering and Summarization
Uses MiniLM for quick filtering or Llama for better quality
"""

from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class AIContentFilter:
    """
    Filter and summarize content using AI models
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        use_gpu: bool = False
    ):
        """
        Initialize AI filter
        
        Args:
            model_name: Model to use (MiniLM or Llama)
            use_gpu: Use GPU if available
        """
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.model = None
        self.tokenizer = None
        
    def load_model(self):
        """Load the AI model"""
        if self.model is not None:
            return
        
        try:
            if "MiniLM" in self.model_name or "sentence" in self.model_name:
                # Use sentence-transformers for embedding-based filtering
                from sentence_transformers import SentenceTransformer
                
                logger.info(f"Loading SentenceTransformer: {self.model_name}")
                device = "cuda" if self.use_gpu else "cpu"
                self.model = SentenceTransformer(self.model_name, device=device)
                
            else:
                # Use transformers for summarization
                from transformers import AutoTokenizer, AutoModelForCausalLM
                import torch
                
                logger.info(f"Loading model: {self.model_name}")
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float16 if self.use_gpu else torch.float32,
                    device_map="auto" if self.use_gpu else None
                )
                
            logger.info("Model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def filter_by_relevance(
        self,
        pages: List[Dict[str, Any]],
        query: str,
        threshold: float = 0.3,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter pages by relevance to query
        
        Args:
            pages: List of crawled pages
            query: Search query/topic
            threshold: Minimum relevance score (0-1)
            top_k: Return only top K pages (None = all above threshold)
            
        Returns:
            Filtered pages with relevance scores
        """
        if not query:
            return pages
        
        self.load_model()
        
        try:
            from sentence_transformers import util
            
            # Encode query
            query_embedding = self.model.encode(query, convert_to_tensor=True)
            
            # Encode page contents
            contents = [page.get("content", "")[:1000] for page in pages]  # Limit length
            content_embeddings = self.model.encode(contents, convert_to_tensor=True)
            
            # Calculate similarities
            similarities = util.cos_sim(query_embedding, content_embeddings)[0]
            
            # Add scores to pages
            for page, score in zip(pages, similarities):
                page["relevance_score"] = float(score)
            
            # Filter by threshold
            filtered = [p for p in pages if p["relevance_score"] >= threshold]
            
            # Sort by relevance
            filtered.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            # Limit to top K
            if top_k:
                filtered = filtered[:top_k]
            
            logger.info(f"Filtered {len(pages)} pages to {len(filtered)} relevant pages")
            
            return filtered
            
        except Exception as e:
            logger.error(f"Relevance filtering failed: {e}")
            return pages
    
    def summarize_content(
        self,
        content: str,
        max_length: int = 150
    ) -> str:
        """
        Summarize content using AI
        
        Args:
            content: Text to summarize
            max_length: Maximum summary length
            
        Returns:
            Summarized text
        """
        self.load_model()
        
        try:
            # Simple extractive summarization - take first N words
            words = content.split()
            if len(words) <= max_length:
                return content
            
            # Take first sentences up to max_length
            summary_words = words[:max_length]
            summary = ' '.join(summary_words)
            
            # Try to end at sentence boundary
            last_period = summary.rfind('.')
            if last_period > max_length * 0.7:  # If period is reasonably close to end
                summary = summary[:last_period + 1]
            else:
                summary += "..."
            
            return summary
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return content[:max_length * 5] + "..."
    
    def extract_key_information(
        self,
        pages: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Extract and rank key information from pages
        
        Args:
            pages: List of crawled pages
            query: Search query
            
        Returns:
            Pages with extracted key information
        """
        # Filter by relevance first
        relevant_pages = self.filter_by_relevance(pages, query, threshold=0.2)
        
        # Add summaries
        for page in relevant_pages:
            content = page.get("content", "")
            page["summary"] = self.summarize_content(content, max_length=100)
            
            # Extract first paragraph as key info
            paragraphs = content.split('\n')
            page["key_info"] = paragraphs[0][:300] if paragraphs else ""
        
        return relevant_pages


def filter_crawled_pages(
    pages: List[Dict[str, Any]],
    query: Optional[str] = None,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.3,
    top_k: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    High-level function to filter crawled pages with AI
    
    Args:
        pages: List of crawled pages
        query: Search query for relevance filtering
        model_name: Model to use for filtering
        threshold: Minimum relevance score
        top_k: Return only top K pages
        
    Returns:
        Filtered pages
    """
    if not query:
        return pages
    
    filter_ai = AIContentFilter(model_name=model_name)
    return filter_ai.filter_by_relevance(pages, query, threshold, top_k)


def summarize_pages(
    pages: List[Dict[str, Any]],
    max_length: int = 150
) -> List[Dict[str, Any]]:
    """
    Add summaries to pages
    
    Args:
        pages: List of pages
        max_length: Maximum summary length
        
    Returns:
        Pages with summaries
    """
    filter_ai = AIContentFilter()
    filter_ai.load_model()
    
    for page in pages:
        content = page.get("content", "")
        page["summary"] = filter_ai.summarize_content(content, max_length)
    
    return pages

