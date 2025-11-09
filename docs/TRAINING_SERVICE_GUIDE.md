# 🧠 Model Training Service Guide

**CraftML Studio Training Service**  
*Hardware-aware training with Transformers, Accelerate, and PEFT*

---

## 📋 Overview

The Training Service provides comprehensive model fine-tuning with:

1. **Hugging Face Transformers** - Load and train pre-trained models
2. **Accelerate** - Multi-GPU, mixed precision, automatic device placement
3. **PEFT** - Parameter-efficient fine-tuning (LoRA, QLoRA)
4. **Hardware Detection** - Auto-detect CUDA, ROCm, Metal
5. **Strategy Recommendation** - Automatic training strategy selection

---

## 🎯 Supported Training Strategies

### 1. **LoRA (Low-Rank Adaptation)**
- **Best For:** Mid-range GPUs (8-16 GB VRAM)
- **VRAM Usage:** ~30% of full fine-tuning
- **Speed:** Fast
- **Quality:** Good
- **Description:** Trains small adapter layers instead of the full model

### 2. **QLoRA (Quantized LoRA)**
- **Best For:** Low VRAM GPUs (4-8 GB)
- **VRAM Usage:** ~25% of LoRA
- **Speed:** Medium  
- **Quality:** Good
- **Description:** 4-bit quantization + LoRA for minimal VRAM

### 3. **Full Fine-tuning**
- **Best For:** High-end GPUs (16+ GB VRAM)
- **VRAM Usage:** 100%
- **Speed:** Slow
- **Quality:** Best
- **Description:** Trains all model parameters

---

## 🖥️ Supported Hardware

### Platform Compatibility

| Platform | Backend | Hardware | Status |
|----------|---------|----------|--------|
| **CUDA** | NVIDIA GPUs | RTX 3090, 4090, A100, etc. | ✅ Full Support |
| **ROCm** | AMD GPUs | RX 6800, 7900, MI100, etc. | ✅ Linux Only |
| **Metal** | Apple Silicon | M1, M2, M3 | ✅ macOS Only |
| **CPU** | Intel/AMD CPUs | Any x86_64 | ✅ All Platforms |

### Hardware Detection

The system automatically detects:
- GPU type and count
- Total VRAM available
- Compute capabilities
- Supported precision (FP16, BF16)
- Flash Attention support

---

## 💻 API Reference

### Hardware Detection

#### Get Hardware Info

**Endpoint:** `GET /api/hardware/info`

**Response:**
```json
{
  "platform": "Windows",
  "device_type": "cuda",
  "device_name": "NVIDIA GeForce RTX 4090",
  "backend": "cuda",
  "cuda_available": true,
  "rocm_available": false,
  "mps_available": false,
  "gpu_count": 1,
  "total_vram_gb": 24.0,
  "recommended_strategy": "lora"
}
```

#### Get Training Recommendation

**Endpoint:** `GET /api/hardware/recommend?strategy=lora`

**Response:**
```json
{
  "device": "cuda",
  "device_map": "auto",
  "strategy": "lora",
  "use_4bit": false,
  "use_8bit": false,
  "fp16": false,
  "bf16": true,
  "use_flash_attention": true,
  "gradient_checkpointing": true,
  "per_device_train_batch_size": 4,
  "gradient_accumulation_steps": 2
}
```

#### List Available Backends

**Endpoint:** `GET /api/hardware/backends`

**Response:**
```json
{
  "backends": {
    "cuda": {
      "available": true,
      "description": "NVIDIA GPUs",
      "platforms": ["Windows", "Linux"]
    },
    "rocm": {
      "available": false,
      "description": "AMD GPUs",
      "platforms": ["Linux"]
    },
    "metal": {
      "available": false,
      "description": "Apple Silicon (M1/M2/M3)",
      "platforms": ["macOS"]
    },
    "cpu": {
      "available": true,
      "description": "CPU-based training",
      "platforms": ["All"]
    }
  },
  "current_backend": "cuda"
}
```

#### List Training Strategies

**Endpoint:** `GET /api/hardware/strategies`

**Response:**
```json
{
  "strategies": {
    "lora": {
      "name": "LoRA (Low-Rank Adaptation)",
      "description": "Parameter-efficient fine-tuning",
      "vram_required_gb": 8,
      "recommended": true,
      "speed": "Fast",
      "quality": "Good"
    },
    "qlora": {
      "name": "QLoRA (Quantized LoRA)",
      "description": "4-bit quantized LoRA for low VRAM",
      "vram_required_gb": 4,
      "recommended": false,
      "speed": "Medium",
      "quality": "Good"
    },
    "full": {
      "name": "Full Fine-tuning",
      "description": "Train all model parameters",
      "vram_required_gb": 16,
      "recommended": false,
      "speed": "Slow",
      "quality": "Best"
    }
  },
  "recommended": "lora",
  "your_vram_gb": 24.0
}
```

