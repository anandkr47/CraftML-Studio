/**
 * Deployment API client: local OpenAI-compatible server and Hugging Face export.
 */

import { API_BASE } from '../config';
import { jsonOrThrow } from './errors';

export interface LocalDeploymentRequest {
  model_id?: string | null;
  port?: number;
  api_key?: string | null;
  allow_lan?: boolean;
}

export interface LocalDeploymentResult {
  deployment_id: string;
  url: string;
  base_url: string;
  endpoints: Record<string, string>;
  auth_required: boolean;
}

export interface HuggingFaceDeploymentRequest {
  model_id: string;
  repo_name: string;
  hf_token?: string;
  private?: boolean;
  description?: string;
}

export interface DeploymentInfo {
  deployment_id: string;
  type: 'local' | 'huggingface';
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped';
  started_at?: string;
  completed_at?: string | null;
  model_id?: string | null;
  url?: string | null;
  base_url?: string | null;
  repo_url?: string | null;
  endpoints?: Record<string, string>;
  error?: string | null;
}

export interface ServerStatus {
  running: boolean;
  host: string;
  port: number;
  url: string;
  base_url: string;
  auth_required: boolean;
  model_id: string | null;
  endpoints: Record<string, string>;
}

async function json<T>(res: Response): Promise<T> {
  return jsonOrThrow<T>(res);
}

const post = <T>(path: string, body?: unknown) =>
  fetch(`${API_BASE}/api/deploy${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((r) => json<T>(r));

const get = <T>(path: string) => fetch(`${API_BASE}/api/deploy${path}`).then((r) => json<T>(r));

export const startLocalServer = (params: LocalDeploymentRequest) => post<LocalDeploymentResult>('/local', params);
export const startHuggingFaceExport = (params: HuggingFaceDeploymentRequest) =>
  post<{ deployment_id: string; status: string }>('/huggingface', params);
export const stopDeployment = (id: string) => post<{ stopped: boolean }>(`/stop/${id}`);
export const fetchDeployments = () => get<{ deployments: DeploymentInfo[] }>('/list').then((r) => r.deployments);
export const getDeploymentStatus = (id: string) => get<DeploymentInfo>(`/status/${id}`);
export const getServerStatus = () => get<{ server: ServerStatus | null }>('/endpoints').then((r) => r.server);
