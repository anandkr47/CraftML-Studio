/**
 * Compress
 * Quantize a local model with device presets (or advanced options) and compare
 * size, memory, perplexity and speed before and after.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Download, Loader2, Play } from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { chatApi, LocalModel } from '../api/chat';
import {
  CompressionJob,
  CompressionJobSummary,
  CompressionMethod,
  CompressionReport,
  Measurement,
  PresetsResponse,
  ToolingStatus,
  compressApi,
} from '../api/compress';
import { useNotificationStore } from '../store/notificationStore';

const fieldClass =
  'w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-3 py-2 text-sm';
const labelClass = 'block text-xs font-semibold uppercase text-neutral-500 mb-1';

const fmtMb = (mb?: number | null) =>
  mb == null ? '—' : mb >= 1024 ? `${(mb / 1024).toFixed(2)} GB` : `${mb.toFixed(1)} MB`;

interface Row {
  label: string;
  before: string;
  after: string;
  note?: string;
  /** Fraction of the "after" bar relative to "before" (smaller = better for size/memory). */
  ratio?: number;
}

function reportRows(r: CompressionReport): Row[] {
  const b: Measurement = r.before;
  const a: Measurement = r.after;
  const rows: Row[] = [
    {
      label: 'File size',
      before: fmtMb(b.size_mb),
      after: fmtMb(a.size_mb),
      note: r.size_reduction_percent != null ? `${r.size_reduction_percent}% smaller` : undefined,
      ratio: b.size_mb ? a.size_mb / b.size_mb : undefined,
    },
  ];
  if (b.memory_mb != null && a.memory_mb != null) {
    rows.push({
      label: 'Memory footprint',
      before: fmtMb(b.memory_mb),
      after: fmtMb(a.memory_mb),
      ratio: b.memory_mb ? a.memory_mb / b.memory_mb : undefined,
    });
  }
  if (b.perplexity != null && a.perplexity != null) {
    rows.push({
      label: 'Perplexity (lower is better)',
      before: b.perplexity.toFixed(2),
      after: a.perplexity.toFixed(2),
      note:
        r.perplexity_increase_percent != null
          ? `${r.perplexity_increase_percent >= 0 ? '+' : ''}${r.perplexity_increase_percent}%`
          : undefined,
    });
  }
  if (b.tokens_per_second != null && a.tokens_per_second != null) {
    rows.push({
      label: 'Speed',
      before: `${b.tokens_per_second} tok/s`,
      after: `${a.tokens_per_second} tok/s`,
      note: r.speedup != null ? `${r.speedup}× faster` : undefined,
    });
  }
  return rows;
}

