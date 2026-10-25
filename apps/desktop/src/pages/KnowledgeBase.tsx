/**
 * Knowledge Base
 * Drag-and-drop document ingestion and vector-store management for local RAG.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { FileText, Loader2, Search, Trash2, UploadCloud } from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { ChatSource } from '../api/chat';
import { KbListing, kbApi } from '../api/kb';
import { useNotificationStore } from '../store/notificationStore';
import { errorText } from '../api/errors';

const formatSize = (bytes: number) =>
  bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;

const KnowledgeBase: React.FC = () => {
  const [listing, setListing] = useState<KbListing | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ChatSource[] | null>(null);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { success: showSuccess, error: showError } = useNotificationStore();

  const refresh = useCallback(async () => {
    try {
      setListing(await kbApi.list());
    } catch (e) {
      showError(`Failed to load knowledge base: ${errorText(e)}`);
    }
  }, [showError]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const upload = async (files: File[]) => {
    if (!files.length) return;
    setUploading(true);
    try {
      const result = await kbApi.upload(files);
      if (result.documents.length) showSuccess(`Added ${result.documents.length} document(s)`);
      result.errors.forEach((e) => showError(`${e.file}: ${e.error}`));
    } catch (e) {
      showError(errorText(e));
    } finally {
      setUploading(false);
      await refresh();
    }
  };

  const remove = async (id: number) => {
    try {
      await kbApi.remove(id);
      setResults(null);
      await refresh();
    } catch (e) {
      showError(errorText(e));
    }
  };

  const runSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      setResults(await kbApi.search(query.trim()));
    } catch (e) {
      showError(errorText(e));
    } finally {
      setSearching(false);
    }
  };

  const supported = listing?.supported.join(', ') ?? '.pdf, .md, .txt, .docx';

  return (
    <Container className="py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">Knowledge Base</h1>
        <p className="text-neutral-600 dark:text-neutral-400 mt-1">
          Documents are chunked and embedded locally. Turn on “Ground with Knowledge Base” in Chat to use them.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          upload(Array.from(e.dataTransfer.files));
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
          dragging
            ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
            : 'border-neutral-300 dark:border-neutral-700 hover:border-brand-400'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          accept={listing?.supported.join(',')}
          onChange={(e) => {
            upload(Array.from(e.target.files ?? []));
            e.target.value = '';
          }}
        />
        {uploading ? (
          <Loader2 className="w-10 h-10 mx-auto animate-spin text-brand-500" />
        ) : (
          <UploadCloud className="w-10 h-10 mx-auto text-neutral-400" />
        )}
        <p className="mt-3 font-medium text-neutral-800 dark:text-neutral-200">
          {uploading ? 'Embedding documents…' : 'Drop files here or click to browse'}
        </p>
        <p className="text-sm text-neutral-500 mt-1">Supported: {supported}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Documents</CardTitle>
          <CardDescription>
            {listing
              ? `${listing.stats.documents} document(s), ${listing.stats.chunks} chunks · index: ${listing.stats.vector_index}`
              : 'Loading…'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {listing && listing.documents.length === 0 && (
            <p className="text-sm text-neutral-500">No documents yet.</p>
          )}
          <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {listing?.documents.map((d) => (
              <li key={d.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3 min-w-0">
                  <FileText className="w-5 h-5 text-neutral-400 shrink-0" />
                  <div className="min-w-0">
                    <p className="font-medium truncate text-neutral-900 dark:text-neutral-100">{d.name}</p>
                    <p className="text-xs text-neutral-500">
                      {formatSize(d.size_bytes)} · {d.num_chunks} chunks
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant="default">{d.ext}</Badge>
                  <button
                    onClick={() => remove(d.id)}
                    className="text-neutral-400 hover:text-error-500"
                    title="Remove document"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Test retrieval</CardTitle>
          <CardDescription>See which chunks would be passed to the model for a question.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runSearch()}
              placeholder="Ask something your documents can answer…"
              className="flex-1 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-3 py-2 text-sm"
            />
            <Button onClick={runSearch} isLoading={searching} leftIcon={<Search className="w-4 h-4" />}>
              Search
            </Button>
          </div>
          {results && results.length === 0 && <p className="text-sm text-neutral-500">No matches.</p>}
          {results?.map((r, i) => (
            <div key={i} className="rounded-lg border border-neutral-200 dark:border-neutral-700 p-3">
              <div className="flex justify-between text-xs text-neutral-500 mb-1">
                <span>
                  {r.document} · chunk {r.chunk_index}
                </span>
                <span className="font-mono">score {r.score?.toFixed(3)}</span>
              </div>
              <p className="text-sm whitespace-pre-wrap text-neutral-800 dark:text-neutral-200">{r.text}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </Container>
  );
};

export default KnowledgeBase;
