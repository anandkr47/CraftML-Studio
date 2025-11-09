# 🚀 Deployment Service Guide

**CraftML Studio Deployment Service**  
*Convert, package, and deploy models in multiple formats*

---

## 📋 Overview

The Deployment Service provides comprehensive model deployment capabilities:

1. **Format Conversion** - Convert models to GGUF, ONNX, SafeTensors
2. **Local Inference** - Deploy models as REST APIs
3. **HuggingFace Deployment** - Upload to Hub and Spaces
4. **Docker Packaging** - Create containerized inference services

---

## 🎯 Supported Model Formats

### 1. **Transformers (.bin, .safetensors)**
- Native PyTorch format
- Full HuggingFace compatibility
- Best for training and fine-tuning

### 2. **GGUF (llama.cpp/Ollama)**
- Optimized for CPU inference
- Quantized formats (Q4_K_M, Q5_K_M, Q8_0)
- Compatible with llama.cpp and Ollama

### 3. **ONNX**
- Cross-platform inference
- Optimized for CPU deployment
- Web deployment ready

### 4. **SafeTensors**
- Secure model loading
- Fast loading times
- Modern HuggingFace standard

---

## 💻 API Reference

### Model Conversion

#### Convert Model Format

**Endpoint:** `POST /api/convert/convert`

**Request:**
```json
{
  "model_path": "resources/models/my-model",
  "output_format": "gguf",
  "output_path": "resources/models/my-model.gguf",
  "quantization": "Q4_K_M"
}
```

**Response:**
```json
{
  "status": "success",
  "output_path": "resources/models/my-model.gguf",
  "format": "gguf",
  "size_mb": 3842.5,
  "quantization": "Q4_K_M"
}
```

#### Get Supported Formats

**Endpoint:** `GET /api/convert/supported-formats`

**Response:**
```json
{
  "formats": ["gguf", "onnx", "safetensors"],
  "details": {
    "gguf": {
      "description": "GGUF format for llama.cpp/Ollama",
      "quantizations": ["Q4_K_M", "Q5_K_M", "Q8_0", "f16"],
      "use_case": "Local inference with llama.cpp"
    },
    "onnx": {
      "description": "ONNX format for cross-platform inference",
      "optimizations": true,
      "use_case": "CPU inference, web deployment"
    },
    "safetensors": {
      "description": "SafeTensors format for secure model loading",
      "use_case": "Modern Hugging Face models"
    }
  }
}
```

---

### Docker Deployment

#### Build Docker Image

**Endpoint:** `POST /api/docker/build`

**Request:**
```json
{
  "model_path": "resources/models/my-model",
  "image_name": "my-model-inference:latest",
  "output_dir": "deployments/my-model",
  "device": "cpu",
  "port": 8000
}
```

**Response:**
```json
{
  "status": "success",
  "image_name": "my-model-inference:latest",
  "build_dir": "deployments/my-model/docker_build",
  "dockerfile": "deployments/my-model/docker_build/Dockerfile",
  "docker_compose": "deployments/my-model/docker-compose.yml",
  "usage": {
    "run": "docker run -p 8000:8000 my-model-inference:latest",
    "compose": "cd deployments/my-model && docker-compose up -d"
  }
}
```

#### Check Docker Availability

**Endpoint:** `GET /api/docker/check`

**Response:**
```json
{
  "docker_available": true,
  "message": "Docker is available"
}
```

#### Create Docker Files

**Endpoint:** `POST /api/docker/create-files`

**Query Parameters:**
- `output_dir` - Directory to create files in
- `device` - "cpu" or "gpu"
- `port` - Port to expose

**Response:**
```json
{
  "status": "success",
  "files": {
    "dockerfile": "deployments/Dockerfile",
    "server": "deployments/server.py",
    "docker_compose": "deployments/docker-compose.yml"
  }
}
```

---

### Local Deployment

#### Deploy Model Locally

**Endpoint:** `POST /api/deploy/start`

**Request:**
```json
{
  "type": "local",
  "model_path": "resources/models/my-model",
  "port": 5001
}
```

