/**
 * Cloud GPUs settings: provider credentials, SSH hosts (with host-key verification), and a view
 * of remote resources that are currently billing.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Check, Cloud, Loader2, ShieldAlert, Trash2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import {
  ActiveRun,
  HostProbe,
  HostTest,
  Orphan,
  ProviderInfo,
  SshProfile,
  CloudApiError,
  cloudApi,
  money,
} from '../../api/cloud';
import { useNotificationStore } from '../../store/notificationStore';
import { errorText } from '../../api/errors';

const field =
  'w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-3 py-2 text-sm';
const label = 'block text-xs font-semibold uppercase text-neutral-500 mb-1';

const ProviderCard: React.FC<{ provider: ProviderInfo; onChanged: () => void }> = ({ provider, onChanged }) => {
  const { success, error } = useNotificationStore();
  const [editing, setEditing] = useState(!provider.configured);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const result = await cloudApi.saveCredentials(provider.id, values);
      success(`${provider.label} connected`, result.account.name);
      setValues({}); // never keep secrets in component state longer than needed
      setEditing(false);
      onChanged();
    } catch (e) {
      error(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    await cloudApi.removeCredentials(provider.id).catch((e) => error(errorText(e)));
    setEditing(true);
    onChanged();
  };

  const caps = [provider.capabilities.training && 'Fine-tuning', provider.capabilities.inference && 'Inference'].filter(Boolean);
  const ready = provider.fields.filter((f) => f.required).every((f) => values[f.name]?.trim());

  return (
    <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold">{provider.label}</p>
          <p className="text-xs text-neutral-500 mt-0.5">{provider.description}</p>
          <div className="flex gap-1 mt-2">
            {caps.map((c) => (
              <Badge key={String(c)} variant="default">{c}</Badge>
            ))}
          </div>
        </div>
        <Badge variant={provider.configured ? 'success' : 'default'}>{provider.configured ? 'Connected' : 'Not set up'}</Badge>
      </div>

      {editing ? (
        <>
          {provider.fields.map((f) => (
            <div key={f.name}>
              <label className={label}>{f.label}</label>
              <input
                type={f.secret ? 'password' : 'text'}
                autoComplete="off"
                className={field}
                placeholder={f.placeholder ?? ''}
                value={values[f.name] ?? ''}
                onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
              />
            </div>
          ))}
          <div className="flex gap-2">
            <Button size="sm" onClick={save} isLoading={busy} disabled={!ready}>Save &amp; verify</Button>
            {provider.configured && <Button size="sm" variant="outline" onClick={() => setEditing(false)}>Cancel</Button>}
          </div>
        </>
      ) : (
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>Replace credentials</Button>
          <Button size="sm" variant="ghost" leftIcon={<Trash2 className="w-4 h-4" />} onClick={remove}>Remove</Button>
        </div>
      )}
    </div>
  );
};

interface SshForm {
  name: string; host: string; port: number; username: string; runtime: 'venv' | 'docker';
  workdir: string; inference_port: string | number; private_key: string; passphrase: string;
}

const EMPTY_SSH: SshForm = { name: '', host: '', port: 22, username: '', runtime: 'venv', workdir: 'craftml', inference_port: '', private_key: '', passphrase: '' };

const SshHosts: React.FC = () => {
  const { success, error } = useNotificationStore();
  const [profiles, setProfiles] = useState<SshProfile[]>([]);
  const [form, setForm] = useState<SshForm | null>(null);
  const [probe, setProbe] = useState<{ name: string; result?: HostProbe; error?: CloudApiError } | null>(null);
  const [tests, setTests] = useState<Record<string, HostTest | 'loading'>>({});
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(() => cloudApi.sshProfiles().then(setProfiles).catch(() => undefined), []);
  useEffect(() => { refresh(); }, [refresh]);

  const save = async () => {
    if (!form) return;
    setSaving(true);
    try {
      await cloudApi.saveSshProfile(form.name, {
        host: form.host.trim(), port: Number(form.port), username: form.username.trim(), runtime: form.runtime,
        workdir: form.workdir.trim() || 'craftml', inference_port: form.inference_port === '' ? null : Number(form.inference_port),
        private_key: form.private_key || undefined, passphrase: form.passphrase || undefined,
      });
      setForm(null);
      await refresh();
      success('SSH host saved', 'Verify its host key before using it.');
    } catch (e) {
      error(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const verify = async (name: string) => {
    setProbe({ name });
    try {
      setProbe({ name, result: await cloudApi.probeSshHost(name) });
    } catch (e) {
      setProbe({ name, error: e as CloudApiError });
    }
  };

  const trust = async () => {
    if (!probe?.result) return;
    try {
      await cloudApi.trustSshHost(probe.name, probe.result.key_type, probe.result.fingerprint);
      success('Host key trusted');
      setProbe(null);
      refresh();
    } catch (e) {
      error(errorText(e));
    }
  };

  const test = async (name: string) => {
    setTests((t) => ({ ...t, [name]: 'loading' }));
    try {
      const result = await cloudApi.testSshHost(name);
      setTests((t) => ({ ...t, [name]: result }));
    } catch (e) {
      setTests((t) => { const { [name]: _, ...rest } = t; return rest; });
      error(errorText(e));
    }
  };

  const readKeyFile = (file: File | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setForm((f) => (f ? { ...f, private_key: String(reader.result) } : f));
    reader.readAsText(file);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>SSH hosts</CardTitle>
        <CardDescription>
          Your own Linux server with an NVIDIA GPU. Key authentication only. The dataset is copied over and removed afterwards.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {profiles.map((p) => {
          const t = tests[p.name];
          return (
            <div key={p.name} className="rounded-lg border border-neutral-200 dark:border-neutral-700 p-3 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <span className="font-medium">{p.name}</span>
                  <span className="text-sm text-neutral-500 ml-2">{p.username}@{p.host}:{p.port} · {p.runtime}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={p.host_key_pinned ? 'success' : 'warning'}>{p.host_key_pinned ? 'Host key trusted' : 'Host key not verified'}</Badge>
                  <Button size="xs" variant="outline" onClick={() => verify(p.name)}>Verify host key</Button>
                  <Button size="xs" variant="outline" onClick={() => test(p.name)} isLoading={t === 'loading'}>Test</Button>
                  <button className="text-neutral-400 hover:text-error-500" title="Remove host"
                    onClick={async () => { await cloudApi.deleteSshProfile(p.name).catch((e) => error(errorText(e))); refresh(); }}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {t && t !== 'loading' && (
                <p className={`text-sm ${t.ready ? 'text-success-700' : 'text-warning-700'}`}>
                  {t.ready ? <Check className="inline w-4 h-4 mr-1" /> : <AlertTriangle className="inline w-4 h-4 mr-1" />}
                  {t.os}; {t.gpus.length ? t.gpus.map((g) => `${g.name} (${g.vram_gb} GB)`).join(', ') : 'no NVIDIA GPU found'}
                  {p.runtime === 'docker' && !t.docker ? '; Docker missing' : ''}
                  {t.ready ? ' — ready for training' : ' — not ready'}
                </p>
              )}

              {probe?.name === p.name && (
                <div className="rounded-lg bg-neutral-100 dark:bg-neutral-800 p-3 text-sm space-y-2">
                  {!probe.result && !probe.error && <p><Loader2 className="inline w-4 h-4 animate-spin mr-1" />Contacting the server…</p>}
                  {probe.error && <p className="text-error-600">{probe.error.message}</p>}
                  {probe.result && (
                    <>
                      <p>The server presented this <strong>{probe.result.key_type}</strong> key:</p>
                      <code className="block break-all">{probe.result.fingerprint}</code>
                      {probe.result.status === 'changed' && (
                        <p className="flex gap-2 text-error-700">
                          <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                          This is DIFFERENT from the key you trusted before. If you didn&apos;t reinstall the server, don&apos;t continue.
                        </p>
                      )}
                      {probe.result.status === 'trusted' ? (
                        <p className="text-success-700">Matches the trusted key.</p>
                      ) : (
                        <>
                          <p className="text-neutral-500">
                            Compare it with <code>ssh-keygen -lf /etc/ssh/ssh_host_{probe.result.key_type.replace('ssh-', '')}_key.pub</code> run on the server.
                          </p>
                          <Button size="sm" onClick={trust}>It matches — trust this key</Button>
                        </>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {form ? (
          <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
            <div><label className={label}>Name</label><input className={field} value={form.name} placeholder="gpu-box" onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div><label className={label}>Host</label><input className={field} value={form.host} placeholder="gpu.example.com" onChange={(e) => setForm({ ...form, host: e.target.value })} /></div>
            <div><label className={label}>Username</label><input className={field} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></div>
            <div><label className={label}>Port</label><input type="number" className={field} value={form.port} onChange={(e) => setForm({ ...form, port: Number(e.target.value) })} /></div>
            <div>
              <label className={label}>Run with</label>
              <select className={field} value={form.runtime} onChange={(e) => setForm({ ...form, runtime: e.target.value as 'venv' | 'docker' })}>
                <option value="venv">Python virtualenv</option>
                <option value="docker">Docker (needs the NVIDIA container toolkit)</option>
              </select>
            </div>
            <div><label className={label}>Working folder (under the home directory)</label><input className={field} value={form.workdir} onChange={(e) => setForm({ ...form, workdir: e.target.value })} /></div>
            <div><label className={label}>Inference port (optional)</label><input type="number" className={field} value={form.inference_port} placeholder="Port of your OpenAI-compatible server" onChange={(e) => setForm({ ...form, inference_port: e.target.value })} /></div>
            <div><label className={label}>Key passphrase (if any)</label><input type="password" autoComplete="off" className={field} value={form.passphrase} onChange={(e) => setForm({ ...form, passphrase: e.target.value })} /></div>
            <div className="md:col-span-2">
              <label className={label}>Private key (Ed25519, ECDSA or RSA)</label>
              <textarea rows={5} autoComplete="off" spellCheck={false} className={field + ' font-mono text-xs resize-none'} value={form.private_key}
                placeholder="-----BEGIN OPENSSH PRIVATE KEY-----" onChange={(e) => setForm({ ...form, private_key: e.target.value })} />
              <input type="file" className="mt-1 text-xs" onChange={(e) => readKeyFile(e.target.files?.[0])} />
              <p className="text-xs text-neutral-500 mt-1">The key is stored encrypted on this computer and never shown again. Use a key made just for this app.</p>
            </div>
            <div className="md:col-span-2 flex gap-2">
              <Button size="sm" onClick={save} isLoading={saving} disabled={!form.name || !form.host || !form.username || !form.private_key.trim()}>Save host</Button>
              <Button size="sm" variant="outline" onClick={() => setForm(null)}>Cancel</Button>
            </div>
          </div>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setForm({ ...EMPTY_SSH })}>Add SSH host</Button>
        )}
      </CardContent>
    </Card>
  );
};

const Resources: React.FC = () => {
  const { success, error } = useNotificationStore();
  const [runs, setRuns] = useState<ActiveRun[]>([]);
  const [orphans, setOrphans] = useState<Orphan[] | null>(null);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    const load = () => cloudApi.runs().then(setRuns).catch(() => undefined);
    load();
    const timer = window.setInterval(load, 15000);
    return () => window.clearInterval(timer);
  }, []);

  const scan = async () => {
    setScanning(true);
    try {
      setOrphans(await cloudApi.orphans());
    } catch (e) {
      error(errorText(e));
    } finally {
      setScanning(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Running remote resources</CardTitle>
        <CardDescription>Anything listed here may be billing you. Costs are estimates (listed price × time).</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {runs.length === 0 && <p className="text-sm text-neutral-500">No remote jobs are running.</p>}
        {runs.map((r) => (
          <div key={r.job_id} className="flex justify-between text-sm">
            <span>{r.job_id} · {r.provider} · {r.gpu ?? 'GPU'}</span>
            <span className="font-mono">≈ {money(r.estimated_cost)} so far</span>
          </div>
        ))}
        <div className="pt-2 border-t border-neutral-200 dark:border-neutral-800">
          <Button size="sm" variant="outline" onClick={scan} isLoading={scanning}>Check for stray resources</Button>
          {orphans && orphans.length === 0 && <p className="text-sm text-success-700 mt-2">Nothing left behind.</p>}
          {orphans?.map((o) => (
            <div key={o.remote_id} className="flex items-center justify-between text-sm mt-2">
              <span>{o.name} ({o.provider}, {o.status})</span>
              <Button size="xs" variant="danger" onClick={async () => {
                try { await cloudApi.terminate(o.provider, o.remote_id); success('Terminated'); setOrphans(await cloudApi.orphans()); }
                catch (e) { error(errorText(e)); }
              }}>Terminate</Button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

export const CloudSettings: React.FC = () => {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [storage, setStorage] = useState<{ secure: boolean; detail: string } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setProviders(await cloudApi.providers());
      setStorage(await cloudApi.storage());
      setLoadError(null);
    } catch (e) {
      setLoadError(errorText(e));
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle><Cloud className="w-5 h-5 inline mr-2" />Cloud GPUs</CardTitle>
          <CardDescription>
            Rent a GPU to fine-tune or run models you can&apos;t fit locally, using your own accounts. Your dataset leaves this computer when you do.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadError && <p className="text-sm text-error-600">{loadError}</p>}
          {storage && !storage.secure && (
            <div className="flex gap-2 rounded-lg bg-warning-50 dark:bg-warning-900/20 p-3 text-sm text-warning-800 dark:text-warning-300">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              <span>Less secure storage: {storage.detail}. Credentials are still encrypted, but the key sits on disk next to them.</span>
            </div>
          )}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {providers.filter((p) => p.id !== 'ssh').map((p) => (
              <ProviderCard key={p.id} provider={p} onChanged={refresh} />
            ))}
          </div>
        </CardContent>
      </Card>
      <SshHosts />
      <Resources />
    </div>
  );
};

export default CloudSettings;
