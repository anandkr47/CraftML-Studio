/**
 * "Where to run" selector for the Fine-Tune wizard: this machine, or a remote GPU.
 * For billed providers it shows the GPU price and the worst-case cost and requires an explicit
 * acknowledgement; it reports a validated CloudTarget (or null for "this machine") to the parent.
 */

import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Cloud, Cpu, Loader2 } from 'lucide-react';
import {
  CloudTarget, CostEstimate, GpuOption, ProviderInfo, SshProfile, cloudApi, money,
} from '../../api/cloud';
import { API_BASE } from '../../config';
import { errorText } from '../../api/errors';

export interface RunPlacement {
  target: CloudTarget | null; // null = this machine
  valid: boolean;
  label: string;
  estimate: CostEstimate | null;
}

const field = 'w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-3 py-2 text-sm';
const labelClass = 'block text-xs font-semibold uppercase text-neutral-500 mb-1';

export const LOCAL_PLACEMENT: RunPlacement = { target: null, valid: true, label: 'This computer', estimate: null };

export const WhereToRun: React.FC<{ onChange: (placement: RunPlacement) => void }> = ({ onChange }) => {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [profiles, setProfiles] = useState<SshProfile[]>([]);
  const [hfConnected, setHfConnected] = useState<boolean | null>(null);
  const [where, setWhere] = useState<string>('local');
  const [gpus, setGpus] = useState<GpuOption[]>([]);
  const [gpuId, setGpuId] = useState('');
  const [sshProfile, setSshProfile] = useState('');
  const [minutes, setMinutes] = useState(120);
  const [estimate, setEstimate] = useState<CostEstimate | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [loading, setLoading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([cloudApi.providers(), cloudApi.sshProfiles()])
      .then(([p, s]) => { setProviders(p.filter((x) => x.capabilities.training && x.configured)); setProfiles(s); })
      .catch(() => undefined);
    fetch(`${API_BASE}/api/settings/hf-token/status`).then((r) => r.json()).then((d) => setHfConnected(!!d.is_authenticated)).catch(() => setHfConnected(false));
  }, []);

  const provider = providers.find((p) => p.id === where);
  const billed = where === 'runpod' || where === 'modal';

  // GPU list for the chosen provider
  useEffect(() => {
    setGpus([]); setGpuId(''); setEstimate(null); setAcknowledged(false); setProblem(null);
    if (!billed) return;
    setLoading(true);
    cloudApi.gpus(where as 'runpod' | 'modal')
      .then((list) => { setGpus(list); setGpuId(list.find((g) => g.available)?.id ?? ''); setProblem(null); })
      .catch((e) => setProblem(errorText(e)))
      .finally(() => setLoading(false));
  }, [where, billed]);

  // Worst-case cost for the chosen GPU and runtime
  useEffect(() => {
    setAcknowledged(false);
    if (!billed || !gpuId) { setEstimate(null); return; }
    const timer = setTimeout(() => {
      cloudApi.estimate({ provider: where as 'runpod' | 'modal', gpu_id: gpuId, max_runtime_minutes: minutes })
        .then((e) => { setEstimate(e); setProblem(null); }).catch((e) => setProblem(errorText(e)));
    }, 300);
    return () => clearTimeout(timer);
  }, [where, billed, gpuId, minutes]);

  useEffect(() => {
    if (where === 'local') { onChange(LOCAL_PLACEMENT); return; }
    const needsToken = billed && hfConnected === false;
    const gpuName = gpus.find((g) => g.id === gpuId)?.name ?? gpuId;
    const ready = where === 'ssh' ? !!sshProfile : !!gpuId && !needsToken && (acknowledged || estimate?.worst_case_cost == null);
    onChange({
      target: { provider: where as CloudTarget['provider'], gpu_id: billed ? gpuId : null, max_runtime_minutes: minutes, ssh_profile: where === 'ssh' ? sshProfile : null },
      valid: ready,
      label: where === 'ssh' ? `SSH host “${sshProfile}”` : `${provider?.label ?? where} · ${gpuName}`,
      estimate,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [where, gpuId, sshProfile, minutes, acknowledged, estimate, hfConnected, gpus]);

  const options = [
    { id: 'local', label: 'This computer', icon: <Cpu className="w-4 h-4" />, note: 'Free; needs enough VRAM or memory.' },
    ...providers.map((p) => ({ id: p.id as string, label: p.label, icon: <Cloud className="w-4 h-4" />, note: p.id === 'ssh' ? 'Your server' : 'Pay per use' })),
  ];
  const sshReady = profiles.length > 0;
  if (sshReady && !providers.some((p) => p.id === 'ssh')) options.push({ id: 'ssh', label: 'SSH host', icon: <Cloud className="w-4 h-4" />, note: 'Your server' });

  return (
    <div className="space-y-4">
      <div>
        <label className={labelClass}>Where to run</label>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {options.map((o) => (
            <button key={o.id} onClick={() => setWhere(o.id)}
              className={`text-left rounded-lg border-2 p-3 ${where === o.id ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20' : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300'}`}>
              <p className="flex items-center gap-2 font-semibold text-sm">{o.icon}{o.label}</p>
              <p className="text-xs text-neutral-500 mt-1">{o.note}</p>
            </button>
          ))}
        </div>
        {providers.length === 0 && !sshReady && (
          <p className="text-xs text-neutral-500 mt-2">
            Short on VRAM? Connect RunPod, Modal or your own server in <Link to="/settings" className="text-brand-600 underline">Settings → Cloud GPUs</Link>.
          </p>
        )}
      </div>

      {where !== 'local' && (
        <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 p-4 space-y-3">
          <p className="text-xs text-warning-700 dark:text-warning-400">
            Your dataset will be sent to {where === 'ssh' ? 'your server' : provider?.label}
            {billed ? ' (via a private Hugging Face repository that is deleted afterwards)' : ''} and removed when the run ends.
          </p>

          {billed && hfConnected === false && (
            <p className="text-sm text-error-600">
              This needs a Hugging Face token to move your data. Add one in <Link to="/settings" className="underline">Settings</Link>.
            </p>
          )}

          {billed && (
            <div>
              <label className={labelClass}>GPU</label>
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : (
                <select className={field} value={gpuId} onChange={(e) => setGpuId(e.target.value)}>
                  {gpus.map((g) => (
                    <option key={g.id} value={g.id} disabled={!g.available}>
                      {g.name} · {g.vram_gb} GB · {g.price_per_hour != null ? `${money(g.price_per_hour)}/h` : 'price n/a'}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {where === 'ssh' && (
            <div>
              <label className={labelClass}>Host</label>
              <select className={field} value={sshProfile} onChange={(e) => setSshProfile(e.target.value)}>
                <option value="">Choose a host…</option>
                {profiles.map((p) => <option key={p.name} value={p.name}>{p.name} ({p.host}){p.host_key_pinned ? '' : ' — host key not verified'}</option>)}
              </select>
              {profiles.find((p) => p.name === sshProfile)?.host_key_pinned === false && (
                <p className="text-xs text-warning-700 mt-1">Verify this host&apos;s key in Settings first, or the connection will be refused.</p>
              )}
            </div>
          )}

          <div>
            <label className={labelClass}>Stop automatically after (minutes)</label>
            <input type="number" min={5} max={1440} className={field} value={minutes} onChange={(e) => setMinutes(Math.max(5, Math.min(1440, Number(e.target.value) || 5)))} />
            <p className="text-xs text-neutral-500 mt-1">A hard cap: the remote machine is shut down when it&apos;s reached, even if the app is closed.</p>
          </div>

          {billed && estimate && (
            <div className="rounded-lg bg-neutral-100 dark:bg-neutral-800 p-3 text-sm space-y-2">
              <p>
                Worst case: <strong>{money(estimate.worst_case_cost)}</strong>
                {estimate.price_per_hour != null && <> ({money(estimate.price_per_hour)}/h × {Math.round((minutes / 60) * 10) / 10} h)</>}
              </p>
              <p className="text-xs text-neutral-500">{estimate.note}</p>
              {estimate.worst_case_cost != null && (
                <label className="flex items-start gap-2">
                  <input type="checkbox" className="mt-1 accent-brand-500" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} />
                  <span>I understand this run may cost up to {money(estimate.worst_case_cost)} on my {provider?.label} account.</span>
                </label>
              )}
            </div>
          )}
          {problem && <p className="text-sm text-error-600">{problem}</p>}
        </div>
      )}
    </div>
  );
};

export default WhereToRun;