---

### Training API

#### Start Training

**Endpoint:** `POST /api/train/start`

**Request:**
```json
{
  "model_name": "meta-llama/Llama-2-7b-hf",
  "dataset_path": "resources/datasets/my_data.jsonl",
  "output_dir": "resources/models/llama2-finetuned",
  "lora_config": {
    "r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "v_proj"]
  },
  "training_config": {
    "num_epochs": 3,
    "batch_size": 4,
    "learning_rate": 0.0002,
    "warmup_steps": 100,
    "use_4bit": false
  }
}
```

**Response:**
```json
{
  "job_id": "train_20231014_123456_abc123",
  "status": "pending",
  "message": "Training job created successfully"
}
```

---

## 🚀 Usage Examples

### Example 1: Auto-Detect Hardware

```python
import requests

# Get hardware info
response = requests.get('http://localhost:5000/api/hardware/info')
hardware = response.json()

print(f"Device: {hardware['device_name']}")
print(f"VRAM: {hardware['total_vram_gb']:.1f} GB")
print(f"Recommended: {hardware['recommended_strategy']}")
```

**Output:**
```
Device: NVIDIA GeForce RTX 4090
VRAM: 24.0 GB
Recommended: lora
```

---

### Example 2: Get Training Recommendation

```python
# Get automatic recommendation
response = requests.get('http://localhost:5000/api/hardware/recommend')
config = response.json()

print(f"Strategy: {config['strategy']}")
print(f"Batch Size: {config['per_device_train_batch_size']}")
print(f"Use BF16: {config['bf16']}")
print(f"Flash Attention: {config['use_flash_attention']}")
```

---

### Example 3: Train with LoRA

```python
# Start training with recommended config
response = requests.post('http://localhost:5000/api/train/start', json={
    "model_name": "meta-llama/Llama-2-7b-hf",
    "dataset_path": "resources/datasets/my_data.jsonl",
    "output_dir": "resources/models/llama2-finetuned",
    "lora_config": {
        "r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05
    },
    "training_config": {
        "num_epochs": 3,
        "batch_size": 4,
        "learning_rate": 2e-4,
        "use_4bit": False  # LoRA without quantization
    }
})

job_id = response.json()['job_id']
print(f"Training started: {job_id}")

# Monitor progress
import time
while True:
    status = requests.get(f'http://localhost:5000/api/tasks/status/{job_id}')
    data = status.json()
    
    if data['status'] in ['completed', 'failed']:
        break
    
    print(f"Progress: {data['info'].get('progress', 0):.1f}%")
    time.sleep(5)
```

---

### Example 4: Train with QLoRA (Low VRAM)

```python
# For GPUs with limited VRAM
response = requests.post('http://localhost:5000/api/train/start', json={
    "model_name": "meta-llama/Llama-2-7b-hf",
    "dataset_path": "resources/datasets/my_data.jsonl",
    "lora_config": {
        "r": 16,
        "lora_alpha": 32
    },
    "training_config": {
        "num_epochs": 3,
        "batch_size": 1,  # Smaller batch for low VRAM
        "use_4bit": True  # QLoRA - 4-bit quantization
    }
})
```

---

## 📊 Hardware Requirements

### Minimum Requirements by Model Size

| Model Size | Strategy | Min VRAM | Recommended VRAM | Example GPUs |
|------------|----------|----------|------------------|--------------|
| **7B** | QLoRA | 6 GB | 8 GB | RTX 3060, RX 6800 |
| **7B** | LoRA | 12 GB | 16 GB | RTX 3090, RTX 4080 |
| **7B** | Full | 24 GB | 32 GB | RTX 4090, A100 |
| **13B** | QLoRA | 10 GB | 12 GB | RTX 3090, RTX 4080 |
| **13B** | LoRA | 20 GB | 24 GB | RTX 4090, A100 40GB |
| **70B** | QLoRA | 32 GB | 48 GB | A100 40GB, H100 |

---

## ⚙️ Configuration Options

### LoRA Configuration

