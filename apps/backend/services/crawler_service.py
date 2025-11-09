"""
Crawler Service
Handles web crawling jobs using core data modules
"""

import sys
from pathlib import Path
import uuid
import logging
from typing import Dict, Any, List
from datetime import datetime
import asyncio

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.data.crawler import start_crawl, crawl_with_playwright, filter_crawled_pages
from core.data.cleaner import clean_crawled_data
from core.data.formatter import DatasetFormatter
from core.utils import setup_logger
from services.dedup_service import deduplicate_with_faiss

logger = setup_logger("crawler_service", log_file="logs/crawler_service.log")

# In-memory job storage
active_jobs: Dict[str, Dict[str, Any]] = {}
crawled_data: Dict[str, List[Dict[str, Any]]] = {}


def start_crawler(params: Dict[str, Any]) -> str:
    """
    Start a new crawling job (returns immediately, job runs in background)
    
    Args:
        params: Crawling parameters including:
            - seed_urls: List of starting URLs
            - max_depth: Maximum crawl depth (default: 3)
            - max_pages: Maximum pages to collect (default: 100)
            - timeout: Request timeout in seconds (default: 30)
            
    Returns:
        job_id: Unique job identifier
    """
    job_id = f"crawl_{uuid.uuid4().hex[:8]}"
    
    logger.info(f"Starting crawler job {job_id} with params: {params}")
    
    # Validate parameters
    seed_urls = params.get("seed_urls", [])
    if not seed_urls:
        raise ValueError("seed_urls is required")
    
    max_depth = params.get("max_depth", 3)
    max_pages = params.get("max_pages", 100)
    timeout = params.get("timeout", 30)
    
    # Store job info
    active_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "params": params,
        "started_at": datetime.now().isoformat(),
        "progress": {
            "pages_crawled": 0,
            "pages_total": max_pages,
            "current_url": None
        }
    }
    
    # Start crawling in background thread (non-blocking)
    import threading
    thread = threading.Thread(target=_run_crawler_job, args=(job_id, params))
    thread.daemon = True
    thread.start()
    
    return job_id


def _run_crawler_job(job_id: str, params: Dict[str, Any]):
    """
    Internal function to run crawler job in background thread
    """
    try:
        active_jobs[job_id]["status"] = "running"
        active_jobs[job_id]["batches"] = []
        
        # Extract parameters
        seed_urls = params.get("seed_urls", [])
        max_depth = params.get("max_depth", 3)
        max_pages = params.get("max_pages", 100)
        timeout = params.get("timeout", 30)
        batch_size = params.get("batch_size", 20)  # Process in batches of 20 pages
        use_playwright = params.get("use_playwright", False)  # Enable Playwright for JS pages
        query = params.get("query", None)  # For AI filtering
        ai_filter = params.get("ai_filter", False)  # Enable AI-based filtering
        use_faiss = params.get("use_faiss", False)  # Use FAISS for deduplication
        
        # Run crawler
        logger.info(f"Crawling {len(seed_urls)} seed URLs in batches of {batch_size}...")
        logger.info(f"Playwright: {use_playwright}, AI Filter: {ai_filter}, FAISS: {use_faiss}")
        
        if use_playwright:
            # Use Playwright for JavaScript-rendered pages
            logger.info("Using Playwright crawler for JavaScript support")
            # Running in background thread, safe to use asyncio.run
            pages = asyncio.run(crawl_with_playwright(
                seed_urls=seed_urls,
                max_depth=max_depth,
                max_pages=max_pages,
                query=query,
                timeout=timeout,
                headless=params.get("headless", True)
            ))
        else:
            # Use standard aiohttp crawler
            pages = start_crawl(
                seed_urls=seed_urls,
                max_depth=max_depth,
                max_pages=max_pages,
                timeout=timeout
            )
        
        # Apply AI filtering if enabled
        if ai_filter and query:
            logger.info(f"Applying AI filtering with query: {query}")
            pages = filter_crawled_pages(
                pages=pages,
                query=query,
                threshold=params.get("relevance_threshold", 0.3),
                top_k=params.get("top_k", None)
            )
        
        # Process data in batches
        all_cleaned_pages = []
        total_batches = (len(pages) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(pages))
            batch_pages = pages[start_idx:end_idx]
            
            # Clean batch
            logger.info(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_pages)} pages)...")
            cleaned_batch = clean_crawled_data(batch_pages)
            
            # Apply FAISS deduplication if enabled
            if use_faiss and len(cleaned_batch) > 10:
                logger.info("Applying FAISS deduplication to batch")
                texts = [page.get("content", "") for page in cleaned_batch]
                unique_texts = deduplicate_with_faiss(texts, threshold=0.9)
                unique_texts_set = set(unique_texts)
                cleaned_batch = [p for p in cleaned_batch if p.get("content", "") in unique_texts_set]
                logger.info(f"FAISS dedup: {len(batch_pages)} -> {len(cleaned_batch)} pages")
            
            all_cleaned_pages.extend(cleaned_batch)
            
            # Store batch info
            batch_info = {
                "batch_number": batch_num + 1,
                "total_batches": total_batches,
                "pages_in_batch": len(cleaned_batch),
                "processed_at": datetime.now().isoformat()
            }
            active_jobs[job_id]["batches"].append(batch_info)
            
            # Update progress
            active_jobs[job_id]["progress"]["pages_crawled"] = len(all_cleaned_pages)
            active_jobs[job_id]["progress"]["current_batch"] = batch_num + 1
            active_jobs[job_id]["progress"]["total_batches"] = total_batches
            
            logger.info(f"Batch {batch_num + 1}/{total_batches} complete: {len(cleaned_batch)} pages")
        
        # Store final results
        crawled_data[job_id] = all_cleaned_pages
        
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        active_jobs[job_id]["progress"]["pages_crawled"] = len(all_cleaned_pages)
        
        logger.info(f"Crawler job {job_id} completed: {len(all_cleaned_pages)} pages in {total_batches} batches")
        
    except Exception as e:
        logger.error(f"Crawler job {job_id} failed: {e}")
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
    
    return job_id


