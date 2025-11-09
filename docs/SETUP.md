# CraftML Studio - Setup Guide

## Prerequisites

### Required Software

1. **Python 3.11+**
   - Download from: https://www.python.org/downloads/
   - Verify: `python --version` or `python3 --version`

2. **Node.js 18+**
   - Download from: https://nodejs.org/
   - Verify: `node --version` and `npm --version`

3. **Rust**
   - Install from: https://rustup.rs/
   - Verify: `rustc --version`

4. **Git**
   - Download from: https://git-scm.com/
   - Verify: `git --version`

### Optional Software

- **CUDA Toolkit** (for GPU acceleration)
  - Download from: https://developer.nvidia.com/cuda-downloads
  - Recommended for training and inference

- **Redis** (for background tasks)
  - Windows: https://github.com/microsoftarchive/redis/releases
  - Linux/Mac: `brew install redis` or `apt install redis`

## Quick Start

### Automated Setup

**Windows:**
```powershell
.\scripts\setup.ps1
```

**Linux/Mac:**
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### Manual Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd CraftML-Studio
   ```

2. **Setup Python environment**
   ```bash
   cd apps/backend
   python -m venv venv
   
   # Windows
   .\venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   
   pip install -r requirements.txt
   cd ../..
   ```

3. **Setup Frontend**
   ```bash
   cd apps/desktop
   npm install
   cd ../..
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

## Development

### Start Development Server

**Windows:**
```powershell
.\scripts\dev.ps1
```

**Linux/Mac:**
```bash
./scripts/dev.sh
```

This will:
- Start the Vite dev server (frontend)
- Launch Tauri in dev mode
- Auto-start the FastAPI backend

### Start Backend Only

```bash
# Windows
.\scripts\dev.ps1 --backend-only

# Linux/Mac
./scripts/dev.sh --backend-only
```

### Start Frontend Only

```bash
# Windows
.\scripts\dev.ps1 --frontend-only

# Linux/Mac
./scripts/dev.sh --frontend-only
```

## Building for Production

### Build Desktop App

**Windows:**
```powershell
.\scripts\build_desktop.ps1
```

**Linux/Mac:**
```bash
./scripts/build_desktop.sh
```

The installer will be created in:
- **Windows:** `apps/desktop/src-tauri/target/release/bundle/nsis/`
- **Linux:** `apps/desktop/src-tauri/target/release/bundle/appimage/`
- **macOS:** `apps/desktop/src-tauri/target/release/bundle/dmg/`

## Project Structure

```
craftml-studio/
├── apps/
│   ├── desktop/          # Tauri + React frontend
│   └── backend/          # FastAPI backend
├── core/
│   ├── ml/              # ML modules (training, compression, deployment)
│   ├── data/            # Data modules (crawler, cleaner, formatter)
│   ├── utils/           # Shared utilities
│   └── config/          # Configuration
├── plugins/             # Plugin system (extensibility)
├── resources/           # Models, datasets, templates
├── scripts/             # Build and dev scripts
├── tests/              # Test suites
└── docs/               # Documentation
```

## Troubleshooting

### Backend won't start

1. Check Python is installed: `python --version`
2. Check dependencies are installed: `pip list`
3. Check port 5000 is available
4. Check logs in `apps/backend/logs/`

### Frontend won't start

1. Check Node.js is installed: `node --version`
2. Delete `node_modules` and reinstall: `npm install`
3. Clear cache: `npm cache clean --force`

### Tauri build fails

1. Ensure Rust is installed: `rustc --version`
2. Update Rust: `rustup update`
3. Check system dependencies for Tauri: https://tauri.app/v1/guides/getting-started/prerequisites

### GPU not detected

1. Install CUDA Toolkit
2. Install PyTorch with CUDA support:
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```
3. Verify: `python -c "import torch; print(torch.cuda.is_available())"`

## Next Steps

- Read the [Architecture Overview](./ARCHITECTURE.md)
- Check the [API Reference](./API_REFERENCE.md)
- See [User Guide](./USER_GUIDE.md) for usage instructions

## Support

For issues and questions:
- GitHub Issues: <repository-url>/issues
- Documentation: <repository-url>/docs

