/**
 * Fine-tuning API client: datasets, jobs, live metrics.
 */

import { API_BASE } from '../config';
import { jsonOrThrow } from './errors';

export interface DatasetInfo {
  id: string;
  name: string;
  path: string;
  extension: string;
  size_mb: number;
  created_at: string;
  // Present on upload / info responses
  num_samples?: number;
  columns?: string[];
  preview?: string[];
  problems?: string[];
  valid?: boolean;
  /** Detected layout: instruction | prompt_completion | chat | text */
  format?: string | null;
}

export type TrainingMethod = 'qlora' | 'lora' | 'full';

export interface StartJobRequest {
  cloud?: { provider: string; gpu_id?: string | null; max_runtime_minutes: number; ssh_profile?: string | null };
  model_name: string;
  dataset_path: string;
  training_method: TrainingMethod;
  lora_config?: { r: number; lora_alpha: number; lora_dropout: number };
  training_config: {
    num_epochs: number;
    batch_size: number;
    learning_rate: number;
    warmup_steps?: number;
    save_steps?: number;
    gradient_accumulation_steps?: number;
    max_seq_length?: number;
    use_4bit?: boolean;
    use_8bit?: boolean;
  };
}

export interface JobProgress {
  current_epoch: number;
  total_epochs: number;
  current_step: number;
  total_steps: number;
  loss: number | null;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped';
  started_at?: string | null;
  completed_at?: string | null;
  progress: JobProgress | null;
  params?: Partial<StartJobRequest> & Record<string, any>;
  error?: string | null;
}

export interface JobSummary {
  job_id: string;
  status: JobStatus['status'];
  started_at?: string | null;
  base_model?: string | null;
  epochs?: number | null;
  current_epoch?: number | null;
  error?: string | null;
}

export interface MetricPoint {
  step: number;
  epoch: number | null;
  loss: number | null;
  learning_rate: number | null;
  vram_gb: number | null;
}

const json = <T>(res: Response): Promise<T> => jsonOrThrow<T>(res);

const post = <T>(path: string, body?: unknown) =>
  fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((r) => json<T>(r));

export const finetuneApi = {
  uploadDataset: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return fetch(`${API_BASE}/api/dataset/upload`, { method: 'POST', body: form }).then((r) => json<DatasetInfo>(r));
  },
  listDatasets: () =>
    fetch(`${API_BASE}/api/dataset/list`).then((r) => json<{ datasets: DatasetInfo[] }>(r)).then((r) => r.datasets),
  datasetInfo: (id: string) => fetch(`${API_BASE}/api/dataset/${id}/info`).then((r) => json<DatasetInfo>(r)),
  deleteDataset: (id: string) =>
    fetch(`${API_BASE}/api/dataset/${id}`, { method: 'DELETE' }).then((r) => json<unknown>(r)),

  searchHubModels: (query: string) =>
    fetch(`${API_BASE}/api/modelhub/search?query=${encodeURIComponent(query)}&limit=10`)
      .then((r) => json<{ models: { model_id: string; downloads?: number; likes?: number }[] }>(r))
      .then((r) => r.models),

  startJob: (req: StartJobRequest) => post<{ job_id: string }>('/api/train/start', req),
  listJobs: () =>
    fetch(`${API_BASE}/api/train/jobs`).then((r) => json<{ jobs: JobSummary[] }>(r)).then((r) => r.jobs),
  jobStatus: (id: string) => fetch(`${API_BASE}/api/train/status/${id}`).then((r) => json<JobStatus>(r)),
  jobMetrics: (id: string, afterStep: number) =>
    fetch(`${API_BASE}/api/train/metrics/${id}?after_step=${afterStep}`)
      .then((r) => json<{ points: MetricPoint[] }>(r))
      .then((r) => r.points),
  jobLogs: (id: string, offset: number) =>
    fetch(`${API_BASE}/api/train/logs/${id}?limit=500&offset=${offset}`).then((r) =>
      json<{ logs: string[]; total: number }>(r)
    ),
  stopJob: (id: string) => post<unknown>(`/api/train/stop/${id}`),
  deleteJob: (id: string) =>
    fetch(`${API_BASE}/api/train/delete/${id}`, { method: 'DELETE' }).then((r) => json<unknown>(r)),
};
