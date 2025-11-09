# 🎯 Task Orchestration Guide

**CraftML Studio Task Orchestration**  
*Celery + Redis for async task management with job tracking*

---

## 📋 Overview

CraftML Studio uses **Celery** + **Redis** for managing long-running async tasks:
- **Training** - Model fine-tuning jobs
- **Crawling** - Web data collection
- **Compression** - Model quantization/pruning/distillation
- **Deployment** - Model deployment to various platforms

Each task gets a **unique Job ID** that's accessible via the UI and API.

---

## 🏗️ Architecture

```
┌─────────────┐
│   Frontend  │
│   (React)   │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────────────┐
│   FastAPI Backend   │
│  ┌───────────────┐  │
│  │ Task Manager  │  │
│  └───────┬───────┘  │
└──────────┼──────────┘
           │ Submit Task
           ▼
    ┌─────────────┐
    │   Celery    │◄──┐
    │   Worker    │   │ Task Queue
    └─────────────┘   │
           │          │
           │    ┌─────────────┐
           │    │    Redis    │
           │    │   (Broker)  │
           │    └─────────────┘
           │          │
           ▼          │
    ┌─────────────┐  │
    │  Job Store  │  │ Result Backend
    │  (SQLite)   │◄─┘
    └─────────────┘
```

---

## 🎯 Core Components

### 1. Task Manager (`tasks/task_manager.py`)
- Creates unique job IDs
- Submits tasks to Celery
- Tracks task status
- Cancels running tasks
- Queries worker statistics

### 2. Job Tracker (`services/job_tracker.py`)
- Persistent job storage (SQLite)
- Job history across sessions
- Log storage per job
- Status and progress tracking

### 3. Celery Tasks (`tasks/tasks.py`)
- `celery_train_model` - Training tasks
- `celery_crawl_web` - Crawler tasks
- `celery_compress_model` - Compression tasks
- `celery_deploy_model` - Deployment tasks

### 4. API Endpoints
- `/api/tasks/*` - Task orchestration
- `/api/jobs/*` - Job history and tracking

---

## 💻 API Reference

### Task Orchestration Endpoints

#### Get Task Status
```http
GET /api/tasks/status/{task_id}
```

**Response:**
```json
{
  "task_id": "train_20231014_123456_abc123",
  "state": "PROGRESS",
  "status": "running",
  "info": {
    "progress": 45.5,
    "current_epoch": 2,
    "total_epochs": 3
  }
}
```

#### Cancel Task
```http
POST /api/tasks/cancel/{task_id}
```

**Response:**
```json
{
  "task_id": "train_20231014_123456_abc123",
  "status": "cancelled",
  "message": "Task has been cancelled"
}
```

#### List Active Tasks
```http
GET /api/tasks/active
```

**Response:**
```json
{
  "tasks": [
    {
      "task_id": "train_20231014_123456_abc123",
      "task_name": "tasks.train_model",
      "worker": "celery@worker1",
      "status": "running"
    }
  ],
  "total": 1
}
```

#### Worker Statistics
```http
GET /api/tasks/workers
```

**Response:**
```json
{
  "workers": {
    "celery@worker1": {
      "pool": "solo",
      "max-concurrency": 2
    }
  },
  "total_workers": 1,
  "total_active_tasks": 3
}
```

#### Health Check
```http
GET /api/tasks/health
```

**Response:**
```json
{
  "status": "healthy",
  "workers": 1,
  "active_tasks": 3,
  "message": "Task system is operational"
}
```

---

### Job History Endpoints

#### Get Job History
```http
GET /api/jobs/history?job_type=train&status=completed&limit=50
```

**Query Parameters:**
- `job_type` - Filter by type (train, crawl, compress, deploy)
- `status` - Filter by status (pending, running, completed, failed)
- `limit` - Max results (default: 100)
- `offset` - Pagination offset (default: 0)

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "train_20231014_123456_abc123",
      "task_id": "train_20231014_123456_abc123",
      "job_type": "train",
      "status": "completed",
      "progress": 100.0,
      "created_at": "2023-10-14T12:34:56",
      "completed_at": "2023-10-14T13:45:00",
      "params": {...},
      "result": {...}
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### Get Job Details
```http
GET /api/jobs/{job_id}
```

**Response:**
```json
{
  "job_id": "train_20231014_123456_abc123",
  "task_id": "train_20231014_123456_abc123",
  "job_type": "train",
  "status": "completed",
  "progress": 100.0,
  "created_at": "2023-10-14T12:34:56",
  "started_at": "2023-10-14T12:35:00",
  "completed_at": "2023-10-14T13:45:00",
  "params": {
    "model_name": "meta-llama/Llama-2-7b-hf",
    "dataset_path": "resources/datasets/my_dataset.jsonl"
  },
  "result": {
    "model_path": "resources/models/llama2-7b-finetuned",
    "final_loss": 0.234
  }
}
```

#### Get Job Logs
```http
GET /api/jobs/{job_id}/logs?limit=1000
```

**Response:**
```json
{
  "job_id": "train_20231014_123456_abc123",
  "logs": [
    {
      "timestamp": "2023-10-14T12:35:00",
      "level": "INFO",
      "message": "Starting training..."
    },
    {
      "timestamp": "2023-10-14T12:35:30",
      "level": "INFO",
      "message": "Epoch 1/3 - Loss: 0.45"
    }
  ],
  "total": 2
}
```

#### Job Count Statistics
```http
GET /api/jobs/stats/counts
```

**Response:**
```json
{
  "pending": 5,
  "running": 2,
  "completed": 123,
  "failed": 3,
  "cancelled": 1,
  "total": 134
}
```

