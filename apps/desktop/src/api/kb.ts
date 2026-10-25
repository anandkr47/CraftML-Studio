/**
 * Knowledge Base API client.
 */

import { API_BASE } from '../config';
import { jsonOrThrow } from './errors';
import type { ChatSource } from './chat';

export interface KbDocument {
  id: number;
  name: string;
  ext: string;
  size_bytes: number;
  num_chunks: number;
  created_at: string | null;
}

export interface KbStats {
  documents: number;
  chunks: number;
  vector_index: 'sqlite-vec' | 'brute-force';
}

export interface KbListing {
  documents: KbDocument[];
  stats: KbStats;
  supported: string[];
}

export interface UploadResult {
  documents: KbDocument[];
  errors: { file: string; error: string }[];
}

const parse = <T>(res: Response): Promise<T> => jsonOrThrow<T>(res);

export const kbApi = {
  list: () => fetch(`${API_BASE}/api/kb/documents`).then((r) => parse<KbListing>(r)),

  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append('files', f));
    return fetch(`${API_BASE}/api/kb/documents`, { method: 'POST', body: form }).then((r) =>
      parse<UploadResult>(r)
    );
  },

  remove: (id: number) =>
    fetch(`${API_BASE}/api/kb/documents/${id}`, { method: 'DELETE' }).then((r) => parse<unknown>(r)),

  search: (query: string, top_k = 4) =>
    fetch(`${API_BASE}/api/kb/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k }),
    })
      .then((r) => parse<{ results: ChatSource[] }>(r))
      .then((r) => r.results),
};
