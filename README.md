# CraftML Studio

A local-first desktop workspace for language models: chat with models on your own machine, ground
answers in your documents, fine-tune with LoRA/QLoRA, compress for your hardware, and serve models
through an OpenAI-compatible API. Optionally, rent a GPU from RunPod or Modal (or use your own server)
when your machine isn't big enough.

Desktop app: **Tauri 2 + React 19 + TypeScript**. Backend: **FastAPI + PyTorch** (runs locally as a sidecar).
Works on **macOS (Apple Silicon), Windows and Linux**.

## Features

| | |
|---|---|
| 💬 **Chat** | Multiple local models (Transformers, LoRA adapters, GGUF via llama.cpp) and cloud models; temperature / top-p / top-k / repetition penalty / max tokens / system prompt; streaming; markdown with highlighted, copyable code; saved sessions with Markdown/JSON export; memory warnings before a context won't fit. |
| 📚 **Knowledge Base** | Drop in PDF, DOCX, Markdown and text files; chunked and embedded locally (`bge-small-en-v1.5`); stored in SQLite with `sqlite-vec`. Turn on *Ground with Knowledge Base* in Chat for answers with cited sources. |
| 🧠 **Fine-Tune** | No-code wizard: base model → dataset (JSONL, JSON, CSV, Parquet, TXT; instruction, prompt/completion, chat or raw text) → QLoRA 4-bit, LoRA 8-bit/16-bit or full fine-tuning → live loss, learning-rate and VRAM charts, logs and automatic checkpoints. Run locally or on a remote GPU. |
| 🗜️ **Compress** | Presets (fit on 8 GB VRAM, Apple Silicon/CPU, edge, max quality) or manual: GGUF (Q8_0…Q2_K), INT8/INT4, GPTQ, AWQ. Before/after report: size, memory, perplexity, speed. |
| 🚀 **Deploy** | One-click local OpenAI-compatible server (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`) with optional API key; push to Hugging Face with a generated model card. |
| 📊 **System monitor** | Live CPU, RAM, GPU and VRAM in the status bar (NVIDIA via NVML, Apple unified memory), with alerts before memory runs out. |
| ☁️ **Cloud GPUs** | Fine-tune on RunPod, Modal or your own SSH host; use Together, Replicate, RunPod endpoints or your server for inference. Your own accounts; hard runtime limits and automatic cleanup. See [docs/CLOUD.md](docs/CLOUD.md). |

## Quick start

Prerequisites: Python 3.11 or 3.12, Node.js 20+, Rust (stable) for the desktop shell.

```bash
# macOS / Linux
./scripts/setup.sh
./scripts/dev.sh            # starts the desktop app (and the backend)
```

```powershell
# Windows (PowerShell)
.\scripts\setup.ps1
.\scripts\dev.ps1
```

Setup installs the exact tested dependency versions (`apps/backend/requirements.lock.txt`). GGUF support
(`llama-cpp-python`) is optional and installed on a best-effort basis; see [docs/SETUP.md](docs/SETUP.md).

## Project layout

```
apps/desktop/      Tauri shell (src-tauri) + React UI (src)
apps/backend/      FastAPI app: api/ (routes), services/ (logic), db/ (SQLite models)
core/              Shared Python: config, data loading, compression, deployment, cloud GPU layer
tests/             pytest suite (runs on Linux, macOS and Windows in CI)
docs/              Setup, architecture, user guide, API reference, cloud GPUs
scripts/           Setup, dev and build scripts (bash + PowerShell)
```

## Documentation

* [Setup](docs/SETUP.md) — installing, running, building, testing
* [User guide](docs/USER_GUIDE.md)
* [Architecture](docs/ARCHITECTURE.md)
* [API reference](docs/API_REFERENCE.md) (generated from the backend's OpenAPI schema)
* [Cloud GPUs](docs/CLOUD.md)

## Privacy

Everything runs on your machine by default; nothing is uploaded. Data leaves the machine only when you
choose to: downloading or publishing models on Hugging Face, chatting with a cloud model, or running a
fine-tune on a remote GPU (see [docs/CLOUD.md](docs/CLOUD.md)).

## License

Apache 2.0