#### Delete Job
```http
DELETE /api/jobs/{job_id}
```

**Response:**
```json
{
  "status": "success",
  "message": "Job train_20231014_123456_abc123 deleted successfully"
}
```

---

## 🚀 Usage Examples

### Starting a Training Job

**1. Submit via API:**
```bash
curl -X POST http://localhost:5000/api/train/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "meta-llama/Llama-2-7b-hf",
    "dataset_path": "resources/datasets/my_dataset.jsonl"
  }'
```

**Response:**
```json
{
  "job_id": "train_20231014_123456_abc123",
  "status": "pending",
  "message": "Training job created successfully"
}
```

**2. Track Progress:**
```bash
# Via task status
curl http://localhost:5000/api/tasks/status/train_20231014_123456_abc123

# Via job details
curl http://localhost:5000/api/jobs/train_20231014_123456_abc123
```

**3. View Logs:**
```bash
curl http://localhost:5000/api/jobs/train_20231014_123456_abc123/logs
```

**4. Cancel if Needed:**
```bash
curl -X POST http://localhost:5000/api/tasks/cancel/train_20231014_123456_abc123
```

---

### Frontend Integration

**React Hook for Task Tracking:**
```typescript
import { useState, useEffect } from 'react';
import api from './api/apiClient';

export function useTaskStatus(taskId: string) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!taskId) return;

    const interval = setInterval(async () => {
      try {
        const response = await api.get(`/tasks/status/${taskId}`);
        setStatus(response.data);
        
        // Stop polling if task is done
        if (['completed', 'failed', 'cancelled'].includes(response.data.status)) {
          clearInterval(interval);
        }
      } catch (error) {
        console.error('Failed to fetch task status:', error);
      } finally {
        setLoading(false);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [taskId]);

  return { status, loading };
}
```

**Usage in Component:**
```tsx
function TrainingDashboard() {
  const [jobId, setJobId] = useState(null);
  const { status, loading } = useTaskStatus(jobId);

  const startTraining = async () => {
    const response = await api.post('/train/start', {...params});
    setJobId(response.data.job_id);
  };

  return (
    <div>
      {status && (
        <div>
          <h3>Job: {status.task_id}</h3>
          <p>Status: {status.status}</p>
          <p>Progress: {status.info.progress}%</p>
        </div>
      )}
    </div>
  );
}
```

---

## 🔧 Setup & Configuration

### 1. Install Dependencies
```bash
cd apps/backend
pip install celery redis
```

### 2. Start Redis
```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or using docker-compose
docker-compose up -d redis
```

### 3. Start Celery Worker
```bash
cd apps/backend
python worker.py
```

### 4. Start FastAPI Backend
```bash
cd apps/backend
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

---

## 📊 Job ID Format

Job IDs follow a consistent pattern:

```
{type}_{timestamp}_{unique_id}

Examples:
- train_20231014_123456_abc123
- crawl_20231014_140000_def456
- compress_20231014_150000_ghi789
- deploy_20231014_160000_jkl012
```

**Components:**
- `type`: Job type (train, crawl, compress, deploy)
- `timestamp`: YYYYMMDD_HHMMSS format
- `unique_id`: 8-character UUID

---

## 🎯 Task States

| Celery State | Status | Description |
|--------------|--------|-------------|
| PENDING | pending | Task is waiting to start |
| STARTED | running | Task has begun execution |
| PROGRESS | running | Task is in progress |
| SUCCESS | completed | Task completed successfully |
| FAILURE | failed | Task failed with error |
| RETRY | retrying | Task is being retried |
| REVOKED | cancelled | Task was cancelled |

---

## 📈 Monitoring

### Check System Health
```bash
curl http://localhost:5000/api/tasks/health
```

### View Active Tasks
```bash
curl http://localhost:5000/api/tasks/active
```

### Worker Statistics
```bash
curl http://localhost:5000/api/tasks/workers
```

### Job Statistics
```bash
curl http://localhost:5000/api/jobs/stats/counts
```

---

## 🎓 Best Practices

### 1. **Always Use Job IDs**
- Store job IDs returned from API
- Use them to track progress
- Display in UI for user reference

### 2. **Poll Task Status**
- Frontend should poll every 2-3 seconds
- Stop polling when task completes
- Use WebSocket for real-time updates (optional)

### 3. **Handle Failures Gracefully**
- Check task state before acting
- Display error messages to users
- Provide retry options

### 4. **Clean Up Old Jobs**
- Periodically delete old completed jobs
- Keep failed jobs for debugging
- Archive important results

### 5. **Monitor Workers**
- Ensure workers are running
- Check health endpoint
- Alert if no workers available

---

## 🚨 Troubleshooting

### No Workers Available
```bash
# Check if Redis is running
redis-cli ping

# Start Celery worker
cd apps/backend
python worker.py
```

### Task Stuck in PENDING
```bash
# Check worker status
curl http://localhost:5000/api/tasks/workers

# Restart worker if needed
```

### Task Failed
```bash
# Get job details
curl http://localhost:5000/api/jobs/{job_id}

# Check logs
curl http://localhost:5000/api/jobs/{job_id}/logs
```

---

## ✅ Summary

CraftML Studio's Task Orchestration provides:

- ✅ **Unique Job IDs** for all async tasks
- ✅ **Celery + Redis** for reliable task execution
- ✅ **Persistent job tracking** with SQLite
- ✅ **RESTful API** for task management
- ✅ **Job history** across sessions
- ✅ **Real-time status** updates
- ✅ **Worker monitoring** and health checks

**All tasks are accessible via UI with full tracking and history!**

---

**Documentation:** Complete  
**Status:** Production Ready 🚀

