# CraftML Studio - Complete Project Structure

## Monorepo Layout

```
craftml-studio/
│
├── 📱 apps/                           # Application layer
│   ├── desktop/                       # Tauri + React desktop app
│   │   ├── src/                      # React source code
│   │   │   ├── api/                  # API client
│   │   │   │   └── apiClient.ts     # Unified API client
│   │   │   ├── components/           # Reusable components
│   │   │   │   ├── LogsPanel.tsx
│   │   │   │   ├── ModelHubPanel.tsx
│   │   │   │   ├── Navbar.tsx
│   │   │   │   └── ResourceMonitor.tsx
│   │   │   ├── hooks/               # Custom React hooks
│   │   │   │   └── useBackend.ts    # Backend process hook
│   │   │   ├── layout/              # Layout components
│   │   │   │   ├── Header.tsx
│   │   │   │   └── Sidebar.tsx
│   │   │   ├── pages/               # Route pages
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── CrawlerManager.tsx
│   │   │   │   ├── DatasetManager.tsx
│   │   │   │   ├── TrainingConsole.tsx
│   │   │   │   ├── CompressionPlayground.tsx
│   │   │   │   ├── DeploymentConsole.tsx
│   │   │   │   └── NotFound.tsx
│   │   │   ├── store/               # State management
│   │   │   │   └── jobStore.ts      # Zustand job store
│   │   │   ├── App.tsx
│   │   │   └── main.tsx
│   │   ├── src-tauri/               # Tauri Rust code
│   │   │   ├── src/
│   │   │   │   ├── backend_process.rs  # Backend manager
│   │   │   │   ├── lib.rs              # Library entry
│   │   │   │   └── main.rs             # App launcher
│   │   │   ├── icons/
│   │   │   ├── tauri.conf.json      # Tauri config
│   │   │   └── Cargo.toml
│   │   ├── dist/                    # Built frontend
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.cjs
│   │   └── tsconfig.json
│   │
│   └── backend/                      # FastAPI backend
│       ├── api/                     # API route handlers
│       │   ├── crawler.py          # Crawler endpoints
│       │   ├── train.py            # Training endpoints
│       │   ├── compress.py         # Compression endpoints
│       │   ├── deploy.py           # Deployment endpoints
│       │   ├── monitor.py          # Monitoring endpoints
│       │   ├── dataset.py          # Dataset endpoints
│       │   └── modelhub.py         # Model hub endpoints
│       ├── services/                # Business logic
│       │   ├── crawler_service.py
│       │   ├── training_service.py
│       │   ├── compression_service.py
│       │   └── deployment_service.py
│       ├── db/                      # Database
│       │   └── models.py           # SQLAlchemy models
│       ├── tasks/                   # Background tasks
│       │   └── tasks.py            # Celery tasks
│       ├── logs/                    # Log files
│       ├── main.py                 # FastAPI app entry
│       ├── worker.py               # Celery worker
│       └── requirements.txt         # Python dependencies
│
├── 🧠 core/                          # Core modules (shared)
│   ├── ml/                          # Machine learning modules
│   │   ├── training/
│   │   │   ├── finetune_lora.py   # LoRA/QLoRA training
│   │   │   └── __init__.py
│   │   ├── compression/
│   │   │   ├── quantization.py    # INT4/INT8/GPTQ quantization
│   │   │   ├── pruning.py         # Magnitude/structured pruning
│   │   │   ├── distillation.py    # Knowledge distillation
│   │   │   └── __init__.py
│   │   ├── deployment/
│   │   │   ├── local_api.py       # Local FastAPI deployment
│   │   │   ├── huggingface_deploy.py  # HF Hub deployment
│   │   │   └── __init__.py
│   │   ├── utils/
│   │   │   ├── gpu_monitor.py     # GPU/system monitoring
│   │   │   ├── metrics.py         # Training metrics
│   │   │   └── __init__.py
│   │   └── __init__.py
│   │
│   ├── data/                        # Data processing modules
│   │   ├── crawler/
│   │   │   ├── web_crawler.py     # Async web crawler
│   │   │   └── __init__.py
│   │   ├── cleaner/
│   │   │   ├── text_cleaner.py    # Text cleaning
│   │   │   └── __init__.py
│   │   ├── formatter/
│   │   │   ├── jsonl_writer.py    # Dataset formatting
│   │   │   └── __init__.py
│   │   └── __init__.py
│   │
│   ├── utils/                       # Shared utilities
│   │   ├── logger.py               # Logging setup
│   │   └── __init__.py
│   │
│   └── config/                      # Configuration
│       ├── settings.py             # App settings
│       └── __init__.py
│
├── 🧩 plugins/                       # Plugin system
│   ├── compression/                 # Custom compression plugins
│   ├── exporters/                   # Custom model exporters
│   └── datasets/                    # Custom dataset loaders
│
├── 📦 resources/                     # Application resources
│   ├── icons/                       # App icons
│   ├── models/                      # Stored models
│   ├── datasets/                    # Stored datasets
│   └── templates/                   # Project templates
│
├── 🔧 scripts/                       # Build & dev scripts
│   ├── setup.sh                     # Setup script (Linux/Mac)
│   ├── setup.ps1                    # Setup script (Windows)
│   ├── dev.sh                       # Dev script (Linux/Mac)
│   ├── dev.ps1                      # Dev script (Windows)
│   ├── build_desktop.sh             # Build script (Linux/Mac)
│   └── build_desktop.ps1            # Build script (Windows)
│
├── 🧪 tests/                         # Test suites
│   ├── backend/                     # Backend tests
│   ├── frontend/                    # Frontend tests
│   ├── ml/                          # ML module tests
│   └── integration/                 # Integration tests
│
├── 📚 docs/                          # Documentation
│   ├── SETUP.md                     # Setup guide
│   ├── ARCHITECTURE.md              # Architecture overview
│   ├── USER_GUIDE.md                # User guide
│   └── API_REFERENCE.md             # API documentation
│
├── 📄 Configuration Files
│   ├── .env.example                 # Environment template
│   ├── pyproject.toml               # Python project config
│   ├── docker-compose.yml           # Docker compose
│   └── README.md                    # Main README
│
└── 🗑️ Legacy (to be removed after verification)
    ├── frontend/                    # Old frontend (copied to apps/desktop)
    └── backend/                     # Old backend (copied to apps/backend)
```