```python
{
  "r": 16,                    # Rank (4-64)
  "lora_alpha": 32,           # Alpha scaling (typically 2x rank)
  "lora_dropout": 0.05,       # Dropout rate
  "target_modules": [         # Which modules to adapt
    "q_proj", "k_proj", 
    "v_proj", "o_proj"
  ]
}
```

### Training Configuration

```python
{
  "num_epochs": 3,                      # Training epochs
  "batch_size": 4,                      # Per-device batch size
  "learning_rate": 2e-4,                # Learning rate
  "warmup_steps": 100,                  # Warmup steps
  "use_4bit": False,                    # 4-bit quantization (QLoRA)
  "use_8bit": False,                    # 8-bit quantization
  "gradient_accumulation_steps": 4,     # Gradient accumulation
  "max_grad_norm": 0.3                  # Gradient clipping
}
```

---

## 🎯 Training Strategy Selection

### Decision Tree

```
Available VRAM?
│
├─ < 8 GB ──────→ QLoRA (4-bit)
│                 - Batch size: 1-2
│                 - Grad accumulation: 8
│
├─ 8-16 GB ─────→ LoRA
│                 - Batch size: 2-4
│                 - Grad accumulation: 4
│
└─ > 16 GB ─────→ LoRA or Full
                  - Batch size: 4-8
                  - Grad accumulation: 2
```

---

## 🔧 Advanced Features

### 1. **Mixed Precision Training**
- **BF16:** Best for modern GPUs (Ampere+)
- **FP16:** Older GPUs
- **Automatic:** System detects best option

### 2. **Flash Attention**
- Automatically enabled on compatible GPUs
- 2-4x faster attention computation
- Reduced memory usage

### 3. **Gradient Checkpointing**
- Trade computation for memory
- Enables larger models/batches
- Automatically enabled

### 4. **Multi-GPU Support**
- Accelerate handles DDP automatically
- Supports data parallel training
- Model parallel for very large models

---

## 🌐 Platform-Specific Notes

### CUDA (NVIDIA)
```bash
# Install CUDA toolkit (if not already installed)
# Windows: Download from NVIDIA website
# Linux: 
sudo apt install nvidia-cuda-toolkit

# Verify
nvidia-smi
```

### ROCm (AMD)
```bash
# Linux only
# Install ROCm
wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | sudo apt-key add -
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/debian/ ubuntu main' | sudo tee /etc/apt/sources.list.d/rocm.list
sudo apt update
sudo apt install rocm-dkms

# Verify
rocm-smi
```

### Metal (Apple Silicon)
```bash
# No additional installation needed
# Metal is built into macOS

# Verify PyTorch MPS
python -c "import torch; print(torch.backends.mps.is_available())"
```

---

## ✅ Best Practices

### 1. **Let the System Detect**
```python
# Don't hardcode device - let hardware detector choose
GET /api/hardware/recommend
```

### 2. **Start with Recommended Strategy**
```python
# Use recommended strategy for your hardware
recommended = hardware['recommended_strategy']
```

### 3. **Monitor VRAM Usage**
```python
# Check GPU memory during training
GET /api/monitor/resources
```

### 4. **Use Gradient Accumulation**
```python
# Instead of large batch size, accumulate gradients
{
  "batch_size": 2,
  "gradient_accumulation_steps": 8
}
# Effective batch size = 2 × 8 = 16
```

### 5. **Save Checkpoints**
```python
{
  "save_steps": 100,  # Save every 100 steps
  "save_strategy": "steps"
}
```

---

## 📈 Performance Optimization

### VRAM Optimization
1. Use QLoRA for low VRAM
2. Reduce batch size
3. Increase gradient accumulation
4. Enable gradient checkpointing
5. Use smaller LoRA rank

### Speed Optimization
1. Use Flash Attention (auto-enabled)
2. Use BF16/FP16
3. Increase batch size (if VRAM allows)
4. Use multi-GPU
5. Disable unnecessary logging

---

## ✅ Summary

The Training Service provides:

✅ **Hugging Face Transformers** - Pre-trained model loading  
✅ **Accelerate** - Multi-GPU, mixed precision  
✅ **PEFT** - LoRA, QLoRA parameter-efficient training  
✅ **Hardware Detection** - Auto-detect CUDA, ROCm, Metal  
✅ **Strategy Recommendation** - Automatic configuration  
✅ **Complete API** - REST endpoints for all operations  
✅ **Real-time Monitoring** - Progress and metrics tracking  

**Status:** Production Ready 🚀

---

**Documentation:** Complete  
**All Platforms:** CUDA, ROCm, Metal, CPU  
**All Strategies:** LoRA, QLoRA, Full Fine-tuning

