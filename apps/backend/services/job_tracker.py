"""
Job Tracker for persistent job storage and history
Uses SQLite to track all jobs across sessions
"""

import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class JobTracker:
    """
    Track jobs in a persistent database
    Stores job metadata, status, and history
    """
    
    def __init__(self, db_path: str = "craftml.db"):
        """
        Initialize job tracker
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create jobs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    task_id TEXT,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    params TEXT,
                    result TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    progress REAL DEFAULT 0.0,
                    metadata TEXT
                )
            ''')
            
            # Create job_logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS job_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_job_type ON jobs(job_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_job_status ON jobs(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_job_created ON jobs(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_job_id ON job_logs(job_id)')
            
            conn.commit()
            conn.close()
            
            logger.info("Job tracker database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize job tracker database: {str(e)}")
            raise
    
    def create_job(
        self,
        job_id: str,
        task_id: str,
        job_type: str,
        params: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new job entry
        
        Args:
            job_id: Unique job identifier
            task_id: Celery task ID
            job_type: Type of job (train, crawl, compress, deploy)
            params: Job parameters
            metadata: Optional additional metadata
            
        Returns:
            Created job information
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT INTO jobs (
                    job_id, task_id, job_type, status, params,
                    created_at, updated_at, progress, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job_id,
                task_id,
                job_type,
                'pending',
                json.dumps(params),
                now,
                now,
                0.0,
                json.dumps(metadata or {})
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Job created: {job_id} (type={job_type})")
            
            return {
                'job_id': job_id,
                'task_id': task_id,
                'job_type': job_type,
                'status': 'pending',
                'created_at': now
            }
            
        except Exception as e:
            logger.error(f"Failed to create job {job_id}: {str(e)}")
            raise
    
    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        Update job status and progress
        
        Args:
            job_id: Job identifier
            status: New status
            progress: Progress percentage (0-100)
            result: Job result
            error: Error message if failed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            updates = []
            values = []
            
            if status:
                updates.append("status = ?")
                values.append(status)
                
                if status == 'running' and not self._get_started_at(job_id):
                    updates.append("started_at = ?")
                    values.append(datetime.now().isoformat())
                elif status in ['completed', 'failed', 'cancelled']:
                    updates.append("completed_at = ?")
                    values.append(datetime.now().isoformat())
            
            if progress is not None:
                updates.append("progress = ?")
                values.append(progress)
            
            if result is not None:
                updates.append("result = ?")
                values.append(json.dumps(result))
            
            if error:
                updates.append("error = ?")
                values.append(error)
            
            if updates:
                updates.append("updated_at = ?")
                values.append(datetime.now().isoformat())
                values.append(job_id)
                
                query = f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?"
                cursor.execute(query, values)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {str(e)}")
    
    def _get_started_at(self, job_id: str) -> Optional[str]:
        """Get started_at timestamp for a job"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT started_at FROM jobs WHERE job_id = ?", (job_id,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except:
            return None
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job information
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job information or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                job = dict(row)
                job['params'] = json.loads(job['params']) if job['params'] else {}
                job['result'] = json.loads(job['result']) if job['result'] else None
                job['metadata'] = json.loads(job['metadata']) if job['metadata'] else {}
                return job
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {str(e)}")
            return None
    
    def list_jobs(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List jobs with optional filters
        
        Args:
            job_type: Filter by job type
            status: Filter by status
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of jobs
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM jobs"
            conditions = []
            params = []
            
            if job_type:
                conditions.append("job_type = ?")
                params.append(job_type)
            
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            jobs = []
            for row in rows:
                job = dict(row)
                job['params'] = json.loads(job['params']) if job['params'] else {}
                job['result'] = json.loads(job['result']) if job['result'] else None
                job['metadata'] = json.loads(job['metadata']) if job['metadata'] else {}
                jobs.append(job)
            
            return jobs
            
        except Exception as e:
            logger.error(f"Failed to list jobs: {str(e)}")
            return []
    
    def add_log(self, job_id: str, level: str, message: str):
        """
        Add a log entry for a job
        
        Args:
            job_id: Job identifier
            level: Log level (INFO, WARNING, ERROR)
            message: Log message
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO job_logs (job_id, timestamp, level, message)
                VALUES (?, ?, ?, ?)
            ''', (job_id, datetime.now().isoformat(), level, message))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to add log for job {job_id}: {str(e)}")
    
    def get_logs(self, job_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get logs for a job
        
        Args:
            job_id: Job identifier
            limit: Maximum number of log entries
            
        Returns:
            List of log entries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, level, message
                FROM job_logs
                WHERE job_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (job_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get logs for job {job_id}: {str(e)}")
            return []
    
    def get_job_counts(self) -> Dict[str, int]:
        """
        Get counts of jobs by status
        
        Returns:
            Dictionary of status counts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM jobs
                GROUP BY status
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            counts = {row[0]: row[1] for row in rows}
            
            # Ensure all statuses are present
            for status in ['pending', 'running', 'completed', 'failed', 'cancelled']:
                if status not in counts:
                    counts[status] = 0
            
            counts['total'] = sum(counts.values())
            
            return counts
            
        except Exception as e:
            logger.error(f"Failed to get job counts: {str(e)}")
            return {}
    
    def delete_job(self, job_id: str):
        """
        Delete a job and its logs
        
        Args:
            job_id: Job identifier
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM job_logs WHERE job_id = ?", (job_id,))
            cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Job deleted: {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {str(e)}")


# Global job tracker instance
job_tracker = JobTracker()

