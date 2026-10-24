/**
 * Deploy & Endpoints
 * Run a local OpenAI-compatible API server and export models to Hugging Face.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Copy, ExternalLink, Play, Square, UploadCloud } from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { chatApi, LocalModel } from '../api/chat';
import {
  fetchDeployments,
  getDeploymentStatus,
  getServerStatus,
  startHuggingFaceExport,
  startLocalServer,
  stopDeployment,
} from '../api/deployment';
import type { DeploymentInfo, ServerStatus } from '../api/deployment';
import { useNotificationStore } from '../store/notificationStore';

const fieldClass =
  'w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-3 py-2 text-sm';
const labelClass = 'block text-xs font-semibold uppercase text-neutral-500 mb-1';

const CopyButton: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="text-neutral-400 hover:text-brand-500"
      title="Copy"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
    </button>
  );
};

const statusVariant = (status: string) =>
  status === 'completed' || status === 'running' ? 'success' : status === 'failed' ? 'error' : 'default';

const DeploymentConsole: React.FC = () => {
  const { success: showSuccess, error: showError } = useNotificationStore();

  const [models, setModels] = useState<LocalModel[]>([]);
  const [server, setServer] = useState<ServerStatus | null>(null);
  const [history, setHistory] = useState<DeploymentInfo[]>([]);

  // Local server form
  const [serverModel, setServerModel] = useState('');
  const [port, setPort] = useState(5001);
  const [apiKey, setApiKey] = useState('');
  const [allowLan, setAllowLan] = useState(false);
  const [serverDeploymentId, setServerDeploymentId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  // Hugging Face form
  const [hfModel, setHfModel] = useState('');
  const [repoName, setRepoName] = useState('');
  const [isPrivate, setIsPrivate] = useState(false);
  const [description, setDescription] = useState('');
  const [hfToken, setHfToken] = useState('');
  const [exportJob, setExportJob] = useState<DeploymentInfo | null>(null);
  const pollRef = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      const [m, s, h] = await Promise.all([chatApi.listModels(), getServerStatus(), fetchDeployments()]);
      setModels(m);
      setServer(s);
      setHistory(h);
    } catch (e) {
      showError(`Failed to load deployment data: ${(e as Error).message}`);
    }
  }, [showError]);

  useEffect(() => {
    refresh();
    return () => window.clearInterval(pollRef.current);
  }, [refresh]);

  const startServer = async () => {
    setStarting(true);
    try {
      const result = await startLocalServer({
        model_id: serverModel || null,
        port,
        api_key: apiKey || null,
        allow_lan: allowLan,
      });
      setServerDeploymentId(result.deployment_id);
      showSuccess('API server started', result.base_url);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setStarting(false);
      refresh();
    }
  };

  const stopServer = async () => {
    try {
      const running = history.find((d) => d.type === 'local' && d.status === 'running');
      const id = serverDeploymentId ?? running?.deployment_id;
      if (id) await stopDeployment(id);
      setServerDeploymentId(null);
      showSuccess('API server stopped');
    } catch (e) {
      showError((e as Error).message);
    } finally {
      refresh();
    }
  };

  const exportToHub = async () => {
    try {
      const { deployment_id } = await startHuggingFaceExport({
        model_id: hfModel,
        repo_name: repoName.trim(),
        private: isPrivate,
        description: description || undefined,
        hf_token: hfToken || undefined,
      });
      setExportJob({ deployment_id, type: 'huggingface', status: 'running' });

      window.clearInterval(pollRef.current);
      pollRef.current = window.setInterval(async () => {
        const info = await getDeploymentStatus(deployment_id).catch(() => null);
        if (!info) return;
        setExportJob(info);
        if (info.status !== 'running' && info.status !== 'pending') {
          window.clearInterval(pollRef.current);
          if (info.status === 'completed') showSuccess('Model published to Hugging Face');
          else showError(info.error || 'Export failed');
          refresh();
        }
      }, 2000);
    } catch (e) {
      showError((e as Error).message);
    }
  };

  const base = server?.base_url ?? '';
  const sampleModel = server?.model_id ?? serverModel ?? 'MODEL_ID';
  const keyHeader = server?.auth_required ? ` \\\n  -H "Authorization: Bearer YOUR_KEY"` : '';
  const curl = `curl ${base}/chat/completions \\\n  -H "Content-Type: application/json"${keyHeader} \\\n  -d '{"model": "${sampleModel}", "messages": [{"role": "user", "content": "Hello"}]}'`;
  const python = `from openai import OpenAI\n\nclient = OpenAI(base_url="${base}", api_key="${server?.auth_required ? 'YOUR_KEY' : 'not-needed'}")\nreply = client.chat.completions.create(\n    model="${sampleModel}",\n    messages=[{"role": "user", "content": "Hello"}],\n)\nprint(reply.choices[0].message.content)`;

  const exporting = exportJob?.status === 'running' || exportJob?.status === 'pending';
  const hfReady = hfModel && /^[\w.-]+\/[\w.-]+$/.test(repoName.trim());

  return (
    <Container className="py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">Deploy &amp; Endpoints</h1>
        <p className="text-neutral-600 dark:text-neutral-400 mt-1">
          Serve local models through an OpenAI-compatible API, or publish them to Hugging Face.
        </p>
      </div>

      {/* Local API server */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Local API server</CardTitle>
              <CardDescription>
                Exposes <code>/v1/models</code>, <code>/v1/chat/completions</code> and <code>/v1/embeddings</code>.
              </CardDescription>
            </div>
            <Badge variant={server ? 'success' : 'default'}>{server ? 'Running' : 'Stopped'}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {!server ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2">
                  <label className={labelClass}>Preload model (optional)</label>
                  <select className={fieldClass} value={serverModel} onChange={(e) => setServerModel(e.target.value)}>
                    <option value="">Load on first request</option>
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.kind})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Port</label>
                  <input
                    type="number"
                    className={fieldClass}
                    value={port}
                    min={1024}
                    max={65535}
                    onChange={(e) => setPort(Number(e.target.value))}
                  />
                </div>
                <div className="md:col-span-2">
                  <label className={labelClass}>API key (optional)</label>
                  <input
                    className={fieldClass}
                    value={apiKey}
                    placeholder="Leave empty for no authentication"
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm self-end pb-2">
                  <input
                    type="checkbox"
                    checked={allowLan}
                    onChange={(e) => setAllowLan(e.target.checked)}
                    className="accent-brand-500"
                  />
                  Allow other devices on my network
                </label>
              </div>
              {allowLan && !apiKey && (
                <p className="text-sm text-warning-600">An API key is required to expose the server to your network.</p>
              )}
              <Button
                onClick={startServer}
                isLoading={starting}
                disabled={allowLan && !apiKey}
                leftIcon={<Play className="w-4 h-4" />}
              >
                Start server
              </Button>
            </>
          ) : (
            <>
              <div className="rounded-lg bg-neutral-100 dark:bg-neutral-800 p-3 space-y-2 text-sm">
                {Object.entries(server.endpoints).map(([name, url]) => (
                  <div key={name} className="flex items-center justify-between gap-3">
                    <span className="text-neutral-500 w-36 shrink-0">{name.replace('_', ' ')}</span>
                    <code className="truncate flex-1">{url}</code>
                    <CopyButton text={url} />
                  </div>
                ))}
                <p className="text-xs text-neutral-500">
                  Auth: {server.auth_required ? 'API key required' : 'none'} ·{' '}
                  {server.host === '0.0.0.0' ? 'visible on your network' : 'this machine only'}
                </p>
              </div>
              {[
                { title: 'curl', code: curl },
                { title: 'Python (openai SDK)', code: python },
              ].map(({ title, code }) => (
                <div key={title}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={labelClass + ' mb-0'}>{title}</span>
                    <CopyButton text={code} />
                  </div>
                  <pre className="overflow-x-auto rounded-lg bg-neutral-900 text-neutral-100 p-3 text-xs">{code}</pre>
                </div>
              ))}
              <Button variant="danger" onClick={stopServer} leftIcon={<Square className="w-4 h-4" />}>
                Stop server
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      {/* Hugging Face export */}
      <Card>
        <CardHeader>
          <CardTitle>Export to Hugging Face</CardTitle>
          <CardDescription>
            Uploads the model (safetensors, LoRA adapter or GGUF) with an auto-generated model card. Uses the token
            saved in <Link to="/settings" className="text-brand-600 underline">Settings</Link> unless you enter one
            below.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Model</label>
              <select className={fieldClass} value={hfModel} onChange={(e) => setHfModel(e.target.value)}>
                <option value="">Select a local model…</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.kind}, {m.size_mb} MB)
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>Repository</label>
              <input
                className={fieldClass}
                placeholder="username/model-name"
                value={repoName}
                onChange={(e) => setRepoName(e.target.value)}
              />
            </div>
            <div className="md:col-span-2">
              <label className={labelClass}>Model card description (optional)</label>
              <textarea
                className={fieldClass + ' resize-none'}
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What is this model good at?"
              />
            </div>
            <div>
              <label className={labelClass}>Token override (optional)</label>
              <input
                type="password"
                className={fieldClass}
                value={hfToken}
                onChange={(e) => setHfToken(e.target.value)}
                placeholder="hf_…"
              />
            </div>
            <label className="flex items-center gap-2 text-sm self-end pb-2">
              <input
                type="checkbox"
                checked={isPrivate}
                onChange={(e) => setIsPrivate(e.target.checked)}
                className="accent-brand-500"
              />
              Private repository
            </label>
          </div>
          <div className="flex items-center gap-4">
            <Button onClick={exportToHub} isLoading={exporting} disabled={!hfReady} leftIcon={<UploadCloud className="w-4 h-4" />}>
              Push to Hub
            </Button>
            {exportJob?.status === 'completed' && exportJob.repo_url && (
              <a
                href={exportJob.repo_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-sm text-brand-600 underline"
              >
                View on Hugging Face <ExternalLink className="w-3 h-3" />
              </a>
            )}
            {exportJob?.status === 'failed' && <span className="text-sm text-error-600">{exportJob.error}</span>}
          </div>
        </CardContent>
      </Card>

      {/* History */}
      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent>
          {history.length === 0 ? (
            <p className="text-sm text-neutral-500">No deployments yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-neutral-500">
                <tr>
                  <th className="py-2">Type</th>
                  <th>Model</th>
                  <th>Status</th>
                  <th>Started</th>
                  <th>Link</th>
                </tr>
              </thead>
              <tbody>
                {history.map((d) => (
                  <tr key={d.deployment_id} className="border-t border-neutral-200 dark:border-neutral-800">
                    <td className="py-2">{d.type === 'local' ? 'Local API' : 'Hugging Face'}</td>
                    <td className="truncate max-w-[16rem]">{d.model_id ?? '—'}</td>
                    <td>
                      <Badge variant={statusVariant(d.status)}>{d.status}</Badge>
                    </td>
                    <td>{d.started_at ? new Date(d.started_at + 'Z').toLocaleString() : '—'}</td>
                    <td>{d.repo_url ? <a href={d.repo_url} target="_blank" rel="noreferrer" className="text-brand-600 underline">repo</a> : d.base_url ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </Container>
  );
};

export default DeploymentConsole;
