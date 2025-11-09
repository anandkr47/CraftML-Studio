"""
Core Data Processing Module
Handles data crawling, cleaning, formatting, and loading
"""

from core.data.crawler import WebCrawler, start_crawling, start_crawl
from core.data.cleaner import TextCleaner, clean_text, clean_crawled_data
from core.data.formatter import (
    DatasetFormatter,
    format_dataset,
    save_as_jsonl,
    save_as_csv
)
from core.data.dataset_utils import (
    DatasetLoader,
    load_and_prepare_dataset,
    format_for_instruction_tuning,
    format_for_chat
)

__all__ = [
    # Crawler
    'WebCrawler',
    'start_crawling',
    'start_crawl',
    
    # Cleaner
    'TextCleaner',
    'clean_text',
    'clean_crawled_data',
    
    # Formatter
    'DatasetFormatter',
    'format_dataset',
    'save_as_jsonl',
    'save_as_csv',
    
    # Dataset Utils
    'DatasetLoader',
    'load_and_prepare_dataset',
    'format_for_instruction_tuning',
    'format_for_chat',
]