const Compress: React.FC = () => {
  const { success: showSuccess, error: showError } = useNotificationStore();

  const [models, setModels] = useState<LocalModel[]>([]);
  const [modelId, setModelId] = useState('');
  const [presets, setPresets] = useState<PresetsResponse | null>(null);
  const [presetId, setPresetId] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [method, setMethod] = useState<CompressionMethod>('gguf');
  const [quantization, setQuantization] = useState('Q4_K_M');
  const [benchmark, setBenchmark] = useState(true);
  const [tooling, setTooling] = useState<ToolingStatus | null>(null);
  const [settingUp, setSettingUp] = useState(false);

  const [job, setJob] = useState<CompressionJob | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [history, setHistory] = useState<CompressionJobSummary[]>([]);
  const [starting, setStarting] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const logOffset = useRef(0);

  const refreshHistory = useCallback(() => compressApi.jobs().then(setHistory).catch(() => undefined), []);

  useEffect(() => {
    chatApi.listModels().then((all) => setModels(all.filter((m) => m.kind === 'full' || m.kind === 'lora')));
    compressApi.tooling().then(setTooling).catch(() => undefined);
    refreshHistory();
    return () => window.clearTimeout(timer.current);
  }, [refreshHistory]);

  // Presets (with size estimates) follow the selected model.
  useEffect(() => {
    compressApi
      .presets(modelId || undefined)
      .then((p) => {
        setPresets(p);
        setPresetId((current) => current ?? p.recommended);
      })
      .catch((e) => showError(e.message));
  }, [modelId, showError]);

  const selectedPreset = presets?.presets.find((p) => p.id === presetId);
  const effective = advanced
    ? { method, quantization: method === 'gguf' ? quantization : null }
    : selectedPreset
    ? { method: selectedPreset.method, quantization: selectedPreset.quantization }
    : null;
  const needsLlamaCpp = effective?.method === 'gguf' && tooling && !tooling.ready;

  const poll = useCallback(async (jobId: string) => {
    try {
      const [status, newLogs] = await Promise.all([compressApi.status(jobId), compressApi.logs(jobId, logOffset.current)]);
      setJob(status);
      if (newLogs.logs.length) {
        logOffset.current += newLogs.logs.length;
        setLogs((prev) => [...prev, ...newLogs.logs]);
      }
      if (status.status === 'pending' || status.status === 'running') {
        timer.current = window.setTimeout(() => poll(jobId), 2000);
      } else {
        refreshHistory();
        chatApi.listModels().then((all) => setModels(all.filter((m) => m.kind === 'full' || m.kind === 'lora')));
        if (status.status === 'completed') showSuccess('Compression finished');
        else showError(status.error || 'Compression failed');
      }
    } catch (e) {
      showError((e as Error).message);
    }
  }, [refreshHistory, showError, showSuccess]);

  const start = async () => {
    if (!effective || !modelId) return;
    setStarting(true);
    try {
      window.clearTimeout(timer.current);
      logOffset.current = 0;
      setLogs([]);
      setJob(null);
      const { job_id } = await compressApi.start({
        model_id: modelId,
        method: effective.method,
        quantization: effective.quantization,
        benchmark,
      });
      setJob({ job_id, status: 'running' });
      poll(job_id);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const setupLlamaCpp = async () => {
    setSettingUp(true);
    try {
      setTooling(await compressApi.setupLlamaCpp());
      showSuccess('llama.cpp is ready');
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setSettingUp(false);
    }
  };

  const running = job?.status === 'running' || job?.status === 'pending';
  const report = job?.status === 'completed' ? job.result : null;

  return (
    <Container className="py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">Compress</h1>
        <p className="text-neutral-600 dark:text-neutral-400 mt-1">
          Shrink a model for your hardware. The result appears in Chat and Deploy like any other local model.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>1. Choose a model</CardTitle>
        </CardHeader>
        <CardContent>
          <select className={fieldClass} value={modelId} onChange={(e) => setModelId(e.target.value)}>
            <option value="">Select a local model…</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.kind}, {fmtMb(m.size_mb)})
              </option>
            ))}
          </select>
          {models.length === 0 && (
            <p className="text-sm text-neutral-500 mt-2">
              No compressible models yet. Fine-tune one or download a model first.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Pick a target</CardTitle>
          {presets && (
            <CardDescription>
              Detected: {presets.hardware.device_name}
              {presets.hardware.total_vram_gb ? ` · ${presets.hardware.total_vram_gb.toFixed(0)} GB` : ''}
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {!advanced && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {presets?.presets.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPresetId(p.id)}
                  className={`text-left rounded-lg border-2 p-3 ${
                    presetId === p.id ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20' : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-sm">{p.title}</span>
                    {presets.recommended === p.id && <Badge variant="success">Recommended</Badge>}
                  </div>
                  <p className="text-xs text-neutral-500 mt-1">{p.description}</p>
                  {p.estimated_size_mb != null && (
                    <p className="text-xs mt-2 font-medium">≈ {fmtMb(p.estimated_size_mb)}</p>
                  )}
                </button>
              ))}
            </div>
          )}

          <button className="text-sm text-brand-600 hover:underline" onClick={() => setAdvanced(!advanced)}>
            {advanced ? 'Use a preset instead' : 'Advanced options'}
          </button>

          {advanced && presets && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Method</label>
                <select className={fieldClass} value={method} onChange={(e) => setMethod(e.target.value as CompressionMethod)}>
                  {Object.entries(presets.methods).map(([id, m]) => (
                    <option key={id} value={id}>
                      {m.label} — {m.runs_on}
                    </option>
                  ))}
                </select>
              </div>
              {method === 'gguf' && (
                <div>
                  <label className={labelClass}>GGUF type</label>
                  <select className={fieldClass} value={quantization} onChange={(e) => setQuantization(e.target.value)}>
                    {Object.entries(presets.gguf_quantizations).map(([id, q]) => (
                      <option key={id} value={id}>
                        {id} — {q.note}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}

          {effective && effective.method !== 'gguf' && presets?.hardware.device_type !== 'cuda' && (
            <p className="text-sm text-warning-700 dark:text-warning-400">
              {presets?.methods[effective.method].label} needs an NVIDIA GPU, which wasn&apos;t detected. Use GGUF on this machine.
            </p>
          )}

          {needsLlamaCpp && (
            <div className="rounded-lg border border-warning-300 bg-warning-50 dark:bg-warning-900/20 p-3 text-sm flex items-center justify-between gap-3">
              <span>GGUF conversion needs llama.cpp. It will be downloaded once (about 30 MB, requires git).</span>
              <Button size="sm" isLoading={settingUp} onClick={setupLlamaCpp} leftIcon={<Download className="w-4 h-4" />}>
                Set up llama.cpp
              </Button>
            </div>
          )}

          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={benchmark} onChange={(e) => setBenchmark(e.target.checked)} className="accent-brand-500" />
            Measure perplexity and speed before and after (loads both models)
          </label>

          <Button onClick={start} isLoading={starting || running} disabled={!modelId || !effective || !!needsLlamaCpp} leftIcon={<Play className="w-4 h-4" />}>
            {running ? 'Compressing…' : 'Compress'}
          </Button>
        </CardContent>
      </Card>

      {(job || logs.length > 0) && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Progress</CardTitle>
              {job && (
                <Badge variant={job.status === 'completed' ? 'success' : job.status === 'failed' ? 'error' : 'default'}>
                  {job.status}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {running && (
              <p className="flex items-center gap-2 text-sm text-neutral-500">
                <Loader2 className="w-4 h-4 animate-spin" /> Working — large models can take several minutes.
              </p>
            )}
            {job?.error && <p className="text-sm text-error-600 whitespace-pre-wrap">{job.error}</p>}
            <div className="h-40 overflow-y-auto rounded-lg bg-neutral-900 p-3 font-mono text-xs text-neutral-200 space-y-0.5">
              {logs.map((line, i) => (
                <div key={i} className="whitespace-pre-wrap">{line}</div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {report && (
        <Card>
          <CardHeader>
            <CardTitle>Before vs after</CardTitle>
            <CardDescription>
              {report.model_id} → <strong>{report.output_id}</strong>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {reportRows(report).map((row) => (
              <div key={row.label}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium">{row.label}</span>
                  {row.note && <span className="text-brand-600 font-medium">{row.note}</span>}
                </div>
                {row.ratio != null ? (
                  <div className="space-y-1">
                    {[
                      ['Before', row.before, 1, 'bg-neutral-400'],
                      ['After', row.after, Math.min(row.ratio, 1), 'bg-brand-500'],
                    ].map(([name, value, frac, color]) => (
                      <div key={String(name)} className="flex items-center gap-2 text-xs">
                        <span className="w-12 text-neutral-500">{name}</span>
                        <div className="flex-1 h-3 rounded bg-neutral-100 dark:bg-neutral-800 overflow-hidden">
                          <div className={`h-full ${color}`} style={{ width: `${Number(frac) * 100}%` }} />
                        </div>
                        <span className="w-24 text-right font-mono">{value}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex gap-6 text-sm font-mono">
                    <span>Before: {row.before}</span>
                    <span>After: {row.after}</span>
                  </div>
                )}
              </div>
            ))}
            <div className="flex gap-4 pt-2 text-sm">
              <Link to="/" className="text-brand-600 underline">Chat with it</Link>
              <Link to="/deploy" className="text-brand-600 underline">Deploy it</Link>
            </div>
          </CardContent>
        </Card>
      )}

      {history.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>History</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-neutral-200 dark:divide-neutral-800 text-sm">
              {history.map((h) => (
                <li key={h.job_id} className="flex items-center justify-between py-2">
                  <button
                    className="text-brand-600 hover:underline truncate text-left"
                    onClick={() => {
                      window.clearTimeout(timer.current);
                      logOffset.current = 0;
                      setLogs([]);
                      poll(h.job_id);
                    }}
                  >
                    {h.model_id} → {h.output_id}
                  </button>
                  <Badge variant={h.status === 'completed' ? 'success' : h.status === 'failed' ? 'error' : 'default'}>{h.status}</Badge>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </Container>
  );
};

export default Compress;
