# Crawler Async Fix 🔧

Fixed the "Cannot run the event loop while another loop is running" error in the crawler service.

## Problem

The crawler service was trying to run `asyncio.run()` inside an already running async context (FastAPI), which caused:
```
RuntimeError: Cannot run the event loop while another loop is running
RuntimeWarning: coroutine 'WebCrawler.crawl' was never awaited
```

## Root Cause

The `start_crawler()` function was:
1. Being called from a FastAPI async endpoint
2. Trying to use `asyncio.run()` for Playwright crawler
3. Doing all the crawling work synchronously in the request handler (blocking)

This violated async best practices and blocked the web server.

## Solution

### 1. **Background Thread Execution**
Moved the heavy crawling work to a background thread:

```python
def start_crawler(params: Dict[str, Any]) -> str:
    # Quick validation and job setup
    job_id = f"crawl_{uuid.uuid4().hex[:8]}"
    active_jobs[job_id] = {...}
    
    # Start crawling in background thread (non-blocking)
    thread = threading.Thread(target=_run_crawler_job, args=(job_id, params))
    thread.daemon = True
    thread.start()
    
    return job_id  # Returns immediately!
```

### 2. **Separate Worker Function**
Created `_run_crawler_job()` to run in background:

```python
def _run_crawler_job(job_id: str, params: Dict[str, Any]):
    """
    Internal function to run crawler job in background thread
    """
    try:
        # All the heavy work happens here
        pages = asyncio.run(crawl_with_playwright(...))  # Safe in background thread!
        # Process batches...
        # Clean data...
        # Save results...
    except Exception as e:
        logger.error(f"Crawler job {job_id} failed: {e}")
        active_jobs[job_id]["status"] = "failed"
```

### 3. **Async Event Loop**
Now `asyncio.run()` works correctly because:
- It's running in a dedicated background thread
- No conflicting event loops
- FastAPI remains responsive

## Benefits

✅ **Non-Blocking**: API returns immediately with job_id  
✅ **No Event Loop Conflicts**: Background thread has its own event loop  
✅ **Proper Async**: Playwright and aiohttp work correctly  
✅ **Scalable**: Multiple crawl jobs can run concurrently  
✅ **Responsive**: FastAPI server never blocks  

## Flow

```
User → POST /api/crawler/start
  ↓
FastAPI Endpoint (async)
  ↓
start_crawler() - Returns job_id immediately
  ↓
Background Thread spawned → _run_crawler_job()
  ↓
FastAPI returns 200 OK with job_id
  ↓
(Meanwhile, in background)
  ↓
Crawler runs → Updates job status
  ↓
User polls GET /api/crawler/status/{job_id}
```

## Testing

To test the fix:
1. Start backend: `python apps/backend/main.py`
2. Go to Crawler Manager in frontend
3. Enter URL: `https://docs.python.org/3/`
4. Set depth: 2, max pages: 100
5. Click "Start Crawl"
6. Should see "Crawl job started" notification
7. Job runs in background, status updates in real-time

## Technical Details

- **Thread Safety**: Job status stored in dictionary with thread-safe updates
- **Daemon Threads**: Auto-cleanup when app shuts down
- **Error Handling**: Exceptions caught and logged, job status updated
- **Memory Management**: Crawled data stored per job_id

The crawler now works correctly with async/await patterns! 🚀

