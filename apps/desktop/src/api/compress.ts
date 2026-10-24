/**
 * Compression API client.
 */

import { API_BASE } from '../config';

export type CompressionMethod = 'gguf' | 'int4' | 'int8' | 'gptq' | 'awq';

export interface Preset {
  id: string;
  title: string;
  description: string;
  method: CompressionMethod;
  quantization: string | null;
  target: string;
  estimated_size_mb?: number;
}

export interface PresetsResponse {
  presets: Preset[];
  recommended: string;
  hardware: { device_type: string; device_name: string; total_vram_gb: number };
  methods: Record<string, { label: string; needs: string; runs_on: string }>;
  gguf_quantizations: Record<string, { bits: number; note: string }>;
}

export interface Measurement {
  size_mb: number;
  memory_mb?: number;
  perplexity?: number | null;
  tokens_per_second?: number;
  load_seconds?: number;
}

export interface CompressionReport {
  model_id: string;
  output_id: string;
  output_path: string;
  method: CompressionMethod;
  quantization: string | null;
  before: Measurement;
  after: Measurement;
  size_reduction_percent: number | null;
  compression_ratio: number | null;
  speedup: number | null;
  perplexity_increase_percent?: number;
}

export interface CompressionJob {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped';
  started_at?: string | null;
  completed_at?: string | null;
  params?: { model_id: string; method: CompressionMethod; quantization: string | null; output_id: string };
  result?: CompressionReport | null;
  error?: string | null;
}

export interface CompressionJobSummary {
  job_id: string;
  status: CompressionJob['status'];
  model_id?: string;
  output_id?: string;
  method?: CompressionMethod;
  quantization?: string | null;
}

export interface ToolingStatus {
  ready: boolean;
  converter: string | null;
  quantize_binary: string | null;
  python_bindings: boolean;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : res.statusText);
  }
  return res.json();
}

export const compressApi = {
  presets: (modelId?: string) =>
    fetch(`${API_BASE}/api/compress/presets${modelId ? `?model_id=${encodeURIComponent(modelId)}` : ''}`).then((r) =>
      json<PresetsResponse>(r)
    ),
  start: (body: { model_id: string; method: CompressionMethod; quantization?: string | null; benchmark: boolean }) =>
    fetch(`${API_BASE}/api/compress/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => json<{ job_id: string }>(r)),
  status: (id: string) => fetch(`${API_BASE}/api/compress/status/${id}`).then((r) => json<CompressionJob>(r)),
  logs: (id: string, offset: number) =>
    fetch(`${API_BASE}/api/jobs/${id}/logs?offset=${offset}&limit=500`).then((r) =>
      json<{ logs: string[]; total: number }>(r)
    ),
  jobs: () =>
    fetch(`${API_BASE}/api/compress/jobs`).then((r) => json<{ jobs: CompressionJobSummary[] }>(r)).then((r) => r.jobs),
  tooling: () => fetch(`${API_BASE}/api/compress/tooling`).then((r) => json<ToolingStatus>(r)),
  setupLlamaCpp: () =>
    fetch(`${API_BASE}/api/compress/setup-llama-cpp`, { method: 'POST' }).then((r) => json<ToolingStatus>(r)),
};
