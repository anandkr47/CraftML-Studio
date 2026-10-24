/**
 * Chat Studio API client (sessions, models, streamed replies).
 */

import { API_BASE } from '../config';

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
  kind: 'full' | 'lora' | 'gguf' | 'hf';
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
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.message || res.statusText);
  }
  return res.json();
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
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(typeof body.detail === 'string' ? body.detail : res.statusText);
    }
    return res.json() as Promise<{ local_path: string; size_mb: number }>;
  },

  listSessions: () => request<{ sessions: ChatSession[] }>('/sessions').then((r) => r.sessions),
  createSession: (body: SessionUpdate = {}) =>
    request<ChatSession>('/sessions', { method: 'POST', body: JSON.stringify(body) }),
  getSession: (id: string) => request<ChatSession>(`/sessions/${id}`),
  updateSession: (id: string, body: SessionUpdate) =>
    request<ChatSession>(`/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteSession: (id: string) => request<unknown>(`/sessions/${id}`, { method: 'DELETE' }),

  /** Download a session export as a file. */
  async exportSession(id: string, format: 'json' | 'markdown', title: string) {
    const res = await fetch(`${API_BASE}/api/chat/sessions/${id}/export?format=${format}`);
    if (!res.ok) throw new Error('Export failed');
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.replace(/[^\w-]+/g, '_') || 'chat'}.${format === 'markdown' ? 'md' : 'json'}`;
    a.click();
    URL.revokeObjectURL(url);
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
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }

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
