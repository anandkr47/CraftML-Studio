"""
Text Cleaning Module
Preprocessing and normalization of text data
"""

from core.data.cleaner.text_cleaner import (
    TextCleaner,
    clean_crawled_data,
)


def clean_text(text: str) -> str:
    """Clean a single text string using default cleaner settings."""
    return TextCleaner().clean(text)


def clean_batch(texts):
    """Clean a batch of texts using default cleaner settings."""
    return TextCleaner().clean_batch(list(texts))


__all__ = ['TextCleaner', 'clean_text', 'clean_batch', 'clean_crawled_data']
