/**
 * Monitor Store
 * Live telemetry from /ws/monitor with automatic reconnection and a short history.
 */

import { create } from 'zustand';
import { Telemetry } from '../api/monitor';
import { WS_BASE } from '../config';
import { useNotificationStore } from './notificationStore';

const HISTORY = 60;
const RECONNECT_MS = 3000;

interface MonitorState {
  latest: Telemetry | null;
  history: Telemetry[];
  connected: boolean;
  start: () => void;
  stop: () => void;
}

let socket: WebSocket | null = null;
let retryTimer: number | undefined;
let wanted = false;
const notified = new Set<string>();

export const useMonitorStore = create<MonitorState>((set) => {
  const connect = () => {
    if (!wanted || socket) return;
    const ws = new WebSocket(`${WS_BASE}/ws/monitor`);
    socket = ws;

    ws.onopen = () => set({ connected: true });

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type !== 'metrics') return;
      const reading = data as Telemetry;
      set((s) => ({ latest: reading, history: [...s.history, reading].slice(-HISTORY) }));

      // Toast each alert once, until it clears.
      const active = new Set(reading.alerts.map((a) => a.id));
      notified.forEach((id) => !active.has(id) && notified.delete(id));
      reading.alerts.forEach((alert) => {
        if (notified.has(alert.id)) return;
        notified.add(alert.id);
        const { error, warning } = useNotificationStore.getState();
        (alert.severity === 'critical' ? error : warning)(alert.title, alert.message, 10000);
      });
    };

    ws.onclose = () => {
      socket = null;
      set({ connected: false });
      if (wanted) retryTimer = window.setTimeout(connect, RECONNECT_MS);
    };
    ws.onerror = () => ws.close();
  };

  return {
    latest: null,
    history: [],
    connected: false,
    start: () => {
      wanted = true;
      connect();
    },
    stop: () => {
      wanted = false;
      window.clearTimeout(retryTimer);
      socket?.close();
      socket = null;
    },
  };
});
