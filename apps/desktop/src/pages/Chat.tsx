/**
 * Chat Studio
 * Multi-model chat with generation controls, streaming replies,
 * persisted sessions and export.
 */

import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bot,
  BookOpen,
  Download,
  Loader2,
  MessageSquarePlus,
  Send,
  Square,
  Trash2,
  User,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { MarkdownMessage } from '../components/chat/MarkdownMessage';
import { DEFAULT_SETTINGS, chatApi } from '../api/chat';
import { ContextCheck, contextCheck } from '../api/monitor';
import { useChatStore } from '../store/chatStore';
import { useNotificationStore } from '../store/notificationStore';

const SLIDERS = [
  { key: 'temperature', label: 'Temperature', min: 0, max: 2, step: 0.05 },
  { key: 'top_p', label: 'Top-P', min: 0, max: 1, step: 0.05 },
  { key: 'top_k', label: 'Top-K', min: 0, max: 200, step: 1 },
  { key: 'repetition_penalty', label: 'Repetition penalty', min: 0.5, max: 2, step: 0.05 },
  { key: 'max_tokens', label: 'Max tokens', min: 16, max: 4096, step: 16 },
] as const;

const Chat: React.FC = () => {
  const chat = useChatStore();
  const { error: showError, success: showSuccess } = useNotificationStore();
  const [input, setInput] = useState('');
  const [busyModel, setBusyModel] = useState(false);
  const [downloadRepo, setDownloadRepo] = useState('');
  const [downloadFile, setDownloadFile] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [memoryCheck, setMemoryCheck] = useState<ContextCheck | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chat.init().catch((e) => showError(`Failed to load chat: ${e.message}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat.messages]);

  // Warn when the chosen context length is likely to run out of memory.
  useEffect(() => {
    setMemoryCheck(null);
    if (!chat.modelId) return;
    const timer = setTimeout(() => {
      // Prompt headroom + generation budget
      contextCheck(chat.modelId!, chat.settings.max_tokens + 1024)
        .then(setMemoryCheck)
        .catch(() => undefined);
    }, 500);
    return () => clearTimeout(timer);
  }, [chat.modelId, chat.settings.max_tokens]);

  const activeSession = chat.sessions.find((s) => s.id === chat.activeId);
  const selectedModel = chat.models.find((m) => m.id === chat.modelId);

  const submit = async () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    await chat.send(text);
  };

  const toggleModelLoaded = async () => {
    if (!selectedModel) return;
    setBusyModel(true);
    try {
      if (selectedModel.is_loaded) await chatApi.unloadModel(selectedModel.id);
      else await chatApi.loadModel(selectedModel.id);
      await chat.refreshModels();
      showSuccess(selectedModel.is_loaded ? 'Model unloaded' : 'Model loaded');
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setBusyModel(false);
    }
  };

  const downloadModel = async () => {
    setDownloading(true);
    try {
      const result = await chatApi.downloadModel(downloadRepo.trim(), downloadFile.trim() || undefined);
      await chat.refreshModels();
      showSuccess(`Downloaded ${downloadRepo.trim()}`, `${result.size_mb} MB`);
      setDownloadRepo('');
      setDownloadFile('');
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setDownloading(false);
    }
  };

  const exportChat = async (format: 'json' | 'markdown') => {
    if (!activeSession) return;
    try {
      await chatApi.exportSession(activeSession.id, format, activeSession.title);
    } catch (e) {
      showError((e as Error).message);
    }
  };

  return (
    <div className="flex h-full min-h-0">
      {/* Sessions */}
      <aside className="w-64 shrink-0 border-r border-neutral-200 dark:border-neutral-800 flex flex-col">
        <div className="p-3">
          <Button fullWidth size="sm" leftIcon={<MessageSquarePlus className="w-4 h-4" />} onClick={() => chat.newSession()}>
            New chat
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {chat.sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => chat.selectSession(s.id)}
              className={`group flex items-center justify-between rounded-lg px-3 py-2 cursor-pointer text-sm ${
                s.id === chat.activeId
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/20 dark:text-brand-300'
                  : 'hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300'
              }`}
            >
              <span className="truncate">{s.title}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  chat.deleteSession(s.id);
                }}
                className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-error-500"
                title="Delete chat"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
          {chat.sessions.length === 0 && (
            <p className="px-3 py-2 text-xs text-neutral-500">No conversations yet.</p>
          )}
        </div>
      </aside>

      {/* Conversation */}
      <section className="flex-1 min-w-0 flex flex-col">
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {chat.messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-neutral-500 text-center">
              <Bot className="w-12 h-12 mb-3 text-neutral-400" />
              <p className="font-medium">
                {chat.models.length ? 'Pick a model and start chatting' : 'No local models found'}
              </p>
              {chat.models.length === 0 && (
                <p className="text-sm mt-1">Use “Download a model” in the right panel, or fine-tune one.</p>
              )}
            </div>
          )}

          {chat.messages.map((m) => (
            <div key={m.id} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''}`}>
              {m.role === 'assistant' && <Bot className="w-6 h-6 mt-1 shrink-0 text-brand-500" />}
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  m.role === 'user'
                    ? 'bg-brand-500 text-white'
                    : 'bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700'
                }`}
              >
                {m.role === 'user' ? (
                  <p className="text-sm whitespace-pre-wrap">{m.content}</p>
                ) : m.content ? (
                  <MarkdownMessage content={m.content} />
                ) : (
                  <Loader2 className="w-4 h-4 animate-spin text-neutral-400" />
                )}
                {m.sources.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-neutral-200 dark:border-neutral-700 text-xs text-neutral-500 space-y-1">
                    <p className="font-medium">Sources</p>
                    {m.sources.map((s, i) => (
                      <details key={i}>
                        <summary className="cursor-pointer">
                          {s.document} · chunk {s.chunk_index}
                        </summary>
                        <p className="mt-1 whitespace-pre-wrap">{s.text}</p>
                      </details>
                    ))}
                  </div>
                )}
              </div>
              {m.role === 'user' && <User className="w-6 h-6 mt-1 shrink-0 text-neutral-400" />}
            </div>
          ))}
          <div ref={endRef} />
        </div>

        {chat.error && (
          <div className="mx-6 mb-2 rounded-lg bg-error-50 dark:bg-error-900/20 px-3 py-2 text-sm text-error-700 dark:text-error-300">
            {chat.error}
          </div>
        )}

        <div className="border-t border-neutral-200 dark:border-neutral-800 p-4">
          <div className="flex gap-2 items-end">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              rows={2}
              placeholder="Send a message (Enter to send, Shift+Enter for a new line)"
              className="flex-1 resize-none rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/50"
            />
            {chat.streaming ? (
              <Button variant="danger" onClick={chat.stop} leftIcon={<Square className="w-4 h-4" />}>
                Stop
              </Button>
            ) : (
              <Button onClick={submit} disabled={!input.trim()} leftIcon={<Send className="w-4 h-4" />}>
                Send
              </Button>
            )}
          </div>
        </div>
      </section>

      {/* Settings */}
      <aside className="w-72 shrink-0 border-l border-neutral-200 dark:border-neutral-800 overflow-y-auto p-4 space-y-5">
        <div>
          <label className="block text-xs font-semibold uppercase text-neutral-500 mb-1">Model</label>
          <select
            value={chat.modelId ?? ''}
            onChange={(e) => chat.setModel(e.target.value || null)}
            className="w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-2 py-2 text-sm"
          >
            <option value="">Select a model…</option>
            {chat.models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.kind}{m.is_loaded ? ', loaded' : ''})
              </option>
            ))}
          </select>
          {selectedModel && (
            <Button
              variant="outline"
              size="sm"
              fullWidth
              className="mt-2"
              isLoading={busyModel}
              onClick={toggleModelLoaded}
            >
              {selectedModel.is_loaded ? 'Unload from memory' : 'Load into memory'}
            </Button>
          )}
        </div>

        <details className="rounded-lg border border-neutral-200 dark:border-neutral-700 p-3" open={chat.models.length === 0}>
          <summary className="cursor-pointer text-xs font-semibold uppercase text-neutral-500">Download a model</summary>
          <div className="mt-2 space-y-2">
            <input
              value={downloadRepo}
              onChange={(e) => setDownloadRepo(e.target.value)}
              placeholder="Hugging Face repo, e.g. Qwen/Qwen2.5-0.5B-Instruct"
              className="w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-2 py-2 text-xs"
            />
            <input
              value={downloadFile}
              onChange={(e) => setDownloadFile(e.target.value)}
              placeholder="GGUF file name (optional)"
              className="w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-2 py-2 text-xs"
            />
            <Button size="sm" fullWidth isLoading={downloading} disabled={!downloadRepo.trim()} onClick={downloadModel}>
              Download
            </Button>
            {downloading && <p className="text-xs text-neutral-500">Downloading… large models can take a while.</p>}
          </div>
        </details>

        <div>
          <label className="block text-xs font-semibold uppercase text-neutral-500 mb-1">System prompt</label>
          <textarea
            value={chat.systemPrompt}
            onChange={(e) => chat.setSystemPrompt(e.target.value)}
            rows={4}
            placeholder="You are a helpful assistant."
            className="w-full resize-none rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-2 py-2 text-sm"
          />
        </div>

        <label className="flex items-start gap-2 rounded-lg border border-neutral-200 dark:border-neutral-700 p-3 cursor-pointer">
          <input
            type="checkbox"
            checked={chat.useKb}
            onChange={(e) => chat.setUseKb(e.target.checked)}
            className="mt-0.5 accent-brand-500"
          />
          <span className="text-sm">
            <span className="flex items-center gap-1 font-medium text-neutral-800 dark:text-neutral-200">
              <BookOpen className="w-4 h-4" /> Ground with Knowledge Base
            </span>
            <span className="block text-xs text-neutral-500 mt-0.5">
              Answers cite your documents.{' '}
              <Link to="/kb" className="text-brand-600 underline">
                Manage
              </Link>
            </span>
          </span>
        </label>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-neutral-500">Parameters</span>
            <button
              className="text-xs text-brand-600 hover:underline"
              onClick={() => chat.setSettings(DEFAULT_SETTINGS)}
            >
              Reset
            </button>
          </div>
          {SLIDERS.map(({ key, label, min, max, step }) => (
            <div key={key}>
              <div className="flex justify-between text-xs text-neutral-600 dark:text-neutral-400">
                <span>{label}</span>
                <span className="font-mono">{chat.settings[key]}</span>
              </div>
              <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={chat.settings[key]}
                onChange={(e) => chat.setSettings({ [key]: Number(e.target.value) })}
                className="w-full accent-brand-500"
              />
            </div>
          ))}
        </div>

        {memoryCheck?.known && memoryCheck.risk !== 'ok' && (
          <div
            className={`rounded-lg px-3 py-2 text-xs ${
              memoryCheck.risk === 'exceeds'
                ? 'bg-error-50 text-error-800 dark:bg-error-900/20 dark:text-error-300'
                : 'bg-warning-50 text-warning-800 dark:bg-warning-900/20 dark:text-warning-300'
            }`}
          >
            <strong>Memory warning.</strong> {memoryCheck.message} (needs ≈{((memoryCheck.required_mb ?? 0) / 1024).toFixed(1)} GB,{' '}
            {((memoryCheck.available_mb ?? 0) / 1024).toFixed(1)} GB free)
          </div>
        )}

        {activeSession && (
          <div className="flex gap-2">
            <Button variant="outline" size="sm" fullWidth leftIcon={<Download className="w-4 h-4" />} onClick={() => exportChat('markdown')}>
              .md
            </Button>
            <Button variant="outline" size="sm" fullWidth leftIcon={<Download className="w-4 h-4" />} onClick={() => exportChat('json')}>
              .json
            </Button>
          </div>
        )}
      </aside>
    </div>
  );
};

export default Chat;
