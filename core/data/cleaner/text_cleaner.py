"""
Text Cleaning and Preprocessing
"""

import re
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class TextCleaner:
    """Clean and preprocess text data"""
    
    def __init__(
        self,
        remove_urls: bool = True,
        remove_emails: bool = True,
        remove_extra_whitespace: bool = True,
        min_length: int = 10,
        max_length: Optional[int] = None
    ):
        """
        Initialize text cleaner
        
        Args:
            remove_urls: Remove URLs from text
            remove_emails: Remove email addresses
            remove_extra_whitespace: Normalize whitespace
            min_length: Minimum text length
            max_length: Maximum text length (None = no limit)
        """
        self.remove_urls = remove_urls
        self.remove_emails = remove_emails
        self.remove_extra_whitespace = remove_extra_whitespace
        self.min_length = min_length
        self.max_length = max_length
        
    def clean(self, text: str) -> str:
        """
        Clean a single text string
        
        Args:
            text: Input text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
            
        # Remove URLs
        if self.remove_urls:
            text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
            
        # Remove emails
        if self.remove_emails:
            text = re.sub(r'\S+@\S+', '', text)
            
        # Remove extra whitespace
        if self.remove_extra_whitespace:
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
        return text
        
    def clean_batch(self, texts: List[str]) -> List[str]:
        """
        Clean a batch of texts
        
        Args:
            texts: List of input texts
            
        Returns:
            List of cleaned texts
        """
        cleaned = []
        
        for text in texts:
            cleaned_text = self.clean(text)
            
            # Apply length filters
            if len(cleaned_text) < self.min_length:
                continue
                
            if self.max_length and len(cleaned_text) > self.max_length:
                cleaned_text = cleaned_text[:self.max_length]
                
            cleaned.append(cleaned_text)
            
        logger.info(f"Cleaned {len(texts)} texts -> {len(cleaned)} texts after filtering")
        return cleaned
        
    def remove_duplicates(self, texts: List[str]) -> List[str]:
        """
        Remove duplicate texts
        
        Args:
            texts: List of texts
            
        Returns:
            List of unique texts
        """
        unique = []
        seen = set()
        
        for text in texts:
            text_lower = text.lower().strip()
            if text_lower not in seen:
                seen.add(text_lower)
                unique.append(text)
                
        logger.info(f"Removed {len(texts) - len(unique)} duplicates")
        return unique
        
    def filter_by_language(
        self,
        texts: List[str],
        target_language: str = "en"
    ) -> List[str]:
        """
        Filter texts by language (requires langdetect)
        
        Args:
            texts: List of texts
            target_language: Target language code (e.g., 'en')
            
        Returns:
            Filtered texts
        """
        try:
            from langdetect import detect, LangDetectException
        except ImportError:
            logger.warning("langdetect not installed. Install with: pip install langdetect")
            return texts
            
        filtered = []
        
        for text in texts:
            try:
                if detect(text) == target_language:
                    filtered.append(text)
            except LangDetectException:
                continue
                
        logger.info(f"Language filter: {len(texts)} -> {len(filtered)} texts")
        return filtered
        

def clean_dataset(
    texts: List[str],
    remove_duplicates: bool = True,
    language: Optional[str] = None,
    **kwargs
) -> List[str]:
    """
    High-level function to clean a dataset
    
    Args:
        texts: List of texts to clean
        remove_duplicates: Remove duplicate texts
        language: Filter by language (None = skip)
        **kwargs: Additional cleaning options
        
    Returns:
        Cleaned texts
    """
    cleaner = TextCleaner(
        remove_urls=kwargs.get("remove_urls", True),
        remove_emails=kwargs.get("remove_emails", True),
        remove_extra_whitespace=kwargs.get("remove_extra_whitespace", True),
        min_length=kwargs.get("min_length", 10),
        max_length=kwargs.get("max_length", None),
    )
    
    # Clean texts
    cleaned = cleaner.clean_batch(texts)
    
    # Remove duplicates
    if remove_duplicates:
        cleaned = cleaner.remove_duplicates(cleaned)
        
    # Filter by language
    if language:
        cleaned = cleaner.filter_by_language(cleaned, language)
        
    return cleaned


def clean_crawled_data(crawled_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean crawled web pages
    
    Args:
        crawled_pages: List of crawled page dictionaries
        
    Returns:
        Cleaned pages
    """
    cleaner = TextCleaner()
    cleaned_pages = []
    
    for page in crawled_pages:
        # Clean content
        cleaned_content = cleaner.clean(page.get("content", ""))
        
        if len(cleaned_content) >= cleaner.min_length:
            cleaned_page = page.copy()
            cleaned_page["content"] = cleaned_content
            cleaned_pages.append(cleaned_page)
            
    logger.info(f"Cleaned {len(crawled_pages)} pages -> {len(cleaned_pages)} after filtering")
    return cleaned_pages