**Response:**
```json
{
  "deployment_id": "deploy_abc123",
  "status": "running",
  "url": "http://127.0.0.1:5001",
  "endpoints": {
    "generate": "http://127.0.0.1:5001/generate",
    "health": "http://127.0.0.1:5001/health"
  }
}
```

---

### HuggingFace Deployment

#### Deploy to HuggingFace Hub

**Endpoint:** `POST /api/deploy/start`

**Request:**
```json
{
  "type": "huggingface",
  "model_path": "resources/models/my-model",
  "repo_name": "username/my-model",
  "hf_token": "hf_...",
  "private": false
}
```

**Response:**
```json
{
  "deployment_id": "deploy_def456",
  "status": "completed",
  "result": {
    "status": "success",
    "url": "https://huggingface.co/username/my-model",
    "repo_id": "username/my-model"
  }
}
```

---

## 🚀 Usage Examples

### Example 1: Convert to GGUF

```python
import requests

# Convert model to GGUF for llama.cpp
response = requests.post('http://localhost:5000/api/convert/convert', json={
    "model_path": "resources/models/llama2-7b-finetuned",
    "output_format": "gguf",
    "output_path": "resources/models/llama2-7b-finetuned.gguf",
    "quantization": "Q4_K_M"  # 4-bit quantization
})

result = response.json()
print(f"Converted model: {result['output_path']}")
print(f"Size: {result['size_mb']:.2f} MB")
```

### Example 2: Convert to ONNX

```python
# Convert model to ONNX for CPU deployment
response = requests.post('http://localhost:5000/api/convert/convert', json={
    "model_path": "resources/models/my-model",
    "output_format": "onnx",
    "output_path": "resources/models/my-model-onnx",
    "opset_version": 14,
    "optimize": True
})

result = response.json()
print(f"ONNX model: {result['output_path']}")
```

### Example 3: Build Docker Image

```python
# Build Docker image for deployment
response = requests.post('http://localhost:5000/api/docker/build', json={
    "model_path": "resources/models/my-model",
    "image_name": "my-model:latest",
    "output_dir": "deployments/my-model",
    "device": "cpu",
    "port": 8000
})

result = response.json()
print(f"Docker image built: {result['image_name']}")
print(f"Run with: {result['usage']['run']}")
```

### Example 4: Deploy Locally

```python
# Deploy model as local REST API
response = requests.post('http://localhost:5000/api/deploy/start', json={
    "type": "local",
    "model_path": "resources/models/my-model",
    "port": 5001
})

deployment = response.json()
print(f"Model deployed at: {deployment['url']}")

# Test inference
inference_response = requests.post(
    f"{deployment['url']}/generate",
    json={
        "prompt": "Once upon a time",
        "max_length": 100,
        "temperature": 0.7
    }
)

print(inference_response.json()['generated_text'])
```

### Example 5: Deploy to HuggingFace

```python
# Upload model to HuggingFace Hub
response = requests.post('http://localhost:5000/api/deploy/start', json={
    "type": "huggingface",
    "model_path": "resources/models/my-model",
    "repo_name": "username/my-model",
    "hf_token": "hf_your_token_here",
    "private": False
})

deployment = response.json()
print(f"Model uploaded to: {deployment['result']['url']}")
```

---

## 📦 Format Comparison

| Format | Size | Speed | Use Case | Platforms |
|--------|------|-------|----------|-----------|
| **Transformers** | Large | Medium | Training, Fine-tuning | PyTorch, CUDA |
| **GGUF (Q4)** | Small (25%) | Fast | Local CPU inference | llama.cpp, Ollama |
| **GGUF (Q8)** | Medium (50%) | Fast | Quality CPU inference | llama.cpp, Ollama |
| **ONNX** | Medium | Fast | Cross-platform CPU | ONNX Runtime, Web |
| **SafeTensors** | Large | Fast | Modern HF models | PyTorch, CUDA |

---

## 🎯 GGUF Quantization Levels

