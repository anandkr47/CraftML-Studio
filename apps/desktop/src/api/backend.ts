/**
 * Backend lifecycle as seen by the UI: the Tauri shell starts the Python backend
 * (src-tauri/src/backend_process.rs) and reports its state; the health endpoint says
 * when it is ready to serve requests.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { API_BASE } from '../config';

export interface ShellBackendStatus {
  state: 'running' | 'external' | 'starting' | 'stopped' | 'failed';
  pid: number | null;
  mode: string | null;
  error: string | null;
  /** What the shell is doing while starting, e.g. unpacking the backend after an update. */
  detail: string | null;
  port: number;
}

export interface BackendLogs {
  stdout: string;
  stderr: string;
  stdout_path: string;
  stderr_path: string;
  log_dir: string;
}

export type BackendPhase =
  | { kind: 'starting'; detail: string }
  | { kind: 'ready' }
  | { kind: 'failed'; error: string };

const inTauri = () => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

/** True when our backend (not some other service on the port) answers the health check. */
export async function backendHealthy(timeoutMs = 1500): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: controller.signal });
    if (!res.ok) return false;
    const body = await res.json().catch(() => null);
    return body?.service === 'craftml-backend';
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function shellStatus(): Promise<ShellBackendStatus | null> {
  if (!inTauri()) return null; // plain browser (vite dev): the backend is started separately
  try {
    return await invoke<ShellBackendStatus>('backend_status');
  } catch {
    return null;
  }
}

export async function restartBackend(): Promise<void> {
  if (!inTauri()) return;
  await invoke<string>('start_backend');
}

export async function fetchBackendLogs(): Promise<BackendLogs | null> {
  if (!inTauri()) return null;
  try {
    return await invoke<BackendLogs>('get_backend_logs');
  } catch {
    return null;
  }
}

/**
 * Long enough for a cold first start (unpacking the backend, antivirus/Gatekeeper scans, first
 * imports); the shell waits as long. A crash is reported straight away, not after this.
 */
const GIVE_UP_MS = 600_000;

/** Polls until the backend is ready or has definitely failed; `retry` restarts it. */
export function useBackendReady(): { phase: BackendPhase; retry: () => Promise<void> } {
  const [phase, setPhase] = useState<BackendPhase>({ kind: 'starting', detail: 'Starting the backend…' });
  const generation = useRef(0);

  const poll = useCallback((gen: number) => {
    const startedAt = Date.now();
    const tick = async () => {
      if (gen !== generation.current) return;
      if (await backendHealthy()) {
        if (gen === generation.current) setPhase({ kind: 'ready' });
        return;
      }
      const status = await shellStatus();
      if (gen !== generation.current) return;
      if (status?.state === 'failed' || (status?.state === 'stopped' && status.error)) {
        setPhase({ kind: 'failed', error: status.error ?? 'The backend stopped unexpectedly.' });
        return;
      }
      if (Date.now() - startedAt > GIVE_UP_MS) {
        setPhase({ kind: 'failed', error: 'The backend did not become ready in time.' });
        return;
      }
      const detail =
        status?.detail ??
        (status?.state === 'starting' || status?.state === 'running'
          ? 'Loading models and services…'
          : 'Starting the backend…');
      setPhase({ kind: 'starting', detail });
      setTimeout(tick, 400);
    };
    tick();
  }, []);

  useEffect(() => {
    const gen = ++generation.current;
    poll(gen);
    return () => {
      generation.current++;
    };
  }, [poll]);

  const retry = useCallback(async () => {
    const gen = ++generation.current;
    setPhase({ kind: 'starting', detail: 'Restarting the backend…' });
    try {
      await restartBackend();
    } catch (e) {
      setPhase({ kind: 'failed', error: String(e) });
      return;
    }
    poll(gen);
  }, [poll]);

  return { phase, retry };
}
