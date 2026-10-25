/**
 * Runtime configuration shared across the app.
 * The desktop shell starts the backend on 127.0.0.1:17860 (port 5000 collides with the macOS
 * AirPlay Receiver). Override the address with VITE_API_BASE at build/dev time.
 */
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:17860';

export const WS_BASE: string = API_BASE.replace(/^http/, 'ws');
