# 🚀 CraftML Studio - Quick Reference

**Your complete guide to getting started quickly!**

---

## ⚡ Quick Commands

### **Setup (One Time)**
```powershell
# Windows
.\scripts\setup.ps1

# Linux/Mac
chmod +x scripts/*.sh && ./scripts/setup.sh
```

### **Development**
```powershell
# Windows
.\scripts\dev.ps1

# Linux/Mac
./scripts/dev.sh
```

### **Production Build**
```powershell
# Windows
.\scripts\build_desktop.ps1

# Linux/Mac
./scripts/build_desktop.sh
```

---

## 📖 Common Workflows

### **1. Build a Custom Dataset**

```
1. Open CraftML Studio
2. Navigate to "Crawler" page
3. Enter seed URLs:
   - https://example.com/docs
   - https://example.com/guide
4. Set max_depth: 3, max_pages: 100
5. Click "Start Crawl"
6. Wait for completion
7. Click "Save Dataset"
8. Choose format: JSONL
```

**Result:** Dataset ready for training!

---

### **2. Fine-Tune a Model**

```
1. Navigate to "Training Console"
2. Select base model:
   - Use template: Llama-2-7B
   OR
   - Download from Model Hub
3. Select your dataset
4. Configure (or use preset):
   - Template: Chatbot Config
5. Click "Start Training"
6. Monitor:
   - Loss curve
   - GPU usage
   - Training logs
7. Wait for completion
8. Model saved automatically
```

**Result:** Fine-tuned model ready!

---

### **3. Compress a Model**

```
1. Navigate to "Compression Playground"
2. Select your trained model
3. Choose method:
   - INT4 (recommended): 4x smaller
   - INT8: 2x smaller
   - GPTQ: Advanced quantization
4. Set output path
5. Click "Compress"
6. View comparison:
   - Original size vs compressed
   - Compression ratio
```

**Result:** Optimized model!

---

### **4. Deploy a Model**

**Option A: Local Deployment**
```
1. Navigate to "Deployment Console"
2. Select model
3. Choose "Local Deployment"
4. Set port: 5001
5. Click "Deploy"
6. API available at: http://127.0.0.1:5001
```

**Test Your API:**
```bash
curl -X POST http://127.0.0.1:5001/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello!", "max_length": 50}'
```

**Option B: HuggingFace**
```
1. Get HF token from: https://huggingface.co/settings/tokens
2. Select model
3. Choose "HuggingFace Deployment"
4. Enter:
   - Repository name: username/model-name
   - HF Token: hf_xxx...
   - Private: Yes/No
5. Click "Deploy"
6. Model uploaded to HuggingFace!
```

**Result:** Model deployed and accessible!

---

## 🎯 API Quick Reference

### **Training**
```bash
# Start training
POST http://127.0.0.1:5000/api/train/start
{
  "model_name": "meta-llama/Llama-2-7b-hf",
  "dataset_path": "./datasets/my_data.jsonl",
  "training_config": {"num_epochs": 3, "use_4bit": true}
}

# Check status
GET http://127.0.0.1:5000/api/train/status/{job_id}

# Get logs
GET http://127.0.0.1:5000/api/train/logs/{job_id}
```

### **Crawling**
```bash
# Start crawl
POST http://127.0.0.1:5000/api/crawler/start
{
  "seed_urls": ["https://example.com"],
  "max_depth": 3,
  "max_pages": 100
}

# Check status
GET http://127.0.0.1:5000/api/crawler/status/{job_id}

# Preview data
GET http://127.0.0.1:5000/api/crawler/preview/{job_id}
```

### **Monitoring**
```bash
# Get all metrics
GET http://127.0.0.1:5000/api/monitor/metrics

# GPU only
GET http://127.0.0.1:5000/api/monitor/gpu

# System metrics
GET http://127.0.0.1:5000/api/monitor/system
```

---

## 🔧 Configuration

### **Environment Variables (.env)**

```bash
# API Settings
API_HOST=127.0.0.1
API_PORT=5000

# HuggingFace
HF_TOKEN=your_token_here

# ML Settings
DEFAULT_DEVICE=auto
DEFAULT_BATCH_SIZE=4
DEFAULT_LEARNING_RATE=2e-4

# Crawler
MAX_CRAWL_DEPTH=3
MAX_CRAWL_PAGES=100
```

### **Model Templates**

Located in `resources/models/`:
- `llama2-7b-config.json` - Llama-2 settings
- `mistral-7b-config.json` - Mistral settings  
- `phi-2-config.json` - Phi-2 settings

### **Training Templates**

Located in `resources/templates/`:
- `chatbot-config.json` - For conversational AI
- `qa-system-config.json` - For Q&A systems

---

## 🐛 Troubleshooting

### **Backend Won't Start**
```powershell
# Check Python version
python --version  # Should be 3.11+

# Check dependencies
cd apps/backend
pip list

# Check logs
Get-Content apps/backend/logs/backend.log -Tail 50
```

### **Frontend Build Fails**
```powershell
# Reinstall dependencies
cd apps/desktop
Remove-Item -Recurse node_modules
npm install

# Clear cache
npm cache clean --force
```

