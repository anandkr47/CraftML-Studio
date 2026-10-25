/**
 * Fine-Tune job dashboard
 * Live loss curve, step progress, GPU memory and logs for one run.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Square, Trash2 } from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { LineChart } from '../components/charts/LineChart';
import { JobStatus, MetricPoint, finetuneApi } from '../api/finetune';
import { useNotificationStore } from '../store/notificationStore';
import { ActiveRun, cloudApi, money } from '../api/cloud';
import { HttpError, errorText } from '../api/errors';

const POLL_MS = 2000;
const ACTIVE = ['pending', 'running'];

const Stat: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div>
    <p className="text-xs uppercase text-neutral-500">{label}</p>
    <p className="text-xl font-semibold text-neutral-900 dark:text-neutral-100">{value}</p>
  </div>
);

const FineTuneJob: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { success: showSuccess, error: showError } = useNotificationStore();

  const [job, setJob] = useState<JobStatus | null>(null);
  const [points, setPoints] = useState<MetricPoint[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [run, setRun] = useState<ActiveRun | null>(null);
  const [connectionIssue, setConnectionIssue] = useState(false);
  const lastStep = useRef(-1);
  const logOffset = useRef(0);
  const logEnd = useRef<HTMLDivElement>(null);

  /** One fetch of status + new metrics + new logs. Throws on failure (the loop decides what to do). */
  const poll = useCallback(async (): Promise<boolean> => {
    if (!jobId) return false;
    const [status, newPoints, newLogs] = await Promise.all([
      finetuneApi.jobStatus(jobId),
      finetuneApi.jobMetrics(jobId, lastStep.current),
      finetuneApi.jobLogs(jobId, logOffset.current),
    ]);
    setJob(status);
    if (status.params?.cloud) {
      cloudApi.runs().then((runs) => setRun(runs.find((r) => r.job_id === jobId) ?? null)).catch(() => undefined);
    }
    if (newPoints.length) {
      lastStep.current = newPoints[newPoints.length - 1].step;
      setPoints((prev) => [...prev, ...newPoints]);
    }
    if (newLogs.logs.length) {
      logOffset.current += newLogs.logs.length;
      setLogs((prev) => [...prev, ...newLogs.logs]);
    }
    return ACTIVE.includes(status.status);
  }, [jobId]);

  // Polling loop: one request at a time, backoff on errors, one last fetch after the job ends
  // (so logs written as it finishes aren't missed), and an immediate tick on demand (`wake`).
  const wake = useRef<() => void>(() => undefined);
  useEffect(() => {
    let timer: number | undefined;
    let cancelled = false;
    let inFlight = false;
    let failures = 0;
    let finalFetchDone = false;

    // a different job: start from scratch
    lastStep.current = -1;
    logOffset.current = 0;
    setPoints([]);
    setLogs([]);
    setJob(null);
    setNotFound(false);

    const tick = async () => {
      if (cancelled || inFlight) return;
      inFlight = true;
      let delay = POLL_MS;
      try {
        const active = await poll();
        failures = 0;
        setConnectionIssue(false);
        if (!active) {
          if (finalFetchDone) return;
          finalFetchDone = true;
          delay = 1000;
        } else {
          finalFetchDone = false;
        }
      } catch (e) {
        if (e instanceof HttpError && e.status === 404) {
          setNotFound(true);
          return;
        }
        failures += 1;
        setConnectionIssue(true);
        delay = Math.min(30000, POLL_MS * 2 ** failures);
      } finally {
        inFlight = false;
      }
      if (!cancelled) timer = window.setTimeout(tick, delay);
    };

    wake.current = () => {
      window.clearTimeout(timer);
      finalFetchDone = false;
      tick();
    };
    tick();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [poll]);

  useEffect(() => {
    logEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const stop = async () => {
    try {
      await finetuneApi.stopJob(jobId!);
      showSuccess('Stopping…');
      wake.current();
    } catch (e) {
      showError(errorText(e));
    }
  };

  const remove = async () => {
    try {
      await finetuneApi.deleteJob(jobId!);
      navigate('/finetune');
    } catch (e) {
      showError(errorText(e));
    }
  };

  if (notFound) {
    return (
      <Container className="py-8">
        <p>Run not found.</p>
        <Link to="/finetune" className="text-brand-600 underline">Back to Fine-Tune</Link>
      </Container>
    );
  }

  const status = job?.status ?? 'pending';
  const active = ACTIVE.includes(status);
  const progress = job?.progress;
  const pct = progress && progress.total_steps ? Math.min(100, (progress.current_step / progress.total_steps) * 100) : 0;
  const latest = points[points.length - 1];
  const steps = points.map((p) => p.step);
  const vram = points.map((p) => p.vram_gb);
  const hasVram = vram.some((v) => v !== null);

  return (
    <Container className="py-8 space-y-6">
      <Link to="/finetune" className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-brand-600">
        <ArrowLeft className="w-4 h-4" /> Fine-Tune
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold truncate">{job?.params?.model_name ?? jobId}</h1>
          <p className="text-sm text-neutral-500 mt-1">
            {jobId} · {job?.params?.training_method?.toUpperCase()}
          </p>
          {job?.params?.cloud && (
            <p className="text-sm mt-1 text-brand-700 dark:text-brand-300">
              Remote: {job.params.cloud.provider}
              {run?.gpu ? ` · ${run.gpu}` : job.params.cloud.gpu_id ? ` · ${job.params.cloud.gpu_id}` : ''}
              {run?.price_per_hour != null && ` · ${money(run.price_per_hour)}/h`}
              {run?.estimated_cost != null && ` · ≈ ${money(run.estimated_cost)} so far (estimate)`}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'default'}>{status}</Badge>
          {active ? (
            <Button variant="danger" size="sm" onClick={stop} leftIcon={<Square className="w-4 h-4" />}
              title={job?.params?.cloud ? 'Stops the job and terminates the remote machine' : undefined}>
              {job?.params?.cloud ? 'Stop & terminate' : 'Stop'}
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={remove} leftIcon={<Trash2 className="w-4 h-4" />}>
              Delete
            </Button>
          )}
        </div>
      </div>

      {connectionIssue && (
        <div className="rounded-lg bg-warning-50 dark:bg-warning-900/20 px-4 py-2 text-sm text-warning-800 dark:text-warning-300">
          Can&apos;t reach the backend right now; retrying… (the job keeps running)
        </div>
      )}
      {job?.error && (
        <div className="rounded-lg bg-error-50 dark:bg-error-900/20 px-4 py-3 text-sm text-error-700 dark:text-error-300">
          {job.error}
        </div>
      )}
      {status === 'completed' && (
        <div className="rounded-lg bg-success-50 dark:bg-success-900/20 px-4 py-3 text-sm text-success-800 dark:text-success-300">
          Training finished. <Link to="/" className="underline font-medium">Chat with the model</Link>,{' '}
          <Link to="/compress" className="underline font-medium">compress it</Link> or{' '}
          <Link to="/deploy" className="underline font-medium">deploy it</Link>.
        </div>
      )}

      <Card>
        <CardContent className="pt-6 space-y-4">
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span>
                Step {progress?.current_step ?? 0} / {progress?.total_steps || '—'}
              </span>
              <span>{pct.toFixed(0)}%</span>
            </div>
            <div className="h-2 rounded-full bg-neutral-200 dark:bg-neutral-700 overflow-hidden">
              <div className="h-full bg-brand-500 transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Stat label="Epoch" value={progress ? `${progress.current_epoch} / ${progress.total_epochs}` : '—'} />
            <Stat label="Loss" value={progress?.loss != null ? progress.loss.toFixed(4) : '—'} />
            <Stat label="Learning rate" value={latest?.learning_rate != null ? latest.learning_rate.toExponential(2) : '—'} />
            <Stat label="GPU memory" value={latest?.vram_gb != null ? `${latest.vram_gb.toFixed(2)} GB` : '—'} />
          </div>
        </CardContent>
      </Card>

      <div className={`grid grid-cols-1 gap-6 ${hasVram ? 'lg:grid-cols-2' : ''}`}>
        <Card>
          <CardHeader>
            <CardTitle>Training loss</CardTitle>
          </CardHeader>
          <CardContent>
            {points.length ? (
              <LineChart labels={steps} data={points.map((p) => p.loss)} label="loss" />
            ) : (
              <p className="text-sm text-neutral-500 py-12 text-center">
                {active ? 'Waiting for the first logged step…' : 'No metrics were recorded.'}
              </p>
            )}
          </CardContent>
        </Card>
        {hasVram && (
          <Card>
            <CardHeader>
              <CardTitle>GPU memory (GB)</CardTitle>
            </CardHeader>
            <CardContent>
              <LineChart labels={steps} data={vram} label="VRAM" color="#10b981" />
            </CardContent>
          </Card>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Logs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-72 overflow-y-auto rounded-lg bg-neutral-900 p-3 font-mono text-xs text-neutral-200 space-y-0.5">
            {logs.length === 0 && <p className="text-neutral-500">No logs yet.</p>}
            {logs.map((line, i) => (
              <div key={i} className="whitespace-pre-wrap">{line}</div>
            ))}
            <div ref={logEnd} />
          </div>
        </CardContent>
      </Card>
    </Container>
  );
};

export default FineTuneJob;
