"""
Web Crawler Module
Context-based crawling with deduplication and AI filtering
"""

from core.data.crawler.web_crawler import WebCrawler, CrawledPage, start_crawling, start_crawl
from core.data.crawler.playwright_crawler import PlaywrightCrawler, crawl_with_playwright
from core.data.crawler.ai_filter import AIContentFilter, filter_crawled_pages, summarize_pages

__all__ = [
    'WebCrawler',
    'CrawledPage',
    'start_crawling',
    'start_crawl',
    'PlaywrightCrawler',
    'crawl_with_playwright',
    'AIContentFilter',
    'filter_crawled_pages',
    'summarize_pages'
]