def stop_crawler(job_id: str) -> bool:
    """
    Stop a running crawler job
    
    Args:
        job_id: Job identifier
        
    Returns:
        True if stopped successfully
    """
    if job_id not in active_jobs:
        logger.warning(f"Job {job_id} not found")
        return False
        
    logger.info(f"Stopping crawler job {job_id}")
    
    active_jobs[job_id]["status"] = "cancelled"
    active_jobs[job_id]["stopped_at"] = datetime.now().isoformat()
    
    # Note: Crawler runs to completion due to async nature
    # Status is set to cancelled to prevent further processing
    
    return True


def get_status(job_id: str) -> Dict[str, Any]:
    """
    Get crawler job status
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job status information
    """
    if job_id not in active_jobs:
        return {
            "job_id": job_id,
            "status": "not_found",
            "error": "Job not found"
        }
    
    return active_jobs[job_id]


def get_preview(job_id: str, limit: int = 10) -> Dict[str, Any]:
    """
    Get preview of crawled data
    
    Args:
        job_id: Job identifier
        limit: Number of pages to preview
        
    Returns:
        Preview data
    """
    if job_id not in crawled_data:
        return {
            "job_id": job_id,
            "pages": [],
            "total": 0
        }
    
    pages = crawled_data[job_id]
    
    return {
        "job_id": job_id,
        "pages": pages[:limit],
        "total": len(pages)
    }


def save_dataset(
    job_id: str,
    output_path: str,
    format_type: str = "jsonl"
) -> Dict[str, Any]:
    """
    Save crawled data as a dataset
    
    Args:
        job_id: Job identifier
        output_path: Where to save the dataset
        format_type: Dataset format (jsonl, csv, text, instruction)
        
    Returns:
        Save result information
    """
    if job_id not in crawled_data:
        raise ValueError(f"No data found for job {job_id}")
    
    pages = crawled_data[job_id]
    
    logger.info(f"Saving {len(pages)} pages to {output_path} as {format_type}")
    
    formatter = DatasetFormatter(output_dir=str(Path(output_path).parent))
    
    saved_path = formatter.crawled_to_training_format(
        crawled_pages=pages,
        format_type=format_type,
        filename=Path(output_path).name
    )
    
    logger.info(f"Dataset saved to {saved_path}")
    
    return {
        "job_id": job_id,
        "output_path": saved_path,
        "format": format_type,
        "num_samples": len(pages)
    }


def list_jobs() -> Dict[str, Any]:
    """
    List all crawler jobs
    
    Returns:
        List of jobs with summary information
    """
    jobs = []
    
    for job_id, job_data in active_jobs.items():
        jobs.append({
            "job_id": job_id,
            "status": job_data.get("status"),
            "started_at": job_data.get("started_at"),
            "pages_crawled": job_data.get("progress", {}).get("pages_crawled", 0),
        })
    
    return {"jobs": jobs}
