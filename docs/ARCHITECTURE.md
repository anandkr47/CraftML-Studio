# Architecture

```
┌──────────────────────────── CraftML Studio (Tauri 2) ─────────────────────────────┐
│  React 19 UI (apps/desktop/src)          Rust shell (apps/desktop/src-tauri)       │
│  Chat · Fine-Tune · Compress · KB ·      starts / supervises / stops the backend,  │
│  Deploy · Settings                        reports its state and logs to the UI     │
└───────────────┬───────────────────────────────────────────┬───────────────────────┘
                │ HTTP + SSE + WebSocket, 127.0.0.1:17860   │ spawn, health probe
┌───────────────▼───────────────────────────────────────────▼───────────────────────┐
│  Python backend (apps/backend, FastAPI)                                            │
│  api/       routes: /api/{chat,kb,train,compress,deploy,dataset,modelhub,monitor,  │
│             jobs,settings,cloud}, OpenAI-compatible /v1, /ws/monitor               │
│  services/  inference engine, chat store, RAG, training, compression, benchmark,   │
│             local API server, monitoring, jobs, cloud orchestration, HF auth       │
│  db/        SQLite (SQLAlchemy 2) + sqlite-vec                                     │
│  core/      config, dataset loading, compression/GGUF, HF export, cloud GPU layer  │
└───────────────────────────────────────────────────────────────────────────────────┘
          │ optional, user-initiated: Hugging Face Hub, cloud GPU providers
```

## Desktop shell

`src-tauri/src/backend_process.rs` owns the backend process:

* **Which backend.** Packaged builds bundle the PyInstaller one-folder build as `bin/backend.tar.gz`
  (an archive, because Tauri's resource copy would flatten the symlinks PyInstaller needs on macOS).
  It is unpacked into a per-user directory named after the build (app version plus the archive's
  size and mtime), so an update is always picked up and an interrupted unpack is never used. Debug builds (or
  `CRAFTML_BACKEND_DIR`) run `apps/backend/run_server.py` with the project's virtualenv.
* **Startup** runs on a background thread so the window appears at once. The health probe accepts only
  a response from `craftml-backend`, so another service on the port is reported, not mistaken for the
  backend. A healthy backend that is already running is reused unless it reports a different app
  version.
* **Shutdown.** The backend is stopped on app exit (SIGTERM, then kill), and on Ctrl+C, SIGTERM or
  SIGHUP sent to the app. If the app dies without cleaning up, the backend's parent watchdog
  (`CRAFTML_PARENT_PID`, checked against the parent's start time) exits on its own.
* **Visibility.** `backend_status` / `get_backend_logs` feed the loading screen, which shows the
  error, the end of the log and a Retry button when startup fails.

## Backend

**Errors.** Every error response has the shape `{"status": "error", "message", "detail", "code"}`;
validation errors get a readable `message`. Streaming endpoints end with an error event plus
`[DONE]`, never by cutting the connection.

**Local-only API.** `api/security.py` rejects requests whose `Host` isn't loopback (DNS rebinding)
and whose `Origin` isn't the app (`tauri://localhost`, `http(s)://tauri.localhost` on Windows) or
the dev server. CORS uses the same allowlist. The separate model server started from Deploy is a
different process-local server with its own optional API key.

**Jobs.** Fine-tuning and compression jobs share one store (`services/jobs.py`: `job_runs`,
`job_run_logs`, `job_run_metrics`), run in background threads, support cancellation, and are marked
failed on the next start if the backend stopped mid-run.

**Inference** (`services/inference`). The engine discovers local models (Hugging Face folders, LoRA
adapters, GGUF files) and registered cloud models, and loads them through one `Backend` protocol:

* Transformers (CUDA / MPS / CPU), with streaming and cancellation;
* llama.cpp for GGUF. Each file is first loaded in a child process (`gguf_check.py`, cached per file),
  because llama.cpp calls `abort()` on unsupported models;
* remote OpenAI-compatible and Replicate endpoints.

Models without a chat template use the same plain `User:`/`Assistant:` prompt in every backend, and
stop sequences are never part of the reply. Models already in the Hugging Face cache load without the
network (`core/utils/hub.py`).

**Knowledge base** (`services/rag`). PDF, DOCX, Markdown and text are extracted, then split into
overlapping chunks of about 800 characters. These are embedded locally with `BAAI/bge-small-en-v1.5`
and stored in SQLite, with a `sqlite-vec` index (brute force if the extension can't load). The index
repairs itself if it drifts from the chunk table. Grounded chat adds the top 4 chunks to the system
prompt and returns them as citations.

**Fine-tuning** (`services/training`). `EfficientTrainer` wraps PEFT LoRA/QLoRA (bitsandbytes 4/8-bit
on NVIDIA) or full fine-tuning on Hugging Face `Trainer`, streaming progress, loss, learning rate,
VRAM and logs into the job store. Datasets (JSONL, JSON, CSV, Parquet, TXT) are normalised by
`core/data/finetune_dataset.py`.

**Compression** (`core/ml/compression`, `services/compression_service.py`). GGUF uses llama.cpp's
converter, which the backend runs with its own interpreter, including when packaged
(`run_server.py --run-python-script`), plus llama-quantize or the bindings. INT8/INT4, GPTQ and AWQ
need an NVIDIA GPU. LoRA adapters are merged first. The before/after report compares size, memory,
perplexity and speed.

**Monitoring** (`services/monitoring`). psutil plus NVML (NVIDIA) or unified memory (Apple), pushed
over `/ws/monitor`, with RAM/VRAM pressure alerts and a "will this context fit" check.

**Cloud GPUs** (`core/cloud`, `services/cloud_service.py`). See [CLOUD.md](CLOUD.md): provider
plug-ins (RunPod, Modal, SSH; Together/Replicate/RunPod/SSH for inference), envelope-encrypted secrets
(OS keychain master key, encrypted file), pinned SSH host keys, a hash-verified worker bundle, a
versioned event protocol, hard runtime limits with remote dead-man switches, and reconciliation of
leftover remote resources on startup.

## Data

All state lives under one per-user directory (see [SETUP.md](SETUP.md#where-things-are-stored)):
`craftml.db` (jobs, chats, knowledge base, cloud runs and models), `models/`, `datasets/`, `logs/`,
`cache/`, and the encrypted secret store. Nothing leaves the machine unless the user downloads or
publishes models, chats with a cloud model, or runs a remote fine-tune.

## Repository layout

```
apps/desktop/src/          React UI: pages/, components/, api/ (typed clients), store/ (zustand)
apps/desktop/src-tauri/    Rust shell: backend launcher, Tauri config, bundled backend in bin/
apps/backend/              FastAPI app: api/, services/, db/, models/ (request/response schemas)
core/                      shared Python: config, data, ml/compression, ml/deployment, cloud, utils
tests/                     pytest (no network, no GPU); runs on Linux, macOS and Windows in CI
scripts/                   setup, dev, build, log helpers (bash + PowerShell)
craftml-backend.spec       PyInstaller spec for the packaged backend
```
