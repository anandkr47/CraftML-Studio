# CraftML Studio - API Reference

Base URL: `http://127.0.0.1:5000`

## Authentication

No authentication required (local-only API).

## Common Response Format

### Success Response
```json
{
  "status": "success",
  "data": { ... }
}
```

### Error Response
```json
{
  "status": "error",
  "message": "Error description",
  "code": "ERROR_CODE"
}
```

## Endpoints

### Health Check

#### GET `/api/health`
Check if backend is running.

**Response:**
```json
{
  "status": "healthy",
  "service": "craftml-backend"
}
```

---

## Crawler API

### Start Crawl

#### POST `/api/crawler/start`
Start a new web crawling job.

**Request Body:**
```json
{
  "seed_urls": ["https://example.com", "https://example.com/docs"],
  "max_depth": 3,
  "max_pages": 100,
  "timeout": 30
}
```

**Response:**
```json
{
  "job_id": "crawl_abc123"
}
```

### Get Crawl Status

#### GET `/api/crawler/status/{job_id}`
Get status of a crawling job.

**Response:**
```json
{
  "job_id": "crawl_abc123",
  "status": "running",
  "progress": {
    "pages_crawled": 45,
    "pages_total": 100,
    "current_url": "https://example.com/page45"
  },
  "started_at": "2025-10-13T10:00:00",
  "estimated_completion": "2025-10-13T10:05:00"
}
```

### Get Crawl Preview

#### GET `/api/crawler/preview/{job_id}`
Preview crawled data.

**Response:**
```json
{
  "pages": [
    {
      "url": "https://example.com",
      "title": "Example Page",
      "content": "Page content...",
      "timestamp": 1697184000,
      "depth": 0
    }
  ],
  "total": 45
}
```

### Stop Crawl

#### POST `/api/crawler/stop/{job_id}`
Stop a running crawl job.

**Response:**
```json
{
  "stopped": true,
  "pages_crawled": 45
}
```

### List Crawl Jobs

#### GET `/api/crawler/jobs`
List all crawler jobs.

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "crawl_abc123",
      "status": "completed",
      "pages_crawled": 100,
      "started_at": "2025-10-13T10:00:00"
    }
  ]
}
```

---

## Training API

### Start Training

#### POST `/api/train/start`
Start model fine-tuning.

**Request Body:**
```json
{
  "model_name": "meta-llama/Llama-2-7b-hf",
  "dataset_path": "./datasets/my_dataset.jsonl",
  "output_dir": "./models/my_model",
  "lora_config": {
    "r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05
  },
  "training_config": {
    "num_epochs": 3,
    "batch_size": 4,
    "learning_rate": 2e-4,
    "use_4bit": true
  }
}
```

**Response:**
```json
{
  "job_id": "train_xyz789"
}
```

### Get Training Status

#### GET `/api/train/status/{job_id}`
Get training job status.

**Response:**
```json
{
  "job_id": "train_xyz789",
  "status": "running",
  "progress": {
    "current_epoch": 2,
    "total_epochs": 3,
    "current_step": 450,
    "total_steps": 600,
    "loss": 0.342,
    "learning_rate": 2e-4
  },
  "metrics": {
    "train_loss": 0.342,
    "gpu_memory_used": 7.2,
    "tokens_per_second": 1250
  },
  "started_at": "2025-10-13T10:00:00",
  "estimated_completion": "2025-10-13T11:30:00"
}
```

### Get Training Logs

#### GET `/api/train/logs/{job_id}`
Get training logs.

**Query Parameters:**
- `limit` (optional): Number of log lines (default: 100)
- `offset` (optional): Log offset (default: 0)

**Response:**
```json
{
  "logs": [
    "[2025-10-13 10:00:00] Starting training...",
    "[2025-10-13 10:00:05] Epoch 1/3",
    "[2025-10-13 10:00:10] Step 10: loss=0.542"
  ],
  "total": 500
}
```

### Stop Training

#### POST `/api/train/stop/{job_id}`
Stop a training job.

**Response:**
```json
{
  "stopped": true,
  "checkpoint_saved": "./models/my_model/checkpoint-450"
}
```

### List Training Jobs

#### GET `/api/train/jobs`
List all training jobs.

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "train_xyz789",
      "model_name": "Llama-2-7b-hf",
      "status": "completed",
      "started_at": "2025-10-13T10:00:00",
      "completed_at": "2025-10-13T11:30:00"
    }
  ]
}
```

### Get Job Counts

#### GET `/api/train/job_counts`
Get training job statistics.

**Response:**
```json
{
  "total": 25,
  "running": 2,
  "completed": 20,
  "failed": 3
}
```

---

## Compression API

### Start Compression

#### POST `/api/compress/start`
Start model compression.

**Request Body:**
```json
{
  "model_path": "./models/my_model",
  "output_path": "./models/my_model_compressed",
  "method": "int4",
  "options": {
    "use_double_quant": true
  }
}
```

**Methods:**
- `int8`: INT8 quantization
- `int4`: INT4 quantization (NF4)
- `gptq`: GPTQ quantization
- `pruning`: Magnitude pruning
- `distillation`: Knowledge distillation

**Response:**
```json
{
  "job_id": "compress_def456"
}
```

### Get Compression Status

#### GET `/api/compress/status/{job_id}`
Get compression status.

**Response:**
```json
{
  "job_id": "compress_def456",
  "status": "completed",
  "result": {
    "original_size_mb": 13500,
    "compressed_size_mb": 3375,
    "compression_ratio": "4.0x",
    "method": "int4"
  }
}
```

---

## Deployment API

### Deploy Locally

#### POST `/api/deploy/local`
Deploy model as local API server.

**Request Body:**
```json
{
  "model_path": "./models/my_model",
  "port": 5001,
  "device": "auto"
}
```

