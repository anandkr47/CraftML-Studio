/**
 * Cloud GPU API client. Credentials are write-only: no call here ever returns a secret.
 */

import { API_BASE } from '../config';
import { messageFromBody } from './errors';

export type ProviderId = 'runpod' | 'modal' | 'together' | 'replicate' | 'ssh';

export interface FieldSpec {
  name: string;
  label: string;
  secret: boolean;
  multiline: boolean;
  required: boolean;
  placeholder?: string | null;
}

export interface ProviderInfo {
  id: ProviderId;
  label: string;
  description: string;
  capabilities: { training: boolean; inference: boolean };
  fields: FieldSpec[];
  configured: boolean;
}

export interface GpuOption {
  id: string;
  name: string;
  vram_gb: number;
  price_per_hour: number | null;
  available: boolean;
}

export interface CloudTarget {
  provider: ProviderId;
  gpu_id?: string | null;
  max_runtime_minutes: number;
  ssh_profile?: string | null;
}

export interface CostEstimate {
  provider: ProviderId;
  gpu: string | null;
  price_per_hour: number | null;
  max_runtime_minutes: number;
  worst_case_cost: number | null;
  note: string;
}

export interface ActiveRun {
  job_id: string;
  provider: ProviderId;
  remote_id: string;
  gpu: string | null;
  price_per_hour: number | null;
  started_at: number;
  estimated_cost: number | null;
}

export interface Orphan {
  provider: ProviderId;
  remote_id: string;
  name: string;
  status: string;
  gpu?: string | null;
  price_per_hour?: number | null;
}

export interface SshProfile {
  name: string;
  host: string;
  port: number;
  username: string;
  runtime: 'venv' | 'docker';
  workdir: string;
  inference_port: number | null;
  host_key_pinned: boolean;
}

export interface SshProfileInput {
  host: string;
  port: number;
  username: string;
  runtime: 'venv' | 'docker';
  workdir: string;
  inference_port: number | null;
  private_key?: string;
  passphrase?: string;
}

export interface HostProbe {
  host: string;
  port: number;
  key_type: string;
  fingerprint: string;
  status: 'trusted' | 'unknown' | 'changed';
}

export interface HostTest {
  os: string;
  gpus: { name: string; vram_gb: number }[];
  docker: boolean;
  ready: boolean;
}

export interface RemoteModel {
  id: string;
  provider: ProviderId;
  name: string;
  remote_model: string;
  base_url?: string | null;
  endpoint_id?: string | null;
}

export interface CatalogModel {
  id: string;
  name: string;
  context_length: number | null;
}

export class CloudApiError extends Error {
  constructor(message: string, public code?: string, public status?: number, public fingerprint?: string, public changed?: boolean) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/cloud${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new CloudApiError(messageFromBody(body, res.statusText || `HTTP ${res.status}`), body.code, res.status, body.fingerprint, body.changed);
  }
  return res.json();
}

const send = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export const cloudApi = {
  providers: () => call<ProviderInfo[]>('/providers'),
  storage: () => call<{ backend: 'keychain' | 'file'; secure: boolean; detail: string }>('/storage'),
  saveCredentials: (id: ProviderId, values: Record<string, string>) =>
    call<{ configured: boolean; account: { name: string; detail?: string } }>(`/providers/${id}/credentials`, send('PUT', { values })),
  removeCredentials: (id: ProviderId) => call<{ configured: boolean }>(`/providers/${id}/credentials`, send('DELETE')),
  gpus: (id: ProviderId) => call<GpuOption[]>(`/providers/${id}/gpus`),
  catalog: (id: ProviderId) => call<{ models: CatalogModel[] }>(`/providers/${id}/catalog`).then((r) => r.models),
  estimate: (target: CloudTarget) => call<CostEstimate>('/training/estimate', send('POST', target)),

  runs: () => call<{ runs: ActiveRun[] }>('/instances').then((r) => r.runs),
  orphans: () => call<Orphan[]>('/orphans'),
  terminate: (provider: ProviderId, remoteId: string) =>
    call<{ terminated: boolean }>(`/instances/${provider}/${encodeURIComponent(remoteId)}/terminate`, send('POST')),

  sshProfiles: () => call<{ profiles: SshProfile[] }>('/ssh/profiles').then((r) => r.profiles),
  saveSshProfile: (name: string, input: SshProfileInput) => call<{ saved: boolean }>(`/ssh/profiles/${name}`, send('PUT', input)),
  deleteSshProfile: (name: string) => call<{ deleted: boolean }>(`/ssh/profiles/${name}`, send('DELETE')),
  probeSshHost: (name: string) => call<HostProbe>(`/ssh/profiles/${name}/probe`, send('POST')),
  trustSshHost: (name: string, keyType: string, fingerprint: string) =>
    call<HostProbe>(`/ssh/profiles/${name}/trust`, send('POST', { key_type: keyType, fingerprint })),
  testSshHost: (name: string) => call<HostTest>(`/ssh/profiles/${name}/test`, send('POST')),

  models: () => call<RemoteModel[]>('/models'),
  addModel: (m: { provider: ProviderId; name: string; remote_model: string; endpoint_id?: string | null }) =>
    call<RemoteModel>('/models', send('POST', m)),
  testModel: (id: string) => call<{ ok: boolean; detail: string }>(`/models/${id}/test`, send('POST')),
  deleteModel: (id: string) => call<{ deleted: boolean }>(`/models/${id}`, send('DELETE')),
};

export const money = (value: number | null | undefined) => (value == null ? '—' : `$${value.toFixed(2)}`);
