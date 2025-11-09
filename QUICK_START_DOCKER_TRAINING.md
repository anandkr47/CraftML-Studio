# 🚀 Quick Start: Docker-Style Training

## ✅ **Everything You Need to Know**

### **1. Start Backend**
```bash
cd apps/backend
uvicorn main:app --host 127.0.0.1 --port 5000 --reload
```

### **2. Start Frontend**
```bash
cd apps/desktop
npm run dev
```

### **3. Go to Training Console**
```
http://localhost:5173/train
```

---

## 🎯 **How It Works**

### **Training Console Layout:**
```
┌─────────────────────────────────────────┐
│ 🔄 Active Training Jobs (2)             │ ← NEW! Shows running jobs
│ ⟳ train_abc123 [Running]               │
│ Model: gpt2 • Epoch 2/3 • 67%          │
│ [View Logs] [Stop]                      │
├─────────────────────────────────────────┤
│ Stats: Total | Running | Completed      │
├─────────────────────────────────────────┤
│ [Select Model] → [Select Dataset] →...  │
├─────────────────────────────────────────┤
│ Training History:                       │
│ Job ID       Status     Actions         │
│ train_abc    Running    [👁️] [⏹️]       │ ← Can stop
│ train_def    Completed  [👁️] [🗑️]       │ ← Can delete
└─────────────────────────────────────────┘
```

---

## 📋 **User Actions**

### **Start Training:**
1. Select model (pretrained or scratch)
2. Select dataset
3. Choose method (QLoRA/LoRA/Full)
4. Configure settings
5. Click **"Start Training"**

**What Happens:**
- ✅ Job created in DB with status="running"
- ✅ Logs open in new tab
- ✅ Job appears in "Active Training Jobs" **immediately**
- ✅ Auto-refreshes every 5 seconds

---

### **View Logs:**
- Click **[👁️]** button in any job
- Opens full-screen log viewer in new tab
- Real-time updates

---

### **Stop Training:**
- Click **[⏹️]** button next to running job
- Job status changes to "stopped"
- Moves from "Active" to "History" only

---

### **Delete Job:**
- Click **[🗑️]** button next to stopped/completed/failed job
- Confirmation dialog appears
- Job removed from database

**Note:** Cannot delete running jobs - stop them first!

---

## 🐳 **Docker Comparison**

| Docker Command | CraftML Equivalent |
|----------------|-------------------|
| `docker run` | Click "Start Training" |
| `docker ps` | "Active Training Jobs" section |
| `docker ps -a` | Training History table |
| `docker logs <id>` | Click [👁️] button |
| `docker stop <id>` | Click [⏹️] button |
| `docker rm <id>` | Click [🗑️] button |
| `docker inspect <id>` | View job details in table |

---

## 🎨 **Visual Indicators**

### **Status Badges:**
- 🟢 **Running** - Blue badge, spinning icon
- 🟢 **Completed** - Green badge
- 🔴 **Failed** - Red badge  
- 🟡 **Stopped** - Yellow badge

### **Progress Bars:**
- Active jobs show real-time progress
- Updates every training step
- Shows epoch counter (e.g., "Epoch 2/3")

---

## 🔄 **Auto-Refresh**

The console **automatically updates every 5 seconds**:
- Active jobs list
- Progress bars
- Status badges
- Job history

**No need to refresh manually!**

---

## ✅ **Key Features**

1. **Persistent** - Jobs saved to DB, survive page refresh
2. **Visible** - Active jobs always shown prominently
3. **Controllable** - Stop/Delete like Docker
4. **Real-time** - Progress updates automatically
5. **Professional** - Clean, modern UI

---

## 🎯 **Expected Behavior**

### **Scenario 1: Start New Training**
```
Before: Console shows old jobs only
Click "Start Training"
After: 
  ✅ "Active Training Jobs (1)" appears
  ✅ Job shows with progress bar
  ✅ Can click "Stop" or "View Logs"
```

### **Scenario 2: Refresh Page**
```
Before: 2 jobs running
Refresh browser
After:
  ✅ "Active Training Jobs (2)" still there
  ✅ Progress bars still updating
  ✅ No data lost
```

### **Scenario 3: Stop Job**
```
Before: Job shows in "Active Training Jobs"
Click "Stop" button
After:
  ✅ Job removed from "Active" section
  ✅ Job appears in history with "Stopped" status
  ✅ [🗑️] Delete button now available
```

### **Scenario 4: Delete Job**
```
Before: Stopped job in history
Click "Delete" (trash icon)
Confirm deletion
After:
  ✅ Job removed from history
  ✅ Stats updated
  ✅ Deleted from database
```

---

## 🚨 **Troubleshooting**

### **Job not showing after start:**
- Check backend logs for errors
- Verify DB has job with status="running"
- Check browser console for API errors

### **Cannot delete job:**
- Make sure job is stopped/completed/failed
- Cannot delete running jobs (stop first)

### **Progress not updating:**
- Check if auto-refresh is working (console should update every 5s)
- Verify training is actually running in log viewer

---

## 📊 **Database Schema**

```sql
CREATE TABLE training_jobs (
    id INTEGER PRIMARY KEY,
    job_id TEXT UNIQUE,
    status TEXT,              -- "running", "stopped", "completed", "failed"
    params TEXT,              -- JSON string
    logs TEXT,
    progress TEXT,            -- JSON string
    error TEXT,
    created_at DATETIME,
    completed_at DATETIME
);
```

---

## 🎉 **Success Indicators**

You know it's working when:
1. ✅ Click "Start Training" → Job appears immediately in "Active Training Jobs"
2. ✅ Refresh page → Jobs still there
3. ✅ Click "Stop" → Job status changes to "Stopped"
4. ✅ Click "Delete" → Job disappears
5. ✅ Progress bars update automatically
6. ✅ No confusion, everything visible!

---

## 🚀 **That's It!**

Your training console now works **exactly like Docker Desktop!**

- Start jobs ✓
- View logs ✓
- Stop jobs ✓
- Delete jobs ✓
- Full persistence ✓
- Auto-refresh ✓

**Enjoy your production-ready training system! 🎉**

