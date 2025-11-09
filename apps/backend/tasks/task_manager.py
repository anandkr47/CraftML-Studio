"""
Task Manager for Celery Task Orchestration
Provides unified interface for managing async tasks with Job IDs
"""

import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from celery.result import AsyncResult
from tasks.tasks import celery_app
import logging

logger = logging.getLogger(__name__)


class TaskManager:
    """
    Unified task manager for all Celery tasks
    Provides job tracking, status checking, and result retrieval
    """
    
    def __init__(self):
        self.app = celery_app
    
    def create_job_id(self, prefix: str) -> str:
        """
        Create a unique job ID
        
        Args:
            prefix: Job type prefix (train, crawl, compress, deploy)
            
        Returns:
            Unique job ID
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{unique_id}"
    
    def submit_task(
        self,
        task_name: str,
        params: Dict[str, Any],
        job_id: Optional[str] = None,
        queue: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit a task to Celery
        
        Args:
            task_name: Name of the Celery task
            params: Task parameters
            job_id: Optional custom job ID
            queue: Optional queue name
            
        Returns:
            Task submission result with job_id and task_id
        """
        try:
            # Generate job ID if not provided
            if not job_id:
                prefix = task_name.split('.')[-1].replace('_', '')
                job_id = self.create_job_id(prefix)
            
            # Add job_id to params
            params['job_id'] = job_id
            
            # Submit task to Celery
            task_kwargs = {'task_id': job_id}
            if queue:
                task_kwargs['queue'] = queue
            
            result = self.app.send_task(
                task_name,
                args=[params],
                **task_kwargs
            )
            
            logger.info(f"Task submitted: {task_name} with job_id={job_id}, task_id={result.id}")
            
            return {
                'job_id': job_id,
                'task_id': result.id,
                'status': 'pending',
                'task_name': task_name,
                'submitted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to submit task {task_name}: {str(e)}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a Celery task
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Task status information
        """
        try:
            result = AsyncResult(task_id, app=self.app)
            
            status_info = {
                'task_id': task_id,
                'state': result.state,
                'status': self._map_celery_state(result.state),
                'info': {}
            }
            
            if result.state == 'PENDING':
                status_info['info'] = {
                    'message': 'Task is waiting to be executed'
                }
            elif result.state == 'STARTED':
                status_info['info'] = result.info or {'message': 'Task has started'}
            elif result.state == 'PROGRESS':
                status_info['info'] = result.info or {}
            elif result.state == 'SUCCESS':
                status_info['info'] = result.result or {}
                status_info['result'] = result.result
            elif result.state == 'FAILURE':
                status_info['info'] = {
                    'error': str(result.info),
                    'traceback': result.traceback
                }
                status_info['error'] = str(result.info)
            elif result.state == 'RETRY':
                status_info['info'] = {
                    'message': 'Task is being retried',
                    'retries': result.info.get('retries', 0) if result.info else 0
                }
            elif result.state == 'REVOKED':
                status_info['info'] = {
                    'message': 'Task was cancelled'
                }
            else:
                status_info['info'] = result.info or {}
            
            return status_info
            
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {str(e)}")
            return {
                'task_id': task_id,
                'state': 'UNKNOWN',
                'status': 'unknown',
                'error': str(e)
            }
    
    def _map_celery_state(self, state: str) -> str:
        """
        Map Celery state to friendly status
        
        Args:
            state: Celery task state
            
        Returns:
            Friendly status string
        """
        mapping = {
            'PENDING': 'pending',
            'STARTED': 'running',
            'PROGRESS': 'running',
            'SUCCESS': 'completed',
            'FAILURE': 'failed',
            'RETRY': 'retrying',
            'REVOKED': 'cancelled'
        }
        return mapping.get(state, state.lower())
    
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a running task
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Cancellation result
        """
        try:
            result = AsyncResult(task_id, app=self.app)
            result.revoke(terminate=True, signal='SIGKILL')
            
            logger.info(f"Task cancelled: {task_id}")
            
            return {
                'task_id': task_id,
                'status': 'cancelled',
                'message': 'Task has been cancelled'
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {str(e)}")
            raise
    
    def get_task_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """
        Get result of a completed task
        
        Args:
            task_id: Celery task ID
            timeout: Optional timeout in seconds
            
        Returns:
            Task result
        """
        try:
            result = AsyncResult(task_id, app=self.app)
            
            if timeout:
                return result.get(timeout=timeout)
            else:
                return result.result if result.ready() else None
                
        except Exception as e:
            logger.error(f"Failed to get task result for {task_id}: {str(e)}")
            raise
    
    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """
        List all active tasks
        
        Returns:
            List of active task information
        """
        try:
            # Get active tasks from Celery
            inspect = self.app.control.inspect()
            
            active_tasks = []
            
            # Get active tasks
            active = inspect.active()
            if active:
                for worker, tasks in active.items():
                    for task in tasks:
                        active_tasks.append({
                            'task_id': task['id'],
                            'task_name': task['name'],
                            'worker': worker,
                            'status': 'running',
                            'args': task.get('args', []),
                            'kwargs': task.get('kwargs', {})
                        })
            
            # Get reserved tasks
            reserved = inspect.reserved()
            if reserved:
                for worker, tasks in reserved.items():
                    for task in tasks:
                        active_tasks.append({
                            'task_id': task['id'],
                            'task_name': task['name'],
                            'worker': worker,
                            'status': 'pending',
                            'args': task.get('args', []),
                            'kwargs': task.get('kwargs', {})
                        })
            
            return active_tasks
            
        except Exception as e:
            logger.error(f"Failed to list active tasks: {str(e)}")
            return []
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """
        Get Celery worker statistics
        
        Returns:
            Worker statistics
        """
        try:
            inspect = self.app.control.inspect()
            
            stats = {
                'workers': {},
                'queues': {},
                'total_workers': 0,
                'total_active_tasks': 0
            }
            
            # Get worker stats
            worker_stats = inspect.stats()
            if worker_stats:
                stats['workers'] = worker_stats
                stats['total_workers'] = len(worker_stats)
            
            # Get active tasks count
            active = inspect.active()
            if active:
                for worker, tasks in active.items():
                    stats['total_active_tasks'] += len(tasks)
            
            # Get queue info
            active_queues = inspect.active_queues()
            if active_queues:
                stats['queues'] = active_queues
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get worker stats: {str(e)}")
            return {
                'error': str(e),
                'workers': {},
                'queues': {},
                'total_workers': 0,
                'total_active_tasks': 0
            }
    
    def purge_queue(self, queue_name: str = None) -> int:
        """
        Purge tasks from a queue
        
        Args:
            queue_name: Queue to purge (None = all queues)
            
        Returns:
            Number of tasks purged
        """
        try:
            if queue_name:
                result = self.app.control.purge()
            else:
                result = self.app.control.purge()
            
            logger.info(f"Purged {result} tasks from queue")
            return result
            
        except Exception as e:
            logger.error(f"Failed to purge queue: {str(e)}")
            raise


# Global task manager instance
task_manager = TaskManager()

