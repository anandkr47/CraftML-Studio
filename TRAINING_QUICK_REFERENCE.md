# Training System Quick Reference 🚀

## 🎯 **Quick Start Guide**

### **Step 1: Select Model**
Choose between:
- **Pretrained Model** (recommended): Search HuggingFace models
- **Train from Scratch**: Build custom model architecture

### **Step 2: Choose Training Method**
| Method | Speed | Memory | Quality | Best For |
|--------|-------|--------|---------|----------|
| **QLoRA** ⚡ | Fastest | Lowest | Good | ✅ Most tasks (Recommended) |
| **LoRA** 🚀 | Fast | Low | Better | Multiple fine-tuning tasks |
| **Full** 🎯 | Moderate | High | Best | Maximum quality needed |

### **Step 3: Configure Parameters**
- **Dataset ID**: Enter your dataset number
- **Epochs**: Number of training passes (QLoRA: 2, LoRA: 3, Full: 5)
- **Learning Rate**: Usually 2e-4 for QLoRA, 1e-4 for LoRA
- **Batch Size**: QLoRA: 8, LoRA: 4, Full: 2

### **Step 4: Start Training**
Click "Start Training" → Monitor progress in real-time

---

## 📊 **UI Elements Guide**

### **Training Console Main View**

```
┌─────────────────────────────────────────────────────────────┐
│ Training Console                                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ [Statistics Cards]                                           │
│ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐                  │
│ │Total  │ │Running│ │Complete│ │Failed │                  │
│ │  12   │ │   2   │ │   8    │ │  2    │                  │
│ └───────┘ └───────┘ └───────┘ └───────┘                  │
│                                                              │
│ [Model Selection]                                           │
│ ( Pretrained Models ) | ( Train from Scratch )             │
│                                                              │
│ [Training Method - Visible for Pretrained Only]            │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐                       │
│ │QLoRA ⚡ │ │ LoRA 🚀│ │ Full 🎯 │                       │
│ │Selected │ │         │ │         │                       │
│ └─────────┘ └─────────┘ └─────────┘                       │
│ ✨ Recommended: QLoRA is fastest...                        │
│                                                              │
│ [Training Configuration]                                    │
│ Dataset ID: [1    ]  Base Model: [meta-llama/...]         │
│ Epochs:     [2    ]  Learning Rate: [0.0002]               │
│ Batch Size: [8    ]                                         │
│                                                              │
│ [▶ Start Training]  [⏹ Stop Monitoring]                   │
│                                                              │
│ [Active Job Status]                                         │
│ Job ID: train_abc12345                                      │
│ Status: Running  Method: QLoRA                             │
│ Progress: [████████░░░░░░░░░░] 45%                         │
│ Epoch 1/2 - Step 50/200 - Loss: 0.4321                    │
│                                                              │
│ [Training Logs]                                             │
│ ┌───────────────────────────────────────────────────┐      │
│ │ [2024-01-15 10:30:01] Training job started       │      │
│ │ [2024-01-15 10:30:05] ✨ Initializing QLoRA...  │      │
│ │ [2024-01-15 10:31:12] Step 10/200 - Loss: 0.45   │      │
│ │ [2024-01-15 10:31:18] Step 15/200 - Loss: 0.44   │      │
│ │ ...                                                │      │
│ └───────────────────────────────────────────────────┘      │
│                                                              │
│ [Job History]                                               │
│ ┌──────────┬───────────┬────────┬──────────┬───────┐       │
│ │ Job ID   │ Model     │ Dataset│ Status   │ Progress│       │
│ ├──────────┼───────────┼────────┼──────────┼───────┤       │
│ │train_abc │ llama-2-7b│ #1     │🟢Running │ 1/2   │       │
│ │train_def │ bert-base │ #2     │✅Complete│ 3/3   │       │
│ │train_xyz │ gpt2      │ #1     │❌Failed  │ 0/3   │       │
│ └──────────┴───────────┴────────┴──────────┴───────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 **Training Method Comparison**

### **QLoRA (Recommended) ⚡**
```
Memory Usage:    ████░░░░░░░░ 25% (4-8GB GPU)
Training Speed:  ██████████   100% (Fastest)
Quality:         ████████░░   80%
Training Time:   20-60 minutes (2 epochs)

✅ Best for: Quick fine-tuning, low memory systems
✅ Use when: You want fast results, limited GPU memory
```

### **LoRA 🚀**
```
Memory Usage:    ██████░░░░░░ 50% (10-14GB GPU)
Training Speed:  ████████░░   80%
Quality:         █████████░   90%
Training Time:   45-135 minutes (3 epochs)

✅ Best for: Balance between speed and quality
✅ Use when: You have decent GPU, want good results
```

### **Full Fine-tuning 🎯**
```
Memory Usage:    ████████████ 100% (16-24GB GPU)
Training Speed:  ██████░░░░   50%
Quality:         ██████████   100%
Training Time:   2.5-7.5 hours (5 epochs)

✅ Best for: Maximum model quality
✅ Use when: You need best possible results, have powerful GPU
```

---

## 📈 **Progress Indicators**

### **What You'll See During Training:**

**Initial Phase (First 30 seconds):**
```
Status: Running
[2024-01-15 10:30:01] Training job started
[2024-01-15 10:30:05] ✨ Initializing QLoRA...
[2024-01-15 10:30:08] ⚡ Expected training time: ~2-5 epochs
[2024-01-15 10:30:12] Loading model: meta-llama/Llama-2-7b-hf
[2024-01-15 10:30:25] ✓ Model loaded with 4-bit quantization
```

**Training Phase (Every 5 steps):**
```
Epoch 1/2 - Step 5/200 - Loss: 0.5234
Progress: [██░░░░░░░░░░░░░░░░░░] 5%