## Key Components

### Frontend (apps/desktop)
- **Framework:** React 19 + TypeScript + Vite
- **Desktop:** Tauri 2.0 (Rust)
- **Styling:** TailwindCSS + SCSS
- **State:** Zustand
- **API:** Axios client
- **Routing:** React Router

### Backend (apps/backend)
- **Framework:** FastAPI
- **Server:** Uvicorn
- **Database:** SQLite + SQLAlchemy
- **Tasks:** Celery + Redis
- **Logging:** Loguru

### Core Modules
- **ML:** Training, compression, deployment, monitoring
- **Data:** Crawling, cleaning, formatting
- **Utils:** Logging, configuration
- **Config:** Centralized settings

## Communication Flow

```
Desktop UI (React)
    ↓ Tauri IPC
Rust Backend Manager
    ↓ HTTP (127.0.0.1:5000)
FastAPI Backend
    ↓ Import
Core Modules (ML & Data)
    ↓ Execute
PyTorch / Web APIs
```

## Build Outputs

### Development
- Frontend: `http://localhost:1420` (Vite dev server)
- Backend: `http://127.0.0.1:5000` (Uvicorn)
- Auto-reload: Enabled for both

### Production
- **Windows:** `.exe` installer (NSIS)
- **Linux:** `.AppImage` package
- **macOS:** `.dmg` installer

All bundled with:
- Python backend
- Core ML/data modules
- Required resources
- Pre-configured settings

## Next Steps

1. **Verify Setup:**
   ```bash
   ./scripts/setup.sh  # or setup.ps1 on Windows
   ```

2. **Start Development:**
   ```bash
   ./scripts/dev.sh    # or dev.ps1 on Windows
   ```

3. **Build for Production:**
   ```bash
   ./scripts/build_desktop.sh  # or build_desktop.ps1 on Windows
   ```

4. **Clean Up Old Directories:**
   After verifying everything works, you can remove:
   - `frontend/` (copied to `apps/desktop/`)
   - `backend/` (copied to `apps/backend/`)

## Plugin Development

To extend functionality:

1. **Create plugin in appropriate directory:**
   - `plugins/compression/` for compression methods
   - `plugins/exporters/` for model export formats
   - `plugins/datasets/` for data loaders

2. **Follow plugin interface:**
   ```python
   class MyPlugin:
       def __init__(self, config):
           pass
       
       def execute(self, *args, **kwargs):
           pass
   ```

3. **Register in backend:**
   Add to plugin registry in backend service

## Environment Variables

See `.env.example` for all available configuration options:
- API settings (host, port)
- Database configuration
- ML settings (device, batch size)
- Crawler settings (depth, pages)
- Paths (models, datasets, logs)

## Support

- **Docs:** See `docs/` folder
- **Issues:** GitHub Issues
- **API:** See `docs/API_REFERENCE.md`

