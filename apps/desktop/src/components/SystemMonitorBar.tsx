/**
 * System Monitor bar
 * Always-visible CPU / RAM / GPU readout at the bottom of the window.
 * Click to expand recent history and active out-of-memory alerts.
 */

import React, { useEffect, useState } from 'react';
import { AlertTriangle, ChevronUp, Cpu, MemoryStick, MonitorCog } from 'lucide-react';
import { LineChart } from './charts/LineChart';
import { useMonitorStore } from '../store/monitorStore';

const gb = (mb: number) => (mb / 1024).toFixed(1);

const level = (percent: number) =>
  percent >= 93 ? 'bg-error-500' : percent >= 85 ? 'bg-warning-500' : 'bg-brand-500';

const Meter: React.FC<{ icon: React.ReactNode; label: string; percent: number | null; detail: string }> = ({
  icon,
  label,
  percent,
  detail,
}) => (
  <div className="flex items-center gap-2 min-w-0" title={`${label}: ${detail}`}>
    <span className="text-neutral-400 shrink-0">{icon}</span>
    <span className="text-xs text-neutral-500 shrink-0">{label}</span>
    <div className="w-20 h-1.5 rounded-full bg-neutral-200 dark:bg-neutral-700 overflow-hidden shrink-0">
      {percent != null && <div className={`h-full ${level(percent)}`} style={{ width: `${Math.min(percent, 100)}%` }} />}
    </div>
    <span className="text-xs font-mono text-neutral-700 dark:text-neutral-300 truncate">{detail}</span>
  </div>
);

export const SystemMonitorBar: React.FC = () => {
  const { latest, history, connected, start, stop } = useMonitorStore();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    start();
    return stop;
  }, [start, stop]);

  const alerts = latest?.alerts ?? [];
  const critical = alerts.some((a) => a.severity === 'critical');
  const gpu = latest?.gpu;
  const labels = history.map((_, i) => i - history.length + 1);

  return (
    <div className="border-t border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
      {open && (
        <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4 border-b border-neutral-200 dark:border-neutral-800">
          {[
            { title: 'CPU %', data: history.map((h) => h.cpu.percent), color: '#6366f1' },
            { title: 'RAM %', data: history.map((h) => h.memory.percent), color: '#10b981' },
            ...(gpu ? [{ title: gpu.kind === 'apple' ? 'Unified memory %' : 'VRAM %', data: history.map((h) => h.gpu?.vram_percent ?? null), color: '#f59e0b' }] : []),
          ].map((chart) => (
            <div key={chart.title}>
              <p className="text-xs font-semibold uppercase text-neutral-500 mb-1">{chart.title}</p>
              <LineChart labels={labels} data={chart.data} label={chart.title} color={chart.color} height={90} />
            </div>
          ))}
          <div className="md:col-span-3 space-y-2">
            {alerts.length === 0 && <p className="text-sm text-neutral-500">No memory alerts.</p>}
            {alerts.map((a) => (
              <div
                key={a.id}
                className={`flex items-start gap-2 rounded-lg px-3 py-2 text-sm ${
                  a.severity === 'critical'
                    ? 'bg-error-50 text-error-800 dark:bg-error-900/20 dark:text-error-300'
                    : 'bg-warning-50 text-warning-800 dark:bg-warning-900/20 dark:text-warning-300'
                }`}
              >
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>
                  <strong>{a.title}.</strong> {a.message}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-6 px-4 py-1.5 text-left hover:bg-neutral-50 dark:hover:bg-neutral-800/50"
      >
        <span className={`h-2 w-2 rounded-full shrink-0 ${connected ? 'bg-success-500' : 'bg-neutral-400'}`} title={connected ? 'Live' : 'Reconnecting…'} />
        {latest ? (
          <>
            <Meter icon={<Cpu className="w-3.5 h-3.5" />} label="CPU" percent={latest.cpu.percent} detail={`${latest.cpu.percent.toFixed(0)}%`} />
            <Meter
              icon={<MemoryStick className="w-3.5 h-3.5" />}
              label="RAM"
              percent={latest.memory.percent}
              detail={`${gb(latest.memory.used_mb)} / ${gb(latest.memory.total_mb)} GB`}
            />
            {gpu && gpu.kind === 'nvidia' && (
              <>
                <Meter icon={<MonitorCog className="w-3.5 h-3.5" />} label="GPU" percent={gpu.util_percent} detail={`${(gpu.util_percent ?? 0).toFixed(0)}%`} />
                <Meter icon={<MemoryStick className="w-3.5 h-3.5" />} label="VRAM" percent={gpu.vram_percent} detail={`${gb(gpu.vram_used_mb)} / ${gb(gpu.vram_total_mb)} GB`} />
              </>
            )}
            {gpu && gpu.kind === 'apple' && (
              <Meter
                icon={<MonitorCog className="w-3.5 h-3.5" />}
                label="GPU"
                percent={null}
                detail={gpu.app_gpu_mb != null ? `${gb(gpu.app_gpu_mb)} GB in use by app (unified memory)` : 'unified memory'}
              />
            )}
          </>
        ) : (
          <span className="text-xs text-neutral-500">Connecting to system monitor…</span>
        )}
        <span className="flex-1" />
        {alerts.length > 0 && (
          <span className={`flex items-center gap-1 text-xs font-medium ${critical ? 'text-error-600' : 'text-warning-600'}`}>
            <AlertTriangle className="w-3.5 h-3.5" /> {alerts.length} alert{alerts.length > 1 ? 's' : ''}
          </span>
        )}
        <ChevronUp className={`w-4 h-4 text-neutral-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
    </div>
  );
};

export default SystemMonitorBar;
