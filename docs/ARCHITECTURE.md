# CraftML Studio - Architecture Overview

## System Architecture

CraftML Studio is a **local-first AI infrastructure management platform** built as a monorepo with the following architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Desktop App (Tauri)                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         React Frontend (TypeScript + Tailwind)         │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│  │  │Dashboard │ │ Crawler  │ │ Training │ │Deployment│ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │
│  │                                                        │ │
│  │  ┌────────────────────────────────────────────────┐  │ │
│  │  │    Zustand State + API Client (axios)          │  │ │
│  │  └────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Rust Backend Manager (Tauri Core)              │ │
│  │  • Auto-starts Python backend on app launch            │ │
│  │  • Manages backend process lifecycle                   │ │
│  │  • Handles IPC between frontend and Rust              │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP (127.0.0.1:5000)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python)                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  API Routes                             │ │
│  │  /api/crawler | /api/train | /api/compress | /api/...  │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Service Layer                              │ │
│  │  • Crawler Service  • Training Service                 │ │
│  │  • Compression Svc  • Deployment Service               │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                Core ML & Data Modules                   │ │
│  │  ┌─────────────────┐      ┌─────────────────┐         │ │
│  │  │   core/ml/      │      │   core/data/    │         │ │
│  │  │  • training     │      │  • crawler      │         │ │
│  │  │  • compression  │      │  • cleaner      │         │ │
│  │  │  • deployment   │      │  • formatter    │         │ │
│  │  │  • utils        │      │                 │         │ │
│  │  └─────────────────┘      └─────────────────┘         │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  ML Infrastructure                           │
│  • PyTorch + Transformers  • Local GPU/CPU                  │
│  • Hugging Face Hub        • SQLite Database                │
│  • Local File Storage      • Background Tasks (Celery)      │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
craftml-studio/
├── apps/
│   ├── desktop/              # Tauri + React application
│   │   ├── src/             # React components and pages
│   │   │   ├── api/         # API client and endpoints
│   │   │   ├── components/  # Reusable UI components
│   │   │   ├── pages/       # Route pages
│   │   │   ├── store/       # Zustand state management
│   │   │   ├── hooks/       # Custom React hooks
│   │   │   └── layout/      # Layout components
│   │   ├── src-tauri/       # Tauri Rust code
│   │   │   ├── src/
│   │   │   │   ├── lib.rs           # Main Tauri entry
│   │   │   │   ├── main.rs          # App launcher
│   │   │   │   └── backend_process.rs  # Backend manager
│   │   │   └── tauri.conf.json      # Tauri configuration
│   │   └── package.json
│   │
│   └── backend/             # FastAPI backend
│       ├── api/            # API route handlers
│       ├── services/       # Business logic services
│       ├── db/            # Database models
│       ├── tasks/         # Background tasks (Celery)
│       ├── logs/          # Application logs
│       ├── main.py        # FastAPI app entry
│       └── requirements.txt
│
├── core/                   # Shared core modules
│   ├── ml/                # Machine learning modules
│   │   ├── training/      # LoRA/QLoRA fine-tuning
│   │   ├── compression/   # Quantization, pruning, distillation
│   │   ├── deployment/    # Local API, HuggingFace deployment
│   │   └── utils/         # GPU monitoring, metrics
│   │
│   ├── data/             # Data processing modules
│   │   ├── crawler/      # Web crawling
│   │   ├── cleaner/      # Text cleaning
│   │   └── formatter/    # Dataset formatting
│   │
│   ├── utils/            # Shared utilities
│   │   └── logger.py     # Logging configuration
│   │
│   └── config/           # Configuration
│       └── settings.py   # Application settings
│
├── plugins/              # Plugin system (extensibility)
│   ├── compression/      # Custom compression methods
│   ├── exporters/        # Model exporters
│   └── datasets/         # Custom dataset loaders
│
├── resources/            # Application resources
│   ├── icons/           # App icons
│   ├── models/          # Stored models
│   ├── datasets/        # Stored datasets
│   └── templates/       # Project templates
│
├── scripts/             # Build and development scripts
│   ├── setup.sh/.ps1    # Setup scripts
│   ├── dev.sh/.ps1      # Development scripts
│   └── build_desktop.sh/.ps1  # Build scripts
│
├── tests/              # Test suites
│   ├── backend/        # Backend tests
│   ├── frontend/       # Frontend tests
│   ├── ml/            # ML module tests
│   └── integration/    # Integration tests
│
├── docs/              # Documentation
│   ├── SETUP.md       # Setup guide
│   ├── ARCHITECTURE.md # This file
│   ├── API_REFERENCE.md # API documentation
│   └── USER_GUIDE.md   # User guide
│
├── pyproject.toml      # Python project metadata
└── README.md          # Project overview
```

## Technology Stack

### Frontend (apps/desktop)
- **Framework:** React 19 + TypeScript
- **Desktop:** Tauri 2.0 (Rust)
- **Styling:** TailwindCSS + SCSS
- **State Management:** Zustand
- **Routing:** React Router DOM
- **HTTP Client:** Axios
- **Charts:** Chart.js
- **Build Tool:** Vite

### Backend (apps/backend)
- **Framework:** FastAPI
- **Server:** Uvicorn
- **Database:** SQLite (SQLAlchemy ORM)
- **Task Queue:** Celery + Redis
- **Logging:** Loguru

### ML Stack (core/ml)
- **Framework:** PyTorch
- **Transformers:** Hugging Face Transformers
- **Quantization:** bitsandbytes
- **Fine-tuning:** PEFT (LoRA/QLoRA)
- **Optimization:** Optimum
- **GPU Monitoring:** psutil, GPUtil

### Data Stack (core/data)
- **Crawling:** aiohttp, BeautifulSoup4
- **Processing:** Python standard library
- **Formats:** JSONL, CSV, Parquet

## Component Communication

### Frontend ↔ Backend
- **Protocol:** HTTP REST API
- **Endpoint:** `http://127.0.0.1:5000/api/*`
- **Format:** JSON
- **Authentication:** None (local-only)

