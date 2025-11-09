# 🎨 CraftML Studio

> **Local-first AI infrastructure management platform** for dataset crawling, model training, compression, deployment, and monitoring.

A complete desktop application built with **Tauri + React + TypeScript** (frontend) and **FastAPI + PyTorch** (backend) that lets you:
- 🕸️ Crawl the web to build custom datasets
- 🧑‍🏫 Fine-tune language models with LoRA/QLoRA
- ⚖️ Compress models using quantization, pruning, and distillation
- 🚀 Deploy models locally or to Hugging Face
- 📊 Monitor system resources and training metrics in real-time

## ✨ Features

### 🕸️ Contextual Dataset Crawling
- Async web crawling with configurable depth and page limits
- Automatic content extraction and cleaning
- Built-in deduplication
- Export to multiple formats (JSONL, CSV, Text)

### 🧑‍🏫 Model Fine-Tuning
- LoRA and QLoRA training support
- 4-bit/8-bit quantization for memory efficiency
- GPU and CPU support with automatic device detection
- Real-time training metrics and loss visualization
- Checkpoint management

### ⚖️ Model Compression
- **Quantization:** INT8, INT4, GPTQ
- **Pruning:** Magnitude-based and structured pruning
- **Distillation:** Knowledge transfer from teacher to student models
- Size comparison and quality metrics

### 🚀 Model Deployment
- **Local Deployment:** FastAPI server for instant inference
- **Hugging Face Hub:** One-click model upload
- **Hugging Face Spaces:** Deploy interactive demos
- API endpoint generation

### 📊 Resource Monitoring
- Real-time GPU utilization and memory tracking
- CPU, RAM, and disk usage monitoring
- Historical metrics with charts
- Performance analytics

### 🧩 Extensible Architecture
- Plugin system for custom features
- Modular codebase with clean separation
- Well-documented APIs
- Configuration-driven design

## 🏗️ Architecture

```
craftml-studio/
├── apps/
│   ├── desktop/          # Tauri + React + TypeScript frontend
│   └── backend/          # FastAPI + PyTorch backend
├── core/
│   ├── ml/              # Training, compression, deployment modules
│   ├── data/            # Crawler, cleaner, formatter modules
│   ├── utils/           # Logging, monitoring utilities
│   └── config/          # Configuration management
├── plugins/             # Extensible plugin system
├── resources/           # Models, datasets, templates
├── scripts/             # Build and development scripts
├── tests/              # Test suites
└── docs/               # Documentation
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Rust** (via [rustup](https://rustup.rs/))
- **Git**
- **CUDA Toolkit** (optional, for GPU support)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd CraftML-Studio
   ```

2. **Run setup script:**
   
   **Windows:**
   ```powershell
   .\scripts\setup.ps1
   ```
   
   **Linux/Mac:**
   ```bash
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (optional)
   ```

### Development

**Start the development environment:**

**Windows:**
```powershell
.\scripts\dev.ps1
```

**Linux/Mac:**
```bash
./scripts/dev.sh
```

This will:
- Start Vite dev server for the frontend
- Launch Tauri in development mode
- Auto-start the FastAPI backend

**Backend only:**
```bash
./scripts/dev.sh --backend-only
```

**Frontend only:**
```bash
./scripts/dev.sh --frontend-only
```

### Building

**Build production executable:**

**Windows:**
```powershell
.\scripts\build_desktop.ps1
```

**Linux/Mac:**
```bash
./scripts/build_desktop.sh
```

**Output:**
- Windows: `apps/desktop/src-tauri/target/release/bundle/nsis/`
- Linux: `apps/desktop/src-tauri/target/release/bundle/appimage/`
- macOS: `apps/desktop/src-tauri/target/release/bundle/dmg/`

## 📖 Documentation

- **[Setup Guide](docs/SETUP.md)** - Detailed installation and configuration
- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and components
- **[User Guide](docs/USER_GUIDE.md)** - Feature walkthroughs and workflows
- **[API Reference](docs/API_REFERENCE.md)** - Complete API documentation

## 🎯 Use Cases

### 1. Domain-Specific Chatbot
```
Crawl company docs → Clean data → Fine-tune Llama-2-7B
→ Compress with INT4 → Deploy locally
```

### 2. Code Assistant
```
Crawl GitHub repos → Format as Q&A → Train CodeLlama
→ Compress → Deploy to Hugging Face
```

### 3. RAG System
```
Crawl knowledge base → Build embeddings → Deploy retrieval API
```

### 4. Model Optimization
```
Load base model → Quantize to INT4 → Prune 30%
→ Compare performance → Deploy optimized version
```

## 🛠️ Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Desktop** | Tauri 2.0, Rust |
| **Frontend** | React 19, TypeScript, TailwindCSS, Zustand |
| **Backend** | FastAPI, Uvicorn, SQLAlchemy |
| **ML** | PyTorch, Transformers, PEFT, bitsandbytes |
| **Data** | aiohttp, BeautifulSoup4, Scrapy |
| **Monitoring** | psutil, GPUtil, Chart.js |

## 🔒 Privacy & Security

- **Local-first:** All operations run on your machine
- **No cloud dependency:** Core features work completely offline
- **Data privacy:** Your data never leaves your computer
- **Optional cloud features:** Hugging Face integration is opt-in

## 🗺️ Roadmap

- [ ] Multi-GPU training support
- [ ] Distributed training across machines
- [ ] Model versioning and registry
- [ ] Advanced AutoML capabilities
- [ ] Cloud training integration (optional)
- [ ] Model marketplace
- [ ] Collaborative workflows
- [ ] Docker deployment support

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines (coming soon).

## 📄 License

Apache 2.0 License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with amazing open-source projects:
- [Tauri](https://tauri.app/) - Desktop framework
- [React](https://react.dev/) - UI framework
- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [PyTorch](https://pytorch.org/) - ML framework
- [Hugging Face](https://huggingface.co/) - Transformers and model hub

## 📧 Support

- **Documentation:** See `docs/` folder
- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions

---

**Made with ❤️ for the AI community**
