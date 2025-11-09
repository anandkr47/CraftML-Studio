# ✨ Quick Reference - Docker-Style Training

## 🚀 **Start the System**

```bash
# Terminal 1: Backend
cd apps/backend
uvicorn main:app --host 127.0.0.1 --port 5000 --reload

# Terminal 2: Frontend  
cd apps/desktop
npm run dev

# Open: http://localhost:5173/train
```

---

## 🎯 **Core Features**

| Action | How To | Result |
|--------|--------|--------|
| **Start Training** | Click "Start Training" | Job in DB, logs in new tab, shows in UI |
| **View Logs** | Click [👁️] button | Opens full-screen log viewer |
| **Stop Job** | Click [⏹️] button | Job status → "stopped" |
| **Delete Job** | Click [🗑️] button | Job removed from DB |
| **Refresh Page** | F5 or refresh | Jobs still there (persistent!) |

---

## 📋 **UI Layout**

```
Training Console
├─ Active Training Jobs (running only)
├─ Stats (Total, Running, Completed, Failed)
├─ Model Selection
├─ Dataset Selection  
├─ Training Configuration
└─ Job History (all jobs with actions)
```

---

## 🔘 **Action Buttons**

| Button | Appears When | Does What |
|--------|--------------|-----------|
| [👁️] | Always | Opens log viewer |
| [⏹️] | Job is running | Stops the job |
| [🗑️] | Job stopped/completed/failed | Deletes job |

---

## 📊 **Job States**

```
running → [Stop] → stopped → [Delete] → deleted
running → (finishes) → completed → [Delete] → deleted
running → (fails) → failed → [Delete] → deleted
```

---

## 🐳 **Docker Comparison**

| Docker | CraftML |
|--------|---------|
| `docker run` | Click "Start Training" |
| `docker ps` | "Active Training Jobs" |
| `docker logs` | [👁️] button |
| `docker stop` | [⏹️] button |
| `docker rm` | [🗑️] button |

---

## ✅ **Expected Behavior**

### **When you start training:**
1. ✅ Job appears in "Active Training Jobs" immediately
2. ✅ Progress bar shows 0%
3. ✅ Epoch counter shows 0/N
4. ✅ Log viewer opens in new tab
5. ✅ Updates every 5 seconds

### **When you refresh the page:**
1. ✅ Active jobs still show
2. ✅ Progress is preserved
3. ✅ All data intact

### **When you stop a job:**
1. ✅ Moves from "Active" to history
2. ✅ Status changes to "stopped"
3. ✅ [⏹️] changes to [🗑️]

---

## 🎨 **Visual Indicators**

**Status Badges:**
- 🔵 **Running** - Blue, spinning icon
- 🟢 **Completed** - Green
- 🔴 **Failed** - Red
- 🟡 **Stopped** - Yellow

**Progress Bars:**
- Shows % complete
- Updates in real-time
- Epoch counter (e.g., "Epoch 2/3")

---

## 🚨 **Troubleshooting**

| Problem | Solution |
|---------|----------|
| Job not showing | Check backend logs, verify DB |
| Can't delete job | Must stop it first if running |
| No progress updates | Check if training actually started |
| Unicode errors | Already fixed with ASCII tags |

---

## 📁 **Key Files**

```
apps/
├─ backend/
│  ├─ api/train.py (API endpoints)
│  ├─ services/training_service.py (Business logic)
│  └─ db/models.py (Database schema)
└─ desktop/
   └─ src/pages/EnhancedTrainingConsole.tsx (UI)
```

---

## 🎯 **Success Indicators**

You know it's working when:
1. ✅ Start training → appears immediately
2. ✅ Refresh page → still there
3. ✅ Stop job → status changes
4. ✅ Delete job → disappears
5. ✅ Progress bars update automatically
6. ✅ No Unicode errors in Windows console

---

## 🎉 **That's It!**

Your training system works **exactly like Docker!**

**Enjoy!** 🚀