### Frontend ↔ Tauri
- **Protocol:** IPC (Inter-Process Communication)
- **Commands:** `start_backend`, `stop_backend`, `backend_status`
- **Format:** JSON

### Backend ↔ Core Modules
- **Import:** Direct Python imports
- **Location:** Core modules added to Python path

## Key Features

### 1. Contextual Data Crawling
- **Module:** `core/data/crawler`
- **Features:**
  - Async web crawling
  - Content deduplication
  - Configurable depth and page limits
  - Automatic content extraction

### 2. Model Fine-Tuning
- **Module:** `core/ml/training`
- **Features:**
  - LoRA/QLoRA training
  - 4-bit/8-bit quantization
  - GPU/CPU support
  - Progress tracking

### 3. Model Compression
- **Module:** `core/ml/compression`
- **Methods:**
  - INT8/INT4 quantization
  - GPTQ quantization
  - Magnitude pruning
  - Knowledge distillation

### 4. Model Deployment
- **Module:** `core/ml/deployment`
- **Options:**
  - Local FastAPI server
  - Hugging Face Hub upload
  - Hugging Face Spaces

### 5. Resource Monitoring
- **Module:** `core/ml/utils`
- **Metrics:**
  - GPU utilization and memory
  - CPU usage
  - System memory
  - Disk usage

## Data Flow

### Training Workflow
```
User Input (Frontend)
  → API Request (/api/train/start)
  → Training Service
  → LoRA Trainer (core/ml/training)
  → PyTorch Training Loop
  → Save Model
  → Update Status
  → Notify Frontend
```

### Crawling Workflow
```
User Input (URLs + Config)
  → API Request (/api/crawler/start)
  → Crawler Service
  → Web Crawler (core/data/crawler)
  → Fetch Pages (async)
  → Clean Text (core/data/cleaner)
  → Format Dataset (core/data/formatter)
  → Save to Disk
  → Update Status
```

### Compression Workflow
```
Select Model
  → Choose Method (quantize/prune/distill)
  → API Request (/api/compress/start)
  → Compression Service
  → Compression Engine (core/ml/compression)
  → Save Compressed Model
  → Show Size Comparison
```

## Security Considerations

### Local-First Design
- All operations run locally
- No cloud dependency for core features
- Data never leaves the machine (unless explicitly deployed)

### Network
- Backend binds to `127.0.0.1` (localhost only)
- No external network access required
- CORS configured for Tauri origin

### File System
- Models and datasets stored in user-controlled directories
- Configurable paths via environment variables

## Performance Optimizations

### Frontend
- Lazy loading of pages
- Memoized components
- Virtual scrolling for large lists
- Debounced API calls

### Backend
- Async request handling (FastAPI)
- Background task processing (Celery)
- Database connection pooling
- Response caching

### ML
- Mixed precision training (FP16)
- Gradient checkpointing
- LoRA for efficient fine-tuning
- Quantization for reduced memory

## Extensibility

### Plugin System
- Custom compression algorithms
- Custom dataset loaders
- Custom model exporters
- Custom training strategies

### Configuration
- Environment-based settings
- Runtime configuration updates
- User preferences storage

## Future Enhancements

1. **Cloud Integration** (optional)
   - Remote training on cloud GPUs
   - Model registry sync
   - Collaborative workflows

2. **Advanced Features**
   - Multi-GPU training
   - Distributed training
   - Model versioning
   - A/B testing

3. **UI/UX**
   - Dark/light themes
   - Customizable layouts
   - Keyboard shortcuts
   - Command palette

4. **ML Features**
   - More compression methods
   - AutoML capabilities
   - Hyperparameter tuning
   - Model ensembling

