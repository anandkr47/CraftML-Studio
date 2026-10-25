# API reference

Generated from the backend's OpenAPI schema by `scripts/gen_api_reference.py`; do not edit by hand.
The interactive version is served at `http://127.0.0.1:17860/docs` while the app runs.

* Base URL: `http://127.0.0.1:17860` (loopback only).
* Browser callers must send an allowed `Origin` (the desktop app's); other web pages are rejected.
* Errors: `{"status": "error", "message": <readable text>, "detail": ..., "code": ...}`.
* `/v1/*` is OpenAI-compatible (chat completions with SSE streaming, embeddings, models).

## Chat

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/chat/models` | List Models |
| `POST` | `/api/chat/models/{model_id}/load` | Load Model |
| `POST` | `/api/chat/models/{model_id}/unload` | Unload Model |
| `GET` | `/api/chat/sessions` | List Sessions |
| `POST` | `/api/chat/sessions` | Create Session |
| `DELETE` | `/api/chat/sessions/{session_id}` | Delete Session |
| `GET` | `/api/chat/sessions/{session_id}` | Get Session |
| `PATCH` | `/api/chat/sessions/{session_id}` | Update Session |
| `GET` | `/api/chat/sessions/{session_id}/export` | Export Session |
| `POST` | `/api/chat/sessions/{session_id}/export/save` | Write the export to the Downloads folder (never overwriting) and return the path. |
| `POST` | `/api/chat/sessions/{session_id}/messages/stream` | Persist the user message, stream the assistant reply as SSE, then persist it. |

## Cloud GPUs

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/cloud/instances` | Remote runs currently billing, with an estimated cost so far. |
| `POST` | `/api/cloud/instances/{provider_id}/{remote_id}/terminate` | Terminate Instance |
| `GET` | `/api/cloud/models` | List Remote Models |
| `POST` | `/api/cloud/models` | Add Remote Model |
| `DELETE` | `/api/cloud/models/{model_id}` | Delete Remote Model |
| `POST` | `/api/cloud/models/{model_id}/test` | Send a one-token request to prove the credentials, model and endpoint work together. |
| `GET` | `/api/cloud/orphans` | Provider resources named ``craftml-*`` that no active run accounts for (possibly still billing). |
| `GET` | `/api/cloud/providers` | List Providers |
| `GET` | `/api/cloud/providers/{provider_id}/catalog` | Models the provider hosts (where it publishes a list), for the model picker. |
| `DELETE` | `/api/cloud/providers/{provider_id}/credentials` | Delete Credentials |
| `PUT` | `/api/cloud/providers/{provider_id}/credentials` | Save and verify credentials. Rejected credentials are discarded and reported as 401. |
| `GET` | `/api/cloud/providers/{provider_id}/gpus` | List Gpus |
| `GET` | `/api/cloud/ssh/profiles` | List Ssh Profiles |
| `DELETE` | `/api/cloud/ssh/profiles/{name}` | Delete Ssh Profile |
| `PUT` | `/api/cloud/ssh/profiles/{name}` | Save Ssh Profile |
| `POST` | `/api/cloud/ssh/profiles/{name}/probe` | The server's host-key fingerprint and whether it is already trusted. |
| `POST` | `/api/cloud/ssh/profiles/{name}/test` | Log in and report OS, GPUs and whether the host is ready for training. |
| `POST` | `/api/cloud/ssh/profiles/{name}/trust` | Pin the host key the user verified (re-checked against the server to prevent a swap). |
| `GET` | `/api/cloud/storage` | Where credentials are kept (OS keychain vs protected file) so the UI can warn if it's the weaker option. |
| `POST` | `/api/cloud/training/estimate` | Estimate Training Cost |

## Compression

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/compress/jobs` | List Compression Jobs |
| `GET` | `/api/compress/presets` | Target-device presets (with size estimates for ``model_id``) and the hardware-recommended one. |
| `POST` | `/api/compress/setup-llama-cpp` | Download llama.cpp (shallow git clone) into the app's tools directory. |
| `POST` | `/api/compress/start` | Start Compress |
| `GET` | `/api/compress/status/{job_id}` | Compress Status |
| `GET` | `/api/compress/tooling` | Whether the llama.cpp tooling needed for GGUF is available. |

## Dataset

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/dataset/list` | List Datasets |
| `POST` | `/api/dataset/upload` | Save a dataset file and return its inspection (format, columns, preview, problems). |
| `DELETE` | `/api/dataset/{dataset_id}` | Delete Dataset |
| `GET` | `/api/dataset/{dataset_id}/info` | Dataset Info |

## Deployment

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/deploy/endpoints` | Get Active Endpoints |
| `POST` | `/api/deploy/huggingface` | Start a Hugging Face export; poll /status/{deployment_id} for completion. |
| `GET` | `/api/deploy/list` | List Active Deployments |
| `POST` | `/api/deploy/local` | Start the local OpenAI-compatible API server. |
| `GET` | `/api/deploy/status/{deployment_id}` | Deployment Status |
| `POST` | `/api/deploy/stop/{deployment_id}` | Stop Deployment Api |

## Job History

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/jobs/history` | Get Job History |
| `GET` | `/api/jobs/stats` | Get Job Stats |
| `GET` | `/api/jobs/stats/counts` | Get Job Stats |
| `DELETE` | `/api/jobs/{job_id}` | Delete Job |
| `GET` | `/api/jobs/{job_id}` | Get Job Details |
| `GET` | `/api/jobs/{job_id}/logs` | Get Job Logs |

## Knowledge Base

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/kb/documents` | List Documents |
| `POST` | `/api/kb/documents` | Ingest one or more PDF / DOCX / Markdown / TXT files. |
| `DELETE` | `/api/kb/documents/{doc_id}` | Delete Document |
| `POST` | `/api/kb/search` | Search |

## Model Hub

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/modelhub/download` | Download a model from the Hugging Face Hub into the local models directory. |
| `GET` | `/api/modelhub/local` | List locally stored models |
| `DELETE` | `/api/modelhub/local/{model_name}` | Delete a local model |
| `GET` | `/api/modelhub/local/{model_name}/info` | Get detailed information about a local model |
| `GET` | `/api/modelhub/search` | Search for models on HuggingFace Hub |

## Monitoring

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/monitor/context-check` | Estimate whether ``context`` tokens fit in memory for a local model. |
| `GET` | `/api/monitor/history` | History |
| `GET` | `/api/monitor/snapshot` | Current CPU / RAM / GPU readings plus any active alerts. |

## OpenAI Compatible

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat/completions` | Chat Completions |
| `POST` | `/v1/embeddings` | Create Embeddings |
| `GET` | `/v1/models` | List Models |

## Other

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | API root endpoint |
| `GET` | `/api/health` | Health check endpoint |

## Settings

| Method | Path | Description |
|---|---|---|
| `DELETE` | `/api/settings/hf-token` | Delete Hf Token |
| `POST` | `/api/settings/hf-token` | Verify and save a HuggingFace access token (encrypted). |
| `GET` | `/api/settings/hf-token/status` | Token status and user name (never the token itself). |

## Training

| Method | Path | Description |
|---|---|---|
| `DELETE` | `/api/train/delete/{job_id}` | Delete a training job (like Docker rm) |
| `GET` | `/api/train/job_counts` | Get training job statistics |
| `GET` | `/api/train/jobs` | List all training jobs |
| `GET` | `/api/train/logs/{job_id}` | Get training logs for a job |
| `GET` | `/api/train/metrics/{job_id}` | Logged training steps (loss, learning rate, VRAM) with step > after_step. |
| `POST` | `/api/train/start` | Start a new training job |
| `GET` | `/api/train/status/{job_id}` | Get training job status |
| `POST` | `/api/train/stop/{job_id}` | Stop a training job (like Docker stop) |

## WebSockets

| Path | Description |
|---|---|
| `/ws/monitor` | System telemetry (CPU, RAM, GPU) and memory alerts every 2 s |
| `/ws/logs/{job_id}` | A job's log lines as they are written |
| `/ws/metrics/{job_id}` | A job's status and progress whenever they change |
