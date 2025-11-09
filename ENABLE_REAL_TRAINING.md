# 🚀 Enable Real Training - Implementation Guide

## 🎭 **Current State: MOCK Training**

The training service is currently a **mock/placeholder**. It:
- ✅ Creates job records
- ✅ Generates logs
- ✅ Tracks status
- ❌ **Does NOT actually train models**

The actual training code is commented out in `apps/backend/services/training_service.py`:

```python
# Lines 100-105 (Training from scratch)
# TODO: Run this in background with Celery
# For now, we just prepare the job
# result = train_from_scratch(...)  # <- COMMENTED OUT

# Lines 114-116 (Fine-tuning)
# TODO: Run this in background with Celery
# result = start_lora_training(job_id, params)  # <- COMMENTED OUT
```

---

## 🔧 **How to Enable REAL Training**

### **Option 1: Quick Enable (Without Celery)**

For development/testing, you can enable training directly in the API request (blocking):

```python
# In apps/backend/services/training_service.py

def start_training(params: Dict[str, Any]) -> str:
    # ... existing code ...
    
    try:
        active_jobs[job_id]["status"] = "running"
        _add_log(job_id, f"Training job {job_id} started")
        
        train_from_scratch_flag = params.get('train_from_scratch', False)
        
        if train_from_scratch_flag:
            model_type = params.get('model_type')
            _add_log(job_id, f"Training {model_type} from scratch")
            
            # UNCOMMENT AND RUN REAL TRAINING
            result = train_from_scratch(
                model_type=model_type,
                dataset_path=params['dataset_path'],
                output_dir=params.get('output_dir', f'models/{job_id}'),
                config=params
            )
            
            active_jobs[job_id]["status"] = "completed"
            active_jobs[job_id]["model_path"] = result.get("model_path")
            _add_log(job_id, "Training completed successfully!")
            
        else:
            _add_log(job_id, f"Model: {params.get('model_name')}")
            
            # UNCOMMENT AND RUN REAL TRAINING
            result = start_lora_training(job_id, params)
            
            active_jobs[job_id]["status"] = "completed"
            active_jobs[job_id]["model_path"] = result.get("output_dir")
            _add_log(job_id, "Fine-tuning completed successfully!")
```

**⚠️ Warning:** This approach blocks the API request until training completes (could be hours).

---

### **Option 2: Background Training (With Threading)**

Run training in a background thread (better for development):

```python
import threading

def start_training(params: Dict[str, Any]) -> str:
    job_id = f"train_{uuid.uuid4().hex[:8]}"
    
    # ... existing setup code ...
    
    # Start training in background thread
    def _run_training():
        try:
            active_jobs[job_id]["status"] = "running"
            _add_log(job_id, f"Training job {job_id} started")
            
            train_from_scratch_flag = params.get('train_from_scratch', False)
            
            if train_from_scratch_flag:
                result = train_from_scratch(
                    model_type=params.get('model_type'),
                    dataset_path=params['dataset_path'],
                    output_dir=params.get('output_dir', f'models/{job_id}'),
                    config=params
                )
            else:
                result = start_lora_training(job_id, params)
            
            active_jobs[job_id]["status"] = "completed"
            active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
            active_jobs[job_id]["model_path"] = result.get("output_dir")
            _add_log(job_id, "Training completed successfully!")
            
        except Exception as e:
            logger.error(f"Training job {job_id} failed: {e}")
            active_jobs[job_id]["status"] = "failed"
            active_jobs[job_id]["error"] = str(e)
            _add_log(job_id, f"ERROR: {str(e)}")
    
    # Start background thread
    thread = threading.Thread(target=_run_training, daemon=True)
    thread.start()
    
    return job_id
```

**Benefits:**
- ✅ Non-blocking API
- ✅ Real training happens
- ✅ No additional setup needed
- ⚠️ Jobs lost if server restarts

---

### **Option 3: Production Ready (With Celery)**

Use Celery for robust background task processing:

**1. Create Celery Task:**