| Quantization | Size | Quality | Speed | Use Case |
|--------------|------|---------|-------|----------|
| **Q4_K_M** | ~25% | Good | Very Fast | **Recommended** for most cases |
| **Q5_K_M** | ~31% | Better | Fast | Better quality needed |
| **Q8_0** | ~50% | Excellent | Fast | High quality required |
| **f16** | 100% | Perfect | Medium | Maximum quality |

---

## 🔧 Docker Deployment Workflow

### 1. Build Docker Image
```bash
POST /api/docker/build
{
  "model_path": "resources/models/my-model",
  "image_name": "my-model:latest",
  "output_dir": "deployments",
  "device": "cpu"
}
```

### 2. Files Created
```
deployments/
├── docker-compose.yml
└── docker_build/
    ├── Dockerfile
    ├── server.py
    └── model/
        ├── config.json
        ├── pytorch_model.bin
        └── tokenizer.json
```

### 3. Run with Docker
```bash
# Option 1: Direct Docker run
docker run -p 8000:8000 my-model:latest

# Option 2: Docker Compose
cd deployments
docker-compose up -d
```

### 4. Test API
```bash
# Health check
curl http://localhost:8000/health

# Generate text
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello", "max_length": 50}'
```

---

## 🌐 HuggingFace Deployment

### 1. Upload Model
```python
POST /api/deploy/start
{
  "type": "huggingface",
  "model_path": "resources/models/my-model",
  "repo_name": "username/my-model",
  "hf_token": "hf_...",
  "private": false
}
```

### 2. Model Available At
- **Hub:** `https://huggingface.co/username/my-model`
- **Download:** 
  ```python
  from transformers import AutoModel
  model = AutoModel.from_pretrained("username/my-model")
  ```

### 3. Optional: Create Space Demo
```python
{
  "create_space": true,
  "space_name": "username/my-model-demo"
}
```
- **Space URL:** `https://huggingface.co/spaces/username/my-model-demo`

---

## 📊 Deployment Options Summary

| Deployment Type | Setup Time | Scalability | Cost | Best For |
|----------------|------------|-------------|------|----------|
| **Local API** | Minutes | Single machine | Free | Development, testing |
| **Docker** | 30 minutes | Container orchestration | Low | Production, cloud |
| **HuggingFace Hub** | Minutes | HF infrastructure | Free/Paid | Sharing, collaboration |
| **HF Spaces** | 30 minutes | Auto-scaling | Free/Paid | Public demos |

---

## ✅ Best Practices

### 1. **Choose Right Format**
```
Local CPU → GGUF (Q4_K_M)
Cloud CPU → ONNX
GPU Inference → Transformers/SafeTensors
Mobile → ONNX (quantized)
```

### 2. **Docker for Production**
- Use multi-stage builds for smaller images
- Enable health checks
- Use docker-compose for easy management
- Tag images with versions

### 3. **HuggingFace Deployment**
- Always create model cards
- Use private repos for proprietary models
- Test models before making public
- Use Spaces for demos

### 4. **Local Development**
- Start with local deployment for testing
- Use Docker for reproducibility
- Deploy to HF for sharing

---

## 🚨 Troubleshooting

### GGUF Conversion Fails
```
Error: llama.cpp not found
Solution: Install llama.cpp and add to PATH
```

### Docker Build Fails
```
Error: Docker not available
Solution: Install Docker and start Docker daemon
```

### ONNX Conversion Slow
```
Issue: Large model takes long time
Solution: Use smaller opset_version or disable optimization
```

### HuggingFace Upload Fails
```
Error: Invalid token
Solution: Get token from https://huggingface.co/settings/tokens
```

---

## ✅ Summary

The Deployment Service provides:

✅ **Format Conversion** - GGUF, ONNX, SafeTensors  
✅ **Local Inference** - REST API deployment  
✅ **Docker Packaging** - Containerized inference  
✅ **HuggingFace Integration** - Hub and Spaces deployment  
✅ **Complete API** - All operations via REST  
✅ **Production Ready** - Health checks, optimizations  

**Status:** Production Ready 🚀

---

**Documentation:** Complete  
**All Formats:** Supported  
**Deployment Options:** Local, Docker, HuggingFace, ONNX

