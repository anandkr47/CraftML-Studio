/**
 * Fine-Tune
 * Four-step wizard for LoRA / QLoRA fine-tuning:
 * base model -> dataset -> settings -> review & start.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, Check, FileText, Loader2, Search, Trash2, UploadCloud } from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { chatApi, LocalModel } from '../api/chat';
import {
  DatasetInfo,
  JobSummary,
  StartJobRequest,
  TrainingMethod,
  finetuneApi,
} from '../api/finetune';
import { useNotificationStore } from '../store/notificationStore';

const STEPS = ['Base model', 'Dataset', 'Settings', 'Review'] as const;

const fieldClass =
  'w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-3 py-2 text-sm';
const labelClass = 'block text-xs font-semibold uppercase text-neutral-500 mb-1';

interface MethodOption {
  id: string;
  method: TrainingMethod;
  eightBit: boolean;
  title: string;
  detail: string;
  defaults: { epochs: number; lr: number; batch: number };
}

const METHODS: MethodOption[] = [
  {
    id: 'qlora',
    method: 'qlora',
    eightBit: false,
    title: 'QLoRA · 4-bit',
    detail: 'Lowest memory. Needs an NVIDIA GPU; on other hardware it falls back to standard LoRA.',
    defaults: { epochs: 2, lr: 2e-4, batch: 4 },
  },
  {
    id: 'lora8',
    method: 'lora',
    eightBit: true,
    title: 'LoRA · 8-bit',
    detail: 'Balanced memory and quality. Needs an NVIDIA GPU; otherwise standard precision.',
    defaults: { epochs: 3, lr: 1e-4, batch: 4 },
  },
  {
    id: 'lora',
    method: 'lora',
    eightBit: false,
    title: 'LoRA · standard precision',
    detail: 'Works on any hardware, including Apple Silicon and CPU. Uses the most memory of the adapter methods.',
    defaults: { epochs: 3, lr: 1e-4, batch: 4 },
  },
  {
    id: 'full',
    method: 'full',
    eightBit: false,
    title: 'Full fine-tuning',
    detail: 'Updates every weight. Best quality, but needs far more memory. For small models only.',
    defaults: { epochs: 3, lr: 5e-5, batch: 2 },
  },
];

const Wizard: React.FC = () => {
  const navigate = useNavigate();
  const { success: showSuccess, error: showError } = useNotificationStore();
  const [step, setStep] = useState(0);

  // Step 1: model
  const [modelId, setModelId] = useState('');
  const [query, setQuery] = useState('');
  const [hubResults, setHubResults] = useState<{ model_id: string; downloads?: number }[]>([]);
  const [searching, setSearching] = useState(false);
  const [localModels, setLocalModels] = useState<LocalModel[]>([]);

  // Step 2: dataset
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  // Step 3: settings
  const [methodId, setMethodId] = useState('qlora');
  const [epochs, setEpochs] = useState(2);
  const [learningRate, setLearningRate] = useState(2e-4);
  const [batchSize, setBatchSize] = useState(4);
  const [maxSeqLength, setMaxSeqLength] = useState(512);
  const [loraRank, setLoraRank] = useState(16);
  const [loraAlpha, setLoraAlpha] = useState(32);
  const [loraDropout, setLoraDropout] = useState(0.05);
  const [saveSteps, setSaveSteps] = useState(100);

  const [starting, setStarting] = useState(false);
  const [recent, setRecent] = useState<JobSummary[]>([]);

  const method = METHODS.find((m) => m.id === methodId)!;

  const refreshDatasets = useCallback(
    () => finetuneApi.listDatasets().then(setDatasets).catch(() => undefined),
    []
  );

  useEffect(() => {
    chatApi.listModels().then(setLocalModels).catch(() => undefined);
    refreshDatasets();
    finetuneApi.listJobs().then(setRecent).catch(() => undefined);
  }, [refreshDatasets]);

  // Debounced Hugging Face search
  useEffect(() => {
    if (query.trim().length < 3) {
      setHubResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        setHubResults(await finetuneApi.searchHubModels(query.trim()));
      } catch {
        setHubResults([]);
      } finally {
        setSearching(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [query]);

  const chooseMethod = (m: MethodOption) => {
    setMethodId(m.id);
    setEpochs(m.defaults.epochs);
    setLearningRate(m.defaults.lr);
    setBatchSize(m.defaults.batch);
  };

  const upload = async (files: File[]) => {
    if (!files.length) return;
    setUploading(true);
    try {
      const info = await finetuneApi.uploadDataset(files[0]);
      setDataset(info);
      await refreshDatasets();
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const pickDataset = async (d: DatasetInfo) => {
    try {
      setDataset(await finetuneApi.datasetInfo(d.id));
    } catch (e) {
      showError((e as Error).message);
    }
  };

  const removeDataset = async (d: DatasetInfo) => {
    await finetuneApi.deleteDataset(d.id).catch((e) => showError(e.message));
    if (dataset?.id === d.id) setDataset(null);
    refreshDatasets();
  };

  const canAdvance = [
    modelId.trim().length > 0,
    !!dataset && dataset.valid !== false,
    epochs >= 1 && learningRate > 0 && batchSize >= 1,
    true,
  ][step];

  const start = async () => {
    if (!dataset) return;
    setStarting(true);
    try {
      const request: StartJobRequest = {
        model_name: modelId.trim(),
        dataset_path: dataset.path,
        training_method: method.method,
        lora_config: { r: loraRank, lora_alpha: loraAlpha, lora_dropout: loraDropout },
        training_config: {
          num_epochs: epochs,
          batch_size: batchSize,
          learning_rate: learningRate,
          max_seq_length: maxSeqLength,
          save_steps: saveSteps,
          use_4bit: method.method === 'qlora',
          use_8bit: method.eightBit,
        },
      };
      const { job_id } = await finetuneApi.startJob(request);
      showSuccess('Fine-tuning started');
      navigate(`/finetune/job/${job_id}`);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  return (
    <Container className="py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">Fine-Tune</h1>
        <p className="text-neutral-600 dark:text-neutral-400 mt-1">
          Adapt a base model to your data with LoRA / QLoRA — no code required.
        </p>
      </div>

      {/* Stepper */}
      <ol className="flex items-center gap-2">
        {STEPS.map((name, i) => (
          <li key={name} className="flex items-center gap-2">
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full text-sm font-semibold ${
                i < step
                  ? 'bg-success-500 text-white'
                  : i === step
                  ? 'bg-brand-500 text-white'
                  : 'bg-neutral-200 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-300'
              }`}
            >
              {i < step ? <Check className="w-4 h-4" /> : i + 1}
            </span>
            <span className={`text-sm ${i === step ? 'font-semibold' : 'text-neutral-500'}`}>{name}</span>
            {i < STEPS.length - 1 && <span className="mx-2 h-px w-8 bg-neutral-300 dark:bg-neutral-700" />}
          </li>
        ))}
      </ol>

      <Card>
        <CardContent className="pt-6 space-y-6">
          {/* STEP 1 — model */}
          {step === 0 && (
            <>
              <div>
                <label className={labelClass}>Base model (Hugging Face id or local path)</label>
                <input
                  className={fieldClass}
                  value={modelId}
                  placeholder="e.g. TinyLlama/TinyLlama-1.1B-Chat-v1.0"
                  onChange={(e) => setModelId(e.target.value)}
                />
              </div>

              <div>
                <label className={labelClass}>Search Hugging Face</label>
                <div className="relative">
                  <Search className="absolute left-3 top-2.5 w-4 h-4 text-neutral-400" />
                  <input
                    className={fieldClass + ' pl-9'}
                    value={query}
                    placeholder="llama, qwen, phi, gpt2…"
                    onChange={(e) => setQuery(e.target.value)}
                  />
                  {searching && <Loader2 className="absolute right-3 top-2.5 w-4 h-4 animate-spin text-neutral-400" />}
                </div>
                <ul className="mt-2 space-y-1 max-h-56 overflow-y-auto">
                  {hubResults.map((m) => (
                    <li key={m.model_id}>
                      <button
                        onClick={() => setModelId(m.model_id)}
                        className={`w-full text-left rounded-lg border px-3 py-2 text-sm ${
                          modelId === m.model_id
                            ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                            : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300'
                        }`}
                      >
                        {m.model_id}
                        <span className="ml-2 text-xs text-neutral-500">
                          {(m.downloads ?? 0).toLocaleString()} downloads
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>

              {localModels.some((m) => m.kind === 'full') && (
                <div>
                  <label className={labelClass}>Downloaded models</label>
                  <div className="flex flex-wrap gap-2">
                    {localModels
                      .filter((m) => m.kind === 'full')
                      .map((m) => (
                        <button
                          key={m.id}
                          onClick={() => setModelId(m.path)}
                          className={`rounded-full border px-3 py-1 text-sm ${
                            modelId === m.path ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20' : 'border-neutral-300 dark:border-neutral-700'
                          }`}
                        >
                          {m.name}
                        </button>
                      ))}
                  </div>
                </div>
              )}
              <p className="text-xs text-neutral-500">
                Gated models need a Hugging Face token — add it in <Link to="/settings" className="text-brand-600 underline">Settings</Link>.
              </p>
            </>
          )}

          {/* STEP 2 — dataset */}
          {step === 1 && (
            <>
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
                onClick={() => fileInput.current?.click()}
                className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
                  dragging ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20' : 'border-neutral-300 dark:border-neutral-700 hover:border-brand-400'
                }`}
              >
                <input
                  ref={fileInput}
                  type="file"
                  hidden
                  accept=".jsonl,.json,.csv,.parquet,.txt"
                  onChange={(e) => {
                    upload(Array.from(e.target.files ?? []));
                    e.target.value = '';
                  }}
                />
                {uploading ? <Loader2 className="w-8 h-8 mx-auto animate-spin text-brand-500" /> : <UploadCloud className="w-8 h-8 mx-auto text-neutral-400" />}
                <p className="mt-2 font-medium">Drop a dataset here or click to browse</p>
                <p className="text-sm text-neutral-500">JSONL, JSON, CSV, Parquet or TXT</p>
                <p className="text-xs text-neutral-500 mt-1">
                  Columns: <code>instruction</code> + <code>output</code> · <code>prompt</code> + <code>completion</code> ·{' '}
                  <code>messages</code> · <code>text</code>
                </p>
              </div>

              {datasets.length > 0 && (
                <div>
                  <label className={labelClass}>Your datasets</label>
                  <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
                    {datasets.map((d) => (
                      <li key={d.id} className="flex items-center justify-between py-2">
                        <button onClick={() => pickDataset(d)} className="flex items-center gap-2 text-left min-w-0">
                          <FileText className="w-4 h-4 text-neutral-400 shrink-0" />
                          <span className={`truncate text-sm ${dataset?.id === d.id ? 'font-semibold text-brand-600' : ''}`}>{d.name}</span>
                          <span className="text-xs text-neutral-500">{d.size_mb} MB</span>
                        </button>
                        <button onClick={() => removeDataset(d)} className="text-neutral-400 hover:text-error-500" title="Delete dataset">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {dataset?.columns && (
                <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 p-4 space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium">{dataset.name}</span>
                    <Badge variant={dataset.valid ? 'success' : 'error'}>{dataset.format ?? 'unrecognised'}</Badge>
                    <span className="text-sm text-neutral-500">
                      {dataset.num_samples?.toLocaleString()} examples · columns: {dataset.columns.join(', ')}
                    </span>
                  </div>
                  {dataset.problems?.map((p) => (
                    <p key={p} className="flex items-start gap-2 text-sm text-warning-700 dark:text-warning-400">
                      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> {p}
                    </p>
                  ))}
                  {dataset.preview && dataset.preview.length > 0 && (
                    <div>
                      <p className={labelClass}>What the model will see</p>
                      {dataset.preview.map((p, i) => (
                        <pre key={i} className="mb-2 whitespace-pre-wrap rounded bg-neutral-100 dark:bg-neutral-800 p-2 text-xs">{p}</pre>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* STEP 3 — settings */}
          {step === 2 && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {METHODS.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => chooseMethod(m)}
                    className={`text-left rounded-lg border-2 p-3 ${
                      methodId === m.id ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20' : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300'
                    }`}
                  >
                    <p className="font-semibold text-sm">{m.title}</p>
                    <p className="text-xs text-neutral-500 mt-1">{m.detail}</p>
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className={labelClass}>Epochs</label>
                  <input type="number" min={1} className={fieldClass} value={epochs} onChange={(e) => setEpochs(Number(e.target.value))} />
                </div>
                <div>
                  <label className={labelClass}>Learning rate</label>
                  <input type="number" step="any" className={fieldClass} value={learningRate} onChange={(e) => setLearningRate(Number(e.target.value))} />
                </div>
                <div>
                  <label className={labelClass}>Batch size</label>
                  <input type="number" min={1} className={fieldClass} value={batchSize} onChange={(e) => setBatchSize(Number(e.target.value))} />
                </div>
                <div>
                  <label className={labelClass}>Max tokens / example</label>
                  <input type="number" min={64} step={64} className={fieldClass} value={maxSeqLength} onChange={(e) => setMaxSeqLength(Number(e.target.value))} />
                </div>
                {method.method !== 'full' && (
                  <>
                    <div>
                      <label className={labelClass}>LoRA rank</label>
                      <input type="number" min={1} className={fieldClass} value={loraRank} onChange={(e) => setLoraRank(Number(e.target.value))} />
                    </div>
                    <div>
                      <label className={labelClass}>LoRA alpha</label>
                      <input type="number" min={1} className={fieldClass} value={loraAlpha} onChange={(e) => setLoraAlpha(Number(e.target.value))} />
                    </div>
                    <div>
                      <label className={labelClass}>LoRA dropout</label>
                      <input type="number" step={0.01} min={0} max={0.5} className={fieldClass} value={loraDropout} onChange={(e) => setLoraDropout(Number(e.target.value))} />
                    </div>
                  </>
                )}
                <div>
                  <label className={labelClass}>Checkpoint every N steps</label>
                  <input type="number" min={1} className={fieldClass} value={saveSteps} onChange={(e) => setSaveSteps(Number(e.target.value))} />
                </div>
              </div>
            </>
          )}

          {/* STEP 4 — review */}
          {step === 3 && (
            <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3 text-sm">
              {[
                ['Base model', modelId],
                ['Dataset', `${dataset?.name} (${dataset?.num_samples?.toLocaleString()} examples)`],
                ['Method', method.title],
                ['Epochs', epochs],
                ['Learning rate', learningRate],
                ['Batch size', batchSize],
                ['Max tokens / example', maxSeqLength],
                ...(method.method !== 'full' ? [['LoRA rank / alpha / dropout', `${loraRank} / ${loraAlpha} / ${loraDropout}`]] : []),
                ['Checkpoints', `every ${saveSteps} steps`],
              ].map(([k, v]) => (
                <div key={String(k)} className="flex justify-between gap-4 border-b border-neutral-200 dark:border-neutral-800 pb-2">
                  <dt className="text-neutral-500">{k}</dt>
                  <dd className="font-medium text-right break-all">{String(v)}</dd>
                </div>
              ))}
            </dl>
          )}

          <div className="flex justify-between pt-2">
            <Button variant="outline" disabled={step === 0} onClick={() => setStep(step - 1)}>
              Back
            </Button>
            {step < STEPS.length - 1 ? (
              <Button disabled={!canAdvance} onClick={() => setStep(step + 1)}>
                Next
              </Button>
            ) : (
              <Button onClick={start} isLoading={starting}>
                Start fine-tuning
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
          <CardDescription>Open a run to watch its loss curve, memory use and logs.</CardDescription>
        </CardHeader>
        <CardContent>
          {recent.length === 0 ? (
            <p className="text-sm text-neutral-500">No runs yet.</p>
          ) : (
            <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
              {recent.slice(0, 8).map((j) => (
                <li key={j.job_id} className="flex items-center justify-between py-2">
                  <Link to={`/finetune/job/${j.job_id}`} className="text-sm text-brand-600 hover:underline truncate">
                    {j.base_model ?? j.job_id}
                  </Link>
                  <Badge variant={j.status === 'completed' ? 'success' : j.status === 'failed' ? 'error' : 'default'}>{j.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </Container>
  );
};

export default Wizard;
