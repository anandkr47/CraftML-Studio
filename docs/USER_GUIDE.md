# CraftML Studio - User Guide

## Getting Started

After installing and running CraftML Studio, you'll see the main dashboard with navigation to different features.

## Features Overview

### 1. Dashboard
The main overview showing:
- Active jobs (training, crawling, compression)
- System resources (GPU, CPU, memory)
- Recent activities
- Quick actions

### 2. Dataset Crawler

Create custom datasets by crawling the web.

**Steps:**
1. Navigate to **Crawler** page
2. Enter seed URLs (one per line)
3. Configure settings:
   - **Max Depth:** How many levels to crawl (1-5)
   - **Max Pages:** Maximum pages to collect (10-1000)
   - **Timeout:** Request timeout in seconds
4. Click **Start Crawl**
5. Monitor progress in real-time
6. Preview collected data
7. Save dataset in desired format

**Example Use Cases:**
- Collect documentation for RAG
- Build domain-specific datasets
- Gather training data from specific websites

### 3. Dataset Manager

View and manage your collected datasets.

**Features:**
- List all datasets
- View dataset details
- Preview content
- Delete datasets
- Export in different formats (JSONL, CSV, Text)

### 4. Model Training

Fine-tune language models on your datasets.

**Steps:**
1. Navigate to **Training Console**
2. Select a base model:
   - From Hugging Face Hub
   - From local models
3. Choose your dataset
4. Configure training:
   - **LoRA Settings:**
     - Rank (r): 8, 16, 32 (higher = more parameters)
     - Alpha: Usually 2x rank
     - Dropout: 0.05-0.1
   - **Training Settings:**
     - Epochs: 1-10
     - Batch Size: 1-8 (depends on GPU)
     - Learning Rate: 1e-5 to 5e-4
   - **Quantization:**
     - 4-bit (QLoRA) - recommended
     - 8-bit
     - No quantization
5. Click **Start Training**
6. Monitor:
   - Loss curve
   - GPU usage
   - Training logs
7. Save trained model

**Tips:**
- Start with 4-bit quantization to save memory
- Use smaller batch sizes if you run out of memory
- Monitor loss - should decrease over time

### 5. Model Compression

Reduce model size for faster inference.

**Compression Methods:**

#### Quantization
Convert model weights to lower precision.

- **INT8:** ~2x smaller, minimal accuracy loss
- **INT4:** ~4x smaller, slight accuracy loss
- **GPTQ:** Advanced quantization with calibration

**Steps:**
1. Select model to compress
2. Choose quantization method
3. Set output location
4. Click **Compress**
5. Compare original vs compressed size

#### Pruning
Remove less important weights.

- **Magnitude Pruning:** Remove smallest weights
- **Structured Pruning:** Remove entire neurons/channels

**Steps:**
1. Select model
2. Choose pruning method
3. Set sparsity level (e.g., 30% = remove 30% of weights)
4. Click **Prune**

#### Knowledge Distillation
Transfer knowledge to smaller model.

**Steps:**
1. Select teacher model (large)
2. Select student model (small)
3. Provide training data
4. Configure temperature and alpha
5. Start distillation

### 6. Model Deployment

Deploy your models for inference.

#### Local Deployment
Run model as a local API server.

**Steps:**
1. Navigate to **Deployment Console**
2. Select model
3. Choose **Local Deployment**
4. Set port (default: 5001)
5. Click **Deploy**
6. Test API at `http://127.0.0.1:5001/generate`

**API Usage:**
```bash
curl -X POST http://127.0.0.1:5001/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Hello, how are you?",
    "max_length": 100,
    "temperature": 0.7
  }'
```

#### Hugging Face Deployment
Upload model to Hugging Face Hub.

**Steps:**
1. Get HuggingFace token from https://huggingface.co/settings/tokens
2. Enter token in deployment settings
3. Select model
4. Choose repository name
5. Set visibility (public/private)
6. Click **Deploy to Hugging Face**
7. Model will be available at `huggingface.co/{username}/{model-name}`

### 7. Resource Monitoring

Real-time monitoring of system resources.

