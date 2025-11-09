"""
Celery Tasks for CraftML Studio
Background task processing for long-running operations
"""

import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from celery import Celery
from services.training_service import start_training, update_progress
from services.crawler_service import start_crawler
from services.compression_service import start_compression
from services.deployment_service import start_deployment

# Initialize Celery app
celery_app = Celery(
    'craftml_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600 * 12,  # 12 hours max
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, name='tasks.train_model')
def celery_train_model(self, params: dict):
    """
    Celery task for model training
    
    Args:
        params: Training parameters
        
    Returns:
        Training result
    """
    try:
        # Start training using the service
        job_id = start_training(params)
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'job_id': job_id, 'status': 'training'}
        )
        
        # Note: Actual training happens in the service
        # This task just initiates it
        
        return {
            'status': 'completed',
            'job_id': job_id
        }
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise


@celery_app.task(bind=True, name='tasks.crawl_web')
def celery_crawl_web(self, params: dict):
    """
    Celery task for web crawling
    
    Args:
        params: Crawler parameters
        
    Returns:
        Crawling result
    """
    try:
        # Start crawler using the service
        job_id = start_crawler(params)
        
        self.update_state(
            state='PROGRESS',
            meta={'job_id': job_id, 'status': 'crawling'}
        )
        
        return {
            'status': 'completed',
            'job_id': job_id
        }
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise


@celery_app.task(bind=True, name='tasks.compress_model')
def celery_compress_model(self, params: dict):
    """
    Celery task for model compression
    
    Args:
        params: Compression parameters
        
    Returns:
        Compression result
    """
    try:
        # Start compression using the service
        job_id = start_compression(params)
        
        self.update_state(
            state='PROGRESS',
            meta={'job_id': job_id, 'status': 'compressing'}
        )
        
        return {
            'status': 'completed',
            'job_id': job_id
        }
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise


@celery_app.task(bind=True, name='tasks.deploy_model')
def celery_deploy_model(self, params: dict):
    """
    Celery task for model deployment
    
    Args:
        params: Deployment parameters
        
    Returns:
        Deployment result
    """
    try:
        # Start deployment using the service
        deployment_id = start_deployment(params)
        
        self.update_state(
            state='PROGRESS',
            meta={'deployment_id': deployment_id, 'status': 'deploying'}
        )
        
        return {
            'status': 'completed',
            'deployment_id': deployment_id
        }
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise


# Task routing
celery_app.conf.task_routes = {
    'tasks.train_model': {'queue': 'training'},
    'tasks.crawl_web': {'queue': 'crawler'},
    'tasks.compress_model': {'queue': 'compression'},
    'tasks.deploy_model': {'queue': 'deployment'},
}
