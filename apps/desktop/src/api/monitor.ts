/**
 * System monitor types and REST helpers.
 */

import { API_BASE } from '../config';

export interface Alert {
  id: string;
  severity: 'warning' | 'critical';
  title: string;
  message: string;
  job_id?: string;
}

export interface GpuReading {
  kind: 'nvidia' | 'apple';
  name: string;
  util_percent: number | null;
  vram_total_mb: number;
  vram_used_mb: number;
  vram_percent: number;
  temperature_c: number | null;
  app_gpu_mb?: number | null;
}

export interface Telemetry {
  timestamp: number;
  cpu: { percent: number; count: number };
  memory: { total_mb: number; used_mb: number; percent: number };
  gpu: GpuReading | null;
  process_rss_mb: number;
  alerts: Alert[];
}

export interface ContextCheck {
  model_id: string;
  context_tokens: number;
  known: boolean;
  risk?: 'ok' | 'high' | 'exceeds';
  message?: string;
  required_mb?: number;
  available_mb?: number;
  kv_cache_mb?: number;
}

export async function contextCheck(modelId: string, context: number): Promise<ContextCheck> {
  const res = await fetch(
    `${API_BASE}/api/monitor/context-check?model_id=${encodeURIComponent(modelId)}&context=${context}`
  );
  if (!res.ok) throw new Error('Context check failed');
  return res.json();
}
