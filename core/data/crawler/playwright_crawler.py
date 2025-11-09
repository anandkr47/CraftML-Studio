"""
Playwright-based Web Crawler
Handles JavaScript-rendered pages and SPAs
"""

import asyncio
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse
import logging
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
import hashlib
import time

logger = logging.getLogger(__name__)


@dataclass
class CrawledPage:
    """Represents a crawled web page"""
    url: str
    title: str
    content: str
    timestamp: float
    depth: int
    content_hash: str
    relevance_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PlaywrightCrawler:
    """
    Advanced web crawler using Playwright for JavaScript rendering
    """
    
    def __init__(
        self,
        max_depth: int = 3,
        max_pages: int = 100,
        timeout: int = 30,
        user_agent: str = "CraftML-Studio/1.0",
        headless: bool = True,
        wait_for_content: bool = True
    ):
        """
        Initialize Playwright crawler
        
        Args:
            max_depth: Maximum crawl depth
            max_pages: Maximum pages to crawl
            timeout: Request timeout in seconds
            user_agent: User agent string
            headless: Run browser in headless mode
            wait_for_content: Wait for dynamic content to load
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.timeout = timeout * 1000  # Convert to milliseconds
        self.user_agent = user_agent
        self.headless = headless
        self.wait_for_content = wait_for_content
        
        self.visited_urls: Set[str] = set()
        self.crawled_pages: List[CrawledPage] = []
        self.content_hashes: Set[str] = set()
        
    async def crawl(
        self,
        seed_urls: List[str],
        query: Optional[str] = None
    ) -> List[CrawledPage]:
        """
        Start crawling from seed URLs
        
        Args:
            seed_urls: Starting URLs
            query: Optional query for relevance filtering
            
        Returns:
            List of crawled pages
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright && playwright install")
            raise
        
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(user_agent=self.user_agent)
            
            try:
                # Crawl each seed URL
                for seed_url in seed_urls:
                    if len(self.crawled_pages) >= self.max_pages:
                        break
                    
                    await self._crawl_recursive(context, seed_url, depth=0)
                
            finally:
                await context.close()
                await browser.close()
        
        return self.crawled_pages
    
    async def _crawl_recursive(
        self,
        context,
        url: str,
        depth: int
    ):
        """
        Recursively crawl pages
        
        Args:
            context: Playwright browser context
            url: URL to crawl
            depth: Current depth
        """
        # Check limits
        if depth > self.max_depth:
            return
        if len(self.crawled_pages) >= self.max_pages:
            return
        if url in self.visited_urls:
            return
        
        # Mark as visited
        self.visited_urls.add(url)
        
        try:
            # Create new page
            page = await context.new_page()
            
            try:
                # Navigate to URL
                logger.info(f"Crawling: {url} (depth: {depth})")
                await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                
                # Wait for dynamic content if enabled
                if self.wait_for_content:
                    await page.wait_for_load_state("networkidle", timeout=self.timeout)
                    await asyncio.sleep(1)  # Extra wait for JS rendering
                
                # Get page content
                html = await page.content()
                
                # Extract content
                crawled_page = self._extract_content(html, url, depth)
                
                if crawled_page:
                    # Check for duplicate content
                    if crawled_page.content_hash not in self.content_hashes:
                        self.content_hashes.add(crawled_page.content_hash)
                        self.crawled_pages.append(crawled_page)
                        
                        logger.info(f"Crawled: {url} ({len(self.crawled_pages)}/{self.max_pages})")
                        
                        # Extract and follow links
                        if depth < self.max_depth and len(self.crawled_pages) < self.max_pages:
                            links = await self._extract_links(page, url)
                            
                            # Crawl links
                            for link in links[:10]:  # Limit links per page
                                if len(self.crawled_pages) >= self.max_pages:
                                    break
                                await self._crawl_recursive(context, link, depth + 1)
                
            finally:
                await page.close()
                
        except Exception as e:
            logger.warning(f"Failed to crawl {url}: {str(e)}")
    
    def _extract_content(
        self,
        html: str,
        url: str,
        depth: int
    ) -> Optional[CrawledPage]:
        """
        Extract content from HTML
        
        Args:
            html: HTML content
            url: Page URL
            depth: Crawl depth
            
        Returns:
            CrawledPage object or None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style tags
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            # Extract title
            title_tag = soup.find('title')
            title = title_tag.get_text().strip() if title_tag else url
            
            # Extract main content
            # Try to find main content area
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            
            if main_content:
                content = main_content.get_text(separator=' ', strip=True)
            else:
                content = soup.get_text(separator=' ', strip=True)
            
            # Clean content
            content = ' '.join(content.split())
            
            # Skip if content is too short
            if len(content) < 100:
                return None
            
            # Create content hash
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            return CrawledPage(
                url=url,
                title=title,
                content=content,
                timestamp=time.time(),
                depth=depth,
                content_hash=content_hash
            )
            
        except Exception as e:
            logger.error(f"Failed to extract content from {url}: {str(e)}")
            return None
    
    async def _extract_links(self, page, base_url: str) -> List[str]:
        """
        Extract links from page
        
        Args:
            page: Playwright page object
            base_url: Base URL for resolving relative links
            
        Returns:
            List of absolute URLs
        """
        try:
            # Get all links
            links = await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(href => href.startsWith('http'));
            }''')
            
            # Filter and normalize
            base_domain = urlparse(base_url).netloc
            valid_links = []
            
            for link in links:
                parsed = urlparse(link)
                
                # Same domain only
                if parsed.netloc == base_domain:
                    # Remove fragments
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if parsed.query:
                        clean_url += f"?{parsed.query}"
                    
                    if clean_url not in self.visited_urls:
                        valid_links.append(clean_url)
            
            return valid_links
            
        except Exception as e:
            logger.error(f"Failed to extract links: {str(e)}")
            return []


async def crawl_with_playwright(
    seed_urls: List[str],
    max_depth: int = 3,
    max_pages: int = 100,
    query: Optional[str] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    High-level function to crawl with Playwright
    
    Args:
        seed_urls: Starting URLs
        max_depth: Maximum crawl depth
        max_pages: Maximum pages to collect
        query: Optional query for relevance filtering
        **kwargs: Additional crawler options
        
    Returns:
        List of crawled page dictionaries
    """
    crawler = PlaywrightCrawler(
        max_depth=max_depth,
        max_pages=max_pages,
        timeout=kwargs.get("timeout", 30),
        headless=kwargs.get("headless", True),
        wait_for_content=kwargs.get("wait_for_content", True)
    )
    
    pages = await crawler.crawl(seed_urls, query=query)
    
    return [page.to_dict() for page in pages]