### **Out of GPU Memory**
```
Solutions:
1. Enable 4-bit quantization: use_4bit: true
2. Reduce batch size: batch_size: 1 or 2
3. Use gradient accumulation: gradient_accumulation_steps: 4
4. Choose smaller model: Phi-2 instead of Llama-2
```

### **Training Loss Not Decreasing**
```
Solutions:
1. Check dataset quality
2. Adjust learning rate: try 2e-4 or 5e-4
3. Increase epochs
4. Verify data format is correct
```

---

## 📂 Important Paths

### **Default Locations**

```
Models:   resources/models/
Datasets: resources/datasets/
Logs:     apps/backend/logs/
Configs:  resources/templates/
```

### **Change Paths**

Edit `core/config/settings.py`:
```python
models_dir: Path = Path("./custom/models")
datasets_dir: Path = Path("./custom/datasets")
```

---

## 🎓 Learning Path

### **Day 1: Setup & Basics**
1. Run `.\scripts\setup.ps1`
2. Read `START_HERE.md`
3. Start dev mode: `.\scripts\dev.ps1`
4. Explore the UI
5. Try the Dashboard

### **Day 2: Data Collection**
1. Read `docs/USER_GUIDE.md` - Crawler section
2. Try crawling a simple website
3. Preview the data
4. Export to different formats
5. Understand deduplication

### **Day 3: Model Training**
1. Read Model Training section in USER_GUIDE
2. Download a small model (Phi-2)
3. Use example dataset
4. Start training with preset
5. Monitor progress

### **Day 4: Compression & Deployment**
1. Compress your trained model
2. Compare sizes
3. Deploy locally
4. Test the API
5. Try HuggingFace deployment

### **Day 5: Advanced**
1. Create custom dataset format
2. Write a plugin
3. Customize training template
4. Optimize hyperparameters
5. Build for production

---

## 💡 Pro Tips

### **Performance**
- Always use 4-bit quantization for training (saves 75% memory)
- Start with small epochs (1-2) to validate before full training
- Monitor GPU temperature (keep below 80°C)
- Use gradient accumulation for larger effective batch sizes

### **Quality**
- Clean datasets produce better models
- 500 quality samples > 5000 poor samples
- Always deduplicate your data
- Validate dataset format before training

### **Efficiency**
- Use templates as starting points
- Save checkpoints frequently
- Compress models before deployment
- Monitor resources to optimize settings

### **Organization**
- Name jobs descriptively
- Keep training logs
- Document what works
- Version your datasets

---

## 🔗 Quick Links

| What | Where |
|------|-------|
| **Setup Guide** | `docs/SETUP.md` |
| **User Guide** | `docs/USER_GUIDE.md` |
| **API Docs** | `docs/API_REFERENCE.md` |
| **Architecture** | `docs/ARCHITECTURE.md` |
| **Model Templates** | `resources/models/` |
| **Dataset Examples** | `resources/datasets/` |
| **Training Presets** | `resources/templates/` |
| **Plugin Examples** | `plugins/` |

---

## 📊 Feature Matrix

| Feature | Status | Documentation |
|---------|--------|---------------|
| Web Crawling | ✅ Ready | USER_GUIDE.md §2 |
| Dataset Management | ✅ Ready | USER_GUIDE.md §2.5 |
| Model Training | ✅ Ready | USER_GUIDE.md §4 |
| Model Compression | ✅ Ready | USER_GUIDE.md §5 |
| Model Deployment | ✅ Ready | USER_GUIDE.md §6 |
| Resource Monitoring | ✅ Ready | USER_GUIDE.md §7 |
| Model Hub | ✅ Ready | USER_GUIDE.md §8 |
| Plugin System | ✅ Ready | plugins/*/README.md |

---

## 🆘 Need Help?

### **Quick Help:**
1. Check `START_HERE.md` (you are here!)
2. Read `docs/USER_GUIDE.md` for features
3. Check `docs/SETUP.md` for installation issues

### **API Help:**
1. Check `docs/API_REFERENCE.md`
2. View auto-generated docs: http://127.0.0.1:5000/docs
3. Check logs: `apps/backend/logs/`

### **Development Help:**
1. Read `docs/ARCHITECTURE.md`
2. Check `FINAL_CODEBASE_MAP.md`
3. Explore `core/` modules

---

## ✨ What Makes CraftML Studio Special

🎯 **Local-First** - No cloud dependency, complete privacy  
🧠 **Complete ML Pipeline** - Crawl → Train → Compress → Deploy  
🔌 **Extensible** - Plugin system for customization  
📊 **Real-Time** - Live monitoring and WebSocket updates  
📚 **Well-Documented** - 115 KB of guides and references  
💯 **Production-Ready** - Zero placeholders, all real code  

---

## 🚀 You're Ready!

```powershell
# Start now:
.\scripts\dev.ps1

# Build your first AI model:
# 1. Crawl data
# 2. Train model
# 3. Deploy locally
# 4. Test and iterate
```

---

**Questions?** Read the docs in `docs/`  
**Issues?** Check logs in `apps/backend/logs/`  
**Ready?** Run `.\scripts\dev.ps1` 🎨

---

**Last Updated:** October 13, 2025  
**Version:** 0.1.0  
**Status:** ✅ Production Ready