Epoch 1/2 - Step 10/200 - Loss: 0.4821
Progress: [███░░░░░░░░░░░░░░░░░] 10%

... continues every 5 steps ...

Epoch 2/2 - Step 195/200 - Loss: 0.3142
Progress: [█████████████████████] 97.5%
```

**Completion:**
```
[2024-01-15 11:15:45] 💾 Saving model...
[2024-01-15 11:16:02] ✅ Training completed successfully!
Status: Completed ✅
```

---

## 🎨 **Status Badge Colors**

| Badge | Color | Meaning | Action |
|-------|-------|---------|--------|
| 🟢 **Running** | Blue | Training in progress | Monitor logs |
| ✅ **Completed** | Green | Successfully finished | Download model |
| ❌ **Failed** | Red | Error occurred | Check error logs |
| 🟡 **Queued** | Yellow | Waiting to start | Be patient |
| ⏸️ **Stopped** | Gray | Manually stopped | Can delete |

---

## 🔍 **Troubleshooting**

### **Problem: Job shows "Running" but no progress**
**Solution:**
1. Check training logs for errors
2. Wait 5-10 minutes (model loading takes time)
3. Run `check_stalled_jobs()` on backend
4. Check GPU memory availability

### **Problem: "Out of Memory" error**
**Solution:**
1. Switch to QLoRA method (uses 50-75% less memory)
2. Reduce batch size: 8 → 4 → 2 → 1
3. Use smaller model variant (7B instead of 13B)

### **Problem: Training too slow**
**Solution:**
1. Switch to QLoRA (fastest method)
2. Reduce num_epochs: 5 → 3 → 2
3. Use smaller dataset for testing
4. Increase batch_size if memory allows

### **Problem: Model not learning (loss not decreasing)**
**Solution:**
1. Check dataset quality (duplicates? errors?)
2. Try different learning rate (increase or decrease 10x)
3. Increase num_epochs
4. Switch from QLoRA to LoRA or Full for better quality

---

## 📝 **Example Training Configurations**

### **Quick Test Run (5-10 minutes)**
```
Method: QLoRA
Epochs: 1
Batch Size: 8
Dataset: 100 samples
Model: distilgpt2 or bert-base-uncased
Purpose: Verify setup works
```

### **Production Fine-tuning (30-60 minutes)**
```
Method: QLoRA
Epochs: 2
Batch Size: 8
Dataset: 1000-10000 samples
Model: meta-llama/Llama-2-7b-hf or similar
Purpose: Production-ready model
```

### **High-Quality Training (2-4 hours)**
```
Method: LoRA or Full
Epochs: 5
Batch Size: 4
Dataset: 10000+ samples
Model: Any 7B-13B parameter model
Purpose: Best possible quality
```

---

## 💡 **Best Practices**

### **DO:**
- ✅ Start with QLoRA for fastest iteration
- ✅ Test with 1 epoch first to verify setup
- ✅ Monitor logs during first few steps
- ✅ Use smaller models (7B) for experimentation
- ✅ Check dataset quality before training
- ✅ Save successful configurations

### **DON'T:**
- ❌ Start with Full fine-tuning on first try
- ❌ Use very high learning rates (> 1e-3)
- ❌ Train with low-quality/duplicate data
- ❌ Run multiple heavy jobs simultaneously
- ❌ Expect immediate results (model loading takes time)

---

## 🎯 **Expected Results**

### **After Training Completes:**

**You'll have:**
- ✅ Fine-tuned model saved in `models/{job_id}/final/`
- ✅ Training logs with all steps recorded
- ✅ Loss metrics showing improvement
- ✅ Model ready for deployment or testing

**Model Performance:**
- **QLoRA:** Good results, fastest, suitable for most tasks
- **LoRA:** Better results, good balance
- **Full:** Best results, highest quality

**Next Steps:**
1. Test model with sample inputs
2. Compare with base model performance
3. Deploy if results are satisfactory
4. Iterate with different hyperparameters if needed

---

## 📞 **Quick Command Reference**

### **Frontend (UI Actions)**
- **Start Training:** Fill form → Click "Start Training"
- **Monitor Progress:** View progress bar and logs panel
- **Stop Monitoring:** Click "Stop Monitoring" (doesn't stop training, just UI polling)
- **View Job Details:** Click job in history table

### **Backend (API Endpoints)**
```bash
# Start training
POST /api/train/start
Body: { model_name, dataset_id, training_method, training_config }

# Check status
GET /api/train/status/{job_id}

# Get logs
GET /api/train/logs/{job_id}

# List all jobs
GET /api/train/jobs

# Stop job
POST /api/train/stop/{job_id}

# Delete job
DELETE /api/train/delete/{job_id}
```

---

## 🎉 **You're Ready!**

Everything is connected and working:
- ✅ UI sends correct parameters
- ✅ Backend processes training properly
- ✅ Progress updates in real-time
- ✅ Training completes successfully
- ✅ All data displayed correctly

**Recommended First Steps:**
1. Select a HuggingFace model (e.g., "distilgpt2" for testing)
2. Choose QLoRA method ⚡
3. Enter your dataset ID
4. Click "Start Training"
5. Watch the magic happen! ✨

Good luck with your training! 🚀

