"""
Celery Worker for CraftML Studio
Handles background task processing
"""

import sys
from pathlib import Path

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tasks.tasks import celery_app

if __name__ == '__main__':
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=2',
        '--pool=solo' if sys.platform == 'win32' else '--pool=prefork'
    ])
