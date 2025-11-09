"""
Web Crawler for Dataset Collection
Context-based crawling with deduplication
"""

import asyncio
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse
import logging
from bs4 import BeautifulSoup
import aiohttp
from dataclasses import dataclass, asdict
import hashlib

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
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WebCrawler:
    """Asynchronous web crawler for dataset collection"""
    
    def __init__(
        self,
        max_depth: int = 3,
        max_pages: int = 100,
        timeout: int = 30,
        user_agent: str = "CraftML-Studio/1.0"
    ):
        """
        Initialize crawler
        
        Args:
            max_depth: Maximum crawl depth
            max_pages: Maximum pages to crawl
            timeout: Request timeout in seconds
            user_agent: User agent string
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.timeout = timeout
        self.user_agent = user_agent
        
        self.visited_urls: Set[str] = set()
        self.crawled_pages: List[CrawledPage] = []
        self.content_hashes: Set[str] = set()
        
    async def fetch_page(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> Optional[str]:
        """
        Fetch a single page
        
        Args:
            session: aiohttp session
            url: URL to fetch
            
        Returns:
            Page HTML or None if failed
        """
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": self.user_agent}
            ) as response:
                if response.status == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'text/html' in content_type:
                        return await response.text()
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {str(e)}")
            
        return None
        
    def extract_content(self, html: str, url: str) -> Optional[CrawledPage]:
        """
        Extract content from HTML
        
        Args:
            html: HTML content
            url: Page URL
            
        Returns:
            CrawledPage object or None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
                
            # Extract title
            title = soup.title.string if soup.title else ""
            
            # Extract main content
            # Try to find main content area
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)
                
            # Clean up text
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            content = '\n'.join(lines)
            
            # Calculate content hash for deduplication
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Check if we've seen this content before
            if content_hash in self.content_hashes:
                logger.debug(f"Duplicate content found: {url}")
                return None
                
            self.content_hashes.add(content_hash)
            
            import time
            return CrawledPage(
                url=url,
                title=title,
                content=content,
                timestamp=time.time(),
                depth=0,
                content_hash=content_hash
            )
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return None
            
    def extract_links(self, html: str, base_url: str) -> List[str]:
        """
        Extract links from HTML
        
        Args:
            html: HTML content
            base_url: Base URL for resolving relative links
            
        Returns:
            List of absolute URLs
        """
        links = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Convert to absolute URL
                absolute_url = urljoin(base_url, href)
                
                # Parse URL
                parsed = urlparse(absolute_url)
                
                # Only keep http/https links from same domain
                base_domain = urlparse(base_url).netloc
                if parsed.scheme in ['http', 'https'] and parsed.netloc == base_domain:
                    # Remove fragment
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if parsed.query:
                        clean_url += f"?{parsed.query}"
                        
                    links.append(clean_url)
                    
        except Exception as e:
            logger.error(f"Error extracting links: {str(e)}")
            
        return list(set(links))  # Remove duplicates
        
    async def crawl_url(
        self,
        session: aiohttp.ClientSession,
        url: str,
        depth: int = 0
    ):
        """
        Recursively crawl a URL
        
        Args:
            session: aiohttp session
            url: URL to crawl
            depth: Current crawl depth
        """
        # Check limits
        if depth > self.max_depth:
            return
            
        if len(self.crawled_pages) >= self.max_pages:
            return
            
        if url in self.visited_urls:
            return
            
        self.visited_urls.add(url)
        logger.info(f"Crawling: {url} (depth={depth})")
        
        # Fetch page
        html = await self.fetch_page(session, url)
        if not html:
            return
            
        # Extract content
        page = self.extract_content(html, url)
        if page:
            page.depth = depth
            self.crawled_pages.append(page)
            logger.info(f"Extracted content from {url} ({len(page.content)} chars)")
            
        # Extract and crawl links
        if depth < self.max_depth and len(self.crawled_pages) < self.max_pages:
            links = self.extract_links(html, url)
            
            # Crawl links
            tasks = []
            for link in links[:10]:  # Limit concurrent links
                if len(self.crawled_pages) >= self.max_pages:
                    break
                if link not in self.visited_urls:
                    tasks.append(self.crawl_url(session, link, depth + 1))
                    
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
    async def crawl(self, start_urls: List[str]) -> List[CrawledPage]:
        """
        Start crawling from seed URLs
        
        Args:
            start_urls: List of starting URLs
            
        Returns:
            List of crawled pages
        """
        logger.info(f"Starting crawl with {len(start_urls)} seed URLs")
        
        async with aiohttp.ClientSession() as session:
            tasks = [self.crawl_url(session, url, depth=0) for url in start_urls]
            await asyncio.gather(*tasks, return_exceptions=True)
            
        logger.info(f"Crawl complete. Collected {len(self.crawled_pages)} pages")
        return self.crawled_pages
        

def start_crawl(
    seed_urls: List[str],
    max_depth: int = 3,
    max_pages: int = 100,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    High-level function to start web crawling
    
    Args:
        seed_urls: Starting URLs
        max_depth: Maximum crawl depth
        max_pages: Maximum pages to collect
        **kwargs: Additional crawler options
        
    Returns:
        List of crawled page dictionaries
    """
    crawler = WebCrawler(
        max_depth=max_depth,
        max_pages=max_pages,
        timeout=kwargs.get("timeout", 30)
    )
    
    # Run crawler
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    pages = loop.run_until_complete(crawler.crawl(seed_urls))
    loop.close()
    
    return [page.to_dict() for page in pages]


# Backwards-compatible alias expected by package __init__
def start_crawling(
    seed_urls: List[str],
    max_depth: int = 3,
    max_pages: int = 100,
    **kwargs
) -> List[Dict[str, Any]]:
    """Alias for start_crawl for compatibility with external imports."""
    return start_crawl(seed_urls, max_depth=max_depth, max_pages=max_pages, **kwargs)