**Metrics:**
- **GPU:** Utilization, memory, temperature
- **CPU:** Usage per core, frequency
- **Memory:** RAM usage, swap
- **Disk:** Storage usage

**Features:**
- Live charts
- Historical data
- Export metrics
- Alerts for high usage

### 8. Model Hub

Browse and download models from Hugging Face.

**Features:**
- Search models
- View model details
- Download to local storage
- Manage local models

## Workflows

### Complete ML Pipeline Example

**Scenario:** Train a chatbot on company documentation

1. **Collect Data:**
   ```
   Crawler → Enter company doc URLs → Crawl → Save dataset
   ```

2. **Prepare Dataset:**
   ```
   Dataset Manager → Select dataset → Format as instruction-tuning
   ```

3. **Train Model:**
   ```
   Training Console → Select base model (e.g., Llama-2-7b)
   → Load dataset → Configure LoRA → Train
   ```

4. **Compress Model:**
   ```
   Compression → Select trained model → INT4 quantization
   → Compress → Save
   ```

5. **Deploy:**
   ```
   Deployment → Select compressed model → Local deployment
   → Deploy → Test API
   ```

6. **Monitor:**
   ```
   Resource Monitor → Check GPU/CPU usage during inference
   ```

## Tips & Best Practices

### Training
- Start with small epochs (1-3) and validate results
- Use gradient accumulation if batch size is too small
- Save checkpoints regularly
- Monitor validation loss to prevent overfitting

### Crawling
- Respect robots.txt
- Use reasonable delays between requests
- Start with small page limits for testing
- Verify data quality before using for training

### Compression
- Test compressed model before deployment
- Compare quality metrics (perplexity, accuracy)
- Use INT4 for deployment, keep FP16 for training
- Document compression settings for reproducibility

### Deployment
- Test locally before cloud deployment
- Monitor resource usage in production
- Set up proper error handling
- Use batching for multiple requests

### Resource Management
- Close unused deployments
- Clear completed jobs regularly
- Archive old datasets
- Monitor disk space

## Keyboard Shortcuts

- `Ctrl/Cmd + K` - Command palette (coming soon)
- `Ctrl/Cmd + ,` - Settings
- `Ctrl/Cmd + Shift + M` - Monitor view
- `Esc` - Close dialogs

## Troubleshooting

### Training Issues

**Problem:** Out of memory (OOM)
**Solutions:**
- Reduce batch size
- Enable 4-bit quantization
- Use gradient checkpointing
- Choose smaller model

**Problem:** Training loss not decreasing
**Solutions:**
- Check learning rate (try 2e-4)
- Verify dataset quality
- Increase epochs
- Check for data leakage

### Deployment Issues

**Problem:** API not responding
**Solutions:**
- Check if deployment is running
- Verify port is not blocked
- Check logs for errors
- Restart deployment

**Problem:** Slow inference
**Solutions:**
- Use quantized model
- Reduce max_length
- Enable GPU if available
- Use batching

### Crawler Issues

**Problem:** Pages not loading
**Solutions:**
- Check internet connection
- Increase timeout
- Verify URLs are accessible
- Check for CAPTCHA/blocking

## FAQ

**Q: Can I use CraftML Studio offline?**
A: Yes! All core features work offline. You only need internet for downloading base models and deploying to cloud.

**Q: What models are supported?**
A: Any Hugging Face Transformers model (LLaMA, GPT-2, BERT, etc.)

**Q: How much GPU memory do I need?**
A: Depends on model size:
- 7B model: 6-8GB (with 4-bit)
- 13B model: 10-16GB (with 4-bit)
- CPU only: Possible but slower

**Q: Can I train on multiple GPUs?**
A: Not yet, but planned for future release.

**Q: Where are my models stored?**
A: In `resources/models/` by default (configurable in settings)

**Q: How do I update CraftML Studio?**
A: Download new version and reinstall. Your data is preserved.

## Support & Community

- **Documentation:** Check docs/ folder
- **Issues:** Report bugs on GitHub
- **Discussions:** Join community forums
- **Updates:** Watch repository for new releases

