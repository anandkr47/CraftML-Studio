/**
 * Chat Studio API client (sessions, models, streamed replies).
 */

import { API_BASE } from '../config';
import { httpError, jsonOrThrow } from './errors';

export interface GenerationSettings {
  temperature: number;
  top_p: number;
  top_k: number;
  repetition_penalty: number;
  max_tokens: number;
}

export const DEFAULT_SETTINGS: GenerationSettings = {
  temperature: 0.7,
  top_p: 0.9,
  top_k: 50,
  repetition_penalty: 1.1,
  max_tokens: 512,
};

export interface ChatSource {
  document: string;
  chunk_index: number;
  text: string;
  score?: number;
}

export interface ChatMessage {
  id: number | string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  sources: ChatSource[];
  created_at?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  model_id: string | null;
  system_prompt: string;
  params: GenerationSettings;
  use_kb: boolean;
  created_at: string;
  updated_at: string;
  messages?: ChatMessage[];
}

export interface LocalModel {
  id: string;
  name: string;
  path: string;
  kind: 'full' | 'lora' | 'gguf' | 'hf' | 'remote';
  size_mb: number;
  is_loaded: boolean;
}

export interface SessionUpdate {
  title?: string;
  model_id?: string | null;
  system_prompt?: string;
  params?: GenerationSettings;
  use_kb?: boolean;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/chat${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  return jsonOrThrow<T>(res);
}

export const chatApi = {
  listModels: () => request<{ models: LocalModel[] }>('/models').then((r) => r.models),
  loadModel: (id: string) => request<{ device: string }>(`/models/${id}/load`, { method: 'POST' }),
  unloadModel: (id: string) => request<unknown>(`/models/${id}/unload`, { method: 'POST' }),

  /** Download a model (or a single file, e.g. a .gguf) from Hugging Face into the models folder. */
  downloadModel: async (repo: string, filename?: string) => {
    const res = await fetch(`${API_BASE}/api/modelhub/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_name: repo, filename: filename || null }),
    });
    return jsonOrThrow<{ local_path: string; size_mb: number }>(res);
  },

  listSessions: () => request<{ sessions: ChatSession[] }>('/sessions').then((r) => r.sessions),
  createSession: (body: SessionUpdate = {}) =>
    request<ChatSession>('/sessions', { method: 'POST', body: JSON.stringify(body) }),
  getSession: (id: string) => request<ChatSession>(`/sessions/${id}`),
  updateSession: (id: string, body: SessionUpdate) =>
    request<ChatSession>(`/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteSession: (id: string) => request<unknown>(`/sessions/${id}`, { method: 'DELETE' }),

  /**
   * Export a session. In the desktop app the backend writes it to the Downloads folder (blob
   * downloads aren't reliable in every OS webview); in a plain browser it downloads normally.
   * Returns where it went, for the toast.
   */
  async exportSession(id: string, format: 'json' | 'markdown', title: string): Promise<string> {
    if (typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window) {
      const res = await fetch(`${API_BASE}/api/chat/sessions/${id}/export/save?format=${format}`, { method: 'POST' });
      return (await jsonOrThrow<{ path: string }>(res)).path;
    }
    const res = await fetch(`${API_BASE}/api/chat/sessions/${id}/export?format=${format}`);
    if (!res.ok) throw await httpError(res);
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.replace(/[^\w-]+/g, '_') || 'chat'}.${format === 'markdown' ? 'md' : 'json'}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    return 'your downloads';
  },
};

export interface StreamHandlers {
  onDelta: (text: string) => void;
  onDone: (info: { message_id: number; sources: ChatSource[]; finish_reason: string }) => void;
}

/**
 * Send a message and consume the SSE reply. Resolves when the stream ends;
 * aborting via ``signal`` stops generation server-side (partial reply is saved).
 */
export async function streamReply(
  sessionId: string,
  body: { content: string } & SessionUpdate,
  handlers: StreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw await httpError(res);
  if (!res.body) throw new Error('The server sent no response body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary: number;
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const event = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (!event.startsWith('data: ')) continue;

      const data = event.slice(6);
      if (data === '[DONE]') return;
      const payload = JSON.parse(data);

      if (payload.object === 'craftml.error') throw new Error(payload.message);
      if (payload.object === 'craftml.done') handlers.onDone(payload);
      else {
        const delta = payload.choices?.[0]?.delta?.content;
        if (delta) handlers.onDelta(delta);
      }
    }
  }
}
