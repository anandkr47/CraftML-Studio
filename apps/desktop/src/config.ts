/**
 * Runtime configuration shared across the app.
 * Override the backend address with VITE_API_BASE at build/dev time.
 */
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:5000';

export const WS_BASE: string = API_BASE.replace(/^http/, 'ws');