**Response:**
```json
{
  "deployment_id": "deploy_local_123",
  "url": "http://127.0.0.1:5001",
  "endpoints": {
    "generate": "/generate",
    "health": "/health"
  }
}
```

### Deploy to Hugging Face

#### POST `/api/deploy/huggingface`
Upload model to Hugging Face Hub.

**Request Body:**
```json
{
  "model_path": "./models/my_model",
  "repo_name": "username/my-awesome-model",
  "hf_token": "hf_xxxxxxxxxxxxx",
  "private": false
}
```

**Response:**
```json
{
  "repo_url": "https://huggingface.co/username/my-awesome-model",
  "status": "uploaded"
}
```

### List Deployments

#### GET `/api/deploy/list`
List active deployments.

**Response:**
```json
{
  "deployments": [
    {
      "deployment_id": "deploy_local_123",
      "type": "local",
      "url": "http://127.0.0.1:5001",
      "status": "running",
      "model": "my_model"
    }
  ]
}
```

### Stop Deployment

#### POST `/api/deploy/stop/{deployment_id}`
Stop a deployment.

**Response:**
```json
{
  "stopped": true,
  "deployment_id": "deploy_local_123"
}
```

---

## Monitoring API

### Get System Metrics

#### GET `/api/monitor/system`
Get current system metrics.

**Response:**
```json
{
  "cpu": {
    "usage_percent": 45.2,
    "cores": 8,
    "frequency_mhz": 3600
  },
  "memory": {
    "total_gb": 32,
    "used_gb": 18.5,
    "available_gb": 13.5,
    "percent": 57.8
  },
  "disk": {
    "total_gb": 512,
    "used_gb": 256,
    "free_gb": 256,
    "percent": 50.0
  }
}
```

### Get GPU Metrics

#### GET `/api/monitor/gpu`
Get GPU information and metrics.

**Response:**
```json
{
  "gpus": [
    {
      "id": 0,
      "name": "NVIDIA RTX 4090",
      "memory_total_mb": 24576,
      "memory_used_mb": 8192,
      "memory_free_mb": 16384,
      "utilization_percent": 65.0,
      "temperature_c": 72
    }
  ]
}
```

### Get Resource History

#### GET `/api/monitor/history`
Get historical resource metrics.

**Query Parameters:**
- `limit` (optional): Number of data points (default: 60)

**Response:**
```json
{
  "history": [
    {
      "timestamp": 1697184000,
      "cpu_percent": 45.2,
      "memory_percent": 57.8,
      "gpu_percent": 65.0
    }
  ]
}
```

---

## Dataset API

### List Datasets

#### GET `/api/dataset/list`
List all datasets.

**Response:**
```json
{
  "datasets": [
    {
      "dataset_id": "dataset_123",
      "name": "my_dataset",
      "format": "jsonl",
      "size_mb": 125.5,
      "num_samples": 10000,
      "created_at": "2025-10-13T10:00:00"
    }
  ]
}
```

### Upload Dataset

#### POST `/api/dataset/upload`
Upload a dataset file.

**Content-Type:** `multipart/form-data`

**Form Data:**
- `file`: Dataset file

**Response:**
```json
{
  "dataset_id": "dataset_456",
  "filename": "my_dataset.jsonl",
  "size_mb": 125.5
}
```

### Delete Dataset

#### DELETE `/api/dataset/{dataset_id}`
Delete a dataset.

**Response:**
```json
{
  "deleted": true,
  "dataset_id": "dataset_123"
}
```

---

## Model Hub API

### Search Models

#### GET `/api/modelhub/search`
Search for models on Hugging Face.

**Query Parameters:**
- `query`: Search term
- `limit` (optional): Number of results (default: 20)

**Response:**
```json
{
  "models": [
    {
      "model_id": "meta-llama/Llama-2-7b-hf",
      "name": "Llama 2 7B",
      "downloads": 1500000,
      "likes": 5000,
      "tags": ["llama", "causal-lm"]
    }
  ]
}
```

### Download Model

#### POST `/api/modelhub/download`
Download a model from Hugging Face.

**Request Body:**
```json
{
  "model_name": "meta-llama/Llama-2-7b-hf"
}
```

**Response:**
```json
{
  "job_id": "download_ghi789",
  "model_name": "Llama-2-7b-hf"
}
```

### List Local Models

#### GET `/api/modelhub/local`
List locally stored models.

**Response:**
```json
{
  "models": [
    {
      "name": "my_model",
      "path": "./resources/models/my_model",
      "size_mb": 13500,
      "created_at": "2025-10-13T10:00:00"
    }
  ]
}
```

---

## WebSocket API

### Real-time Logs

#### WS `/ws/logs/{job_id}`
Stream real-time logs for a job.

**Message Format:**
```json
{
  "type": "log",
  "timestamp": 1697184000,
  "message": "Step 100: loss=0.342"
}
```

### Real-time Metrics

#### WS `/ws/metrics/{job_id}`
Stream real-time metrics for a job.

**Message Format:**
```json
{
  "type": "metric",
  "timestamp": 1697184000,
  "metrics": {
    "loss": 0.342,
    "gpu_util": 85.5
  }
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| `INVALID_REQUEST` | Request validation failed |
| `JOB_NOT_FOUND` | Job ID not found |
| `MODEL_NOT_FOUND` | Model not found |
| `DATASET_NOT_FOUND` | Dataset not found |
| `DEPLOYMENT_FAILED` | Deployment failed |
| `TRAINING_FAILED` | Training failed |
| `COMPRESSION_FAILED` | Compression failed |
| `OUT_OF_MEMORY` | Insufficient memory |
| `GPU_NOT_AVAILABLE` | No GPU available |
| `INTERNAL_ERROR` | Internal server error |