```python
# apps/backend/tasks/training_tasks.py

from celery import Celery
from services.training import train_from_scratch
from core.ml.training import start_lora_training

celery_app = Celery('craftml', broker='redis://localhost:6379/0')

@celery_app.task(bind=True)
def run_training_task(self, job_id: str, params: dict):
    """Background training task"""
    from services.training_service import active_jobs, _add_log
    
    try:
        active_jobs[job_id]["status"] = "running"
        _add_log(job_id, "Training started")
        
        if params.get('train_from_scratch'):
            result = train_from_scratch(
                model_type=params['model_type'],
                dataset_path=params['dataset_path'],
                output_dir=params.get('output_dir', f'models/{job_id}'),
                config=params
            )
        else:
            result = start_lora_training(job_id, params)
        
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["model_path"] = result.get("output_dir")
        _add_log(job_id, "Training completed!")
        
    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)
        _add_log(job_id, f"ERROR: {str(e)}")
```

**2. Update Service:**

```python
# apps/backend/services/training_service.py

from tasks.training_tasks import run_training_task

def start_training(params: Dict[str, Any]) -> str:
    job_id = f"train_{uuid.uuid4().hex[:8]}"
    
    # ... existing setup ...
    
    # Queue Celery task
    run_training_task.delay(job_id, params)
    
    return job_id
```

**3. Start Celery Worker:**

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery Worker
cd apps/backend
celery -A tasks.training_tasks worker --loglevel=info
```

**Benefits:**
- ✅ Production-ready
- ✅ Persistent task queue
- ✅ Retry logic
- ✅ Distributed workers
- ✅ Monitoring tools

---

## 📋 **Prerequisites for Real Training**

### **1. Hardware Requirements:**
- **GPU**: NVIDIA GPU with CUDA support (8GB+ VRAM recommended)
- **RAM**: 16GB+ system RAM
- **Storage**: 50GB+ free space for models and datasets

### **2. Software Requirements:**
```bash
# CUDA Toolkit (for NVIDIA GPUs)
# Download from: https://developer.nvidia.com/cuda-downloads

# PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Training dependencies
pip install transformers>=4.30.0
pip install peft>=0.4.0
pip install accelerate>=0.20.0
pip install bitsandbytes>=0.40.0
pip install datasets>=2.12.0
```

### **3. Model and Dataset:**
- Valid HuggingFace model name (e.g., "meta-llama/Llama-3-8B")
- Properly formatted dataset (JSONL, JSON, CSV, or TXT)
- HuggingFace token (for gated models like Llama)

---

## 🧪 **Testing Real Training**

### **Small Test Training:**

```python
# Create a tiny test dataset
# resources/datasets/test-tiny.jsonl
{"instruction": "What is 1+1?", "output": "2"}
{"instruction": "What is 2+2?", "output": "4"}
{"instruction": "What is 3+3?", "output": "6"}

# Start training with minimal config
{
  "model_name": "gpt2",  # Small model for testing
  "dataset_path": "resources/datasets/test-tiny.jsonl",
  "training_config": {
    "num_epochs": 1,
    "batch_size": 1,
    "learning_rate": 0.0001,
    "warmup_steps": 10
  },
  "lora_config": {
    "r": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.1
  }
}
```

Expected time: 2-5 minutes on GPU, 10-30 minutes on CPU

---

## ⚡ **Recommendation**

For now (development):
- **Use Option 2 (Threading)** for quick testing
- Validate your datasets and configs work
- Monitor GPU/RAM usage
- Then upgrade to **Option 3 (Celery)** for production

---

## 🎯 **Current vs. Real Training**

### **Current (Mock):**
```
User clicks "Start Training"
  ↓
API creates job record
  ↓
Returns job_id immediately
  ↓
Status stays "queued" forever
  ↓
❌ No actual training happens
```

### **With Real Training:**
```
User clicks "Start Training"
  ↓
API creates job record
  ↓
Returns job_id immediately
  ↓
Background task starts actual training
  ↓
Status updates: pending → running → completed
  ↓
Logs show real training progress
  ↓
✅ Model saved to output directory
```

---

## 🚀 **Next Steps**

1. **Choose implementation option** (Threading recommended for start)
2. **Verify GPU availability** (`nvidia-smi` command)
3. **Install training dependencies**
4. **Create small test dataset**
5. **Uncomment training code**
6. **Test with small model (GPT-2)**
7. **Monitor logs and GPU usage**
8. **Scale up to larger models**

Would you like me to implement Option 2 (Threading) for you? 🎯

