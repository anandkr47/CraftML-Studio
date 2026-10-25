/**
 * Register a remote model (Together, Replicate, RunPod serverless endpoint, or a server on one of
 * your SSH hosts). The model is tested before it is kept, so a broken entry never lingers.
 */

import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../ui/Button';
import { CatalogModel, ProviderId, ProviderInfo, SshProfile, cloudApi } from '../../api/cloud';
import { useNotificationStore } from '../../store/notificationStore';
import { errorText } from '../../api/errors';

const field = 'w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-2 py-2 text-xs';

export const AddCloudModel: React.FC<{ onAdded: () => void }> = ({ onAdded }) => {
  const { success, error } = useNotificationStore();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [hosts, setHosts] = useState<SshProfile[]>([]);
  const [provider, setProvider] = useState<ProviderId | ''>('');
  const [name, setName] = useState('');
  const [remoteModel, setRemoteModel] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [catalog, setCatalog] = useState<CatalogModel[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    cloudApi.providers().then((p) => setProviders(p.filter((x) => x.capabilities.inference && x.configured))).catch(() => undefined);
    cloudApi.sshProfiles().then((s) => setHosts(s.filter((h) => h.inference_port))).catch(() => undefined);
  }, []);

  useEffect(() => {
    setCatalog([]);
    if (provider === 'together' || provider === 'replicate') cloudApi.catalog(provider).then(setCatalog).catch(() => undefined);
  }, [provider]);

  const needsEndpoint = provider === 'runpod' || provider === 'ssh';
  const valid = provider && /^[\w.-]{1,64}$/.test(name) && remoteModel.trim() && (!needsEndpoint || endpoint.trim());

  const add = async () => {
    if (!provider) return;
    setBusy(true);
    let created: string | null = null;
    try {
      const model = await cloudApi.addModel({ provider, name, remote_model: remoteModel.trim(), endpoint_id: needsEndpoint ? endpoint.trim() : null });
      created = model.id;
      const test = await cloudApi.testModel(model.id);
      success('Cloud model ready', test.detail);
      setName(''); setRemoteModel(''); setEndpoint('');
      onAdded();
    } catch (e) {
      error(errorText(e));
      if (created) await cloudApi.deleteModel(created).catch(() => undefined); // don't keep a model that doesn't work
    } finally {
      setBusy(false);
    }
  };

  if (providers.length === 0 && hosts.length === 0) {
    return (
      <p className="text-xs text-neutral-500">
        Connect Together, Replicate, RunPod or an SSH host with an inference port in <Link to="/settings" className="text-brand-600 underline">Settings → Cloud GPUs</Link>.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <select className={field} value={provider} onChange={(e) => { setProvider(e.target.value as ProviderId); setEndpoint(''); }}>
        <option value="">Provider…</option>
        {providers.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
        {hosts.length > 0 && !providers.some((p) => p.id === 'ssh') && <option value="ssh">SSH host</option>}
      </select>
      <input className={field} placeholder="Name shown in Chat (e.g. llama-70b)" value={name} onChange={(e) => setName(e.target.value)} />
      <input className={field} list="cloud-catalog" placeholder={provider === 'replicate' ? 'owner/model' : 'Provider model id'} value={remoteModel} onChange={(e) => setRemoteModel(e.target.value)} />
      <datalist id="cloud-catalog">{catalog.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</datalist>
      {provider === 'runpod' && <input className={field} placeholder="Serverless endpoint id" value={endpoint} onChange={(e) => setEndpoint(e.target.value)} />}
      {provider === 'ssh' && (
        <select className={field} value={endpoint} onChange={(e) => setEndpoint(e.target.value)}>
          <option value="">Host…</option>
          {hosts.map((h) => <option key={h.name} value={h.name}>{h.name} (port {h.inference_port})</option>)}
        </select>
      )}
      <Button size="sm" fullWidth isLoading={busy} disabled={!valid} onClick={add}>Add &amp; test</Button>
      <p className="text-xs text-neutral-500">Your messages are sent to the provider. Usage is billed to your account there.</p>
    </div>
  );
};

export default AddCloudModel;
