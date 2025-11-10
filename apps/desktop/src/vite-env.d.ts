/// <reference types="vite/client" />

// Shims for Tauri plugins in type-checking environments
declare module "@tauri-apps/plugin-updater" {
  export interface UpdateCheckResult {
    available: boolean;
    currentVersion?: string;
    version?: string;
    downloadAndInstall: (onEvent?: (event: unknown) => void) => Promise<void>;
  }
  export function check(): Promise<UpdateCheckResult | null>;
}

declare module "@tauri-apps/api/process" {
  export function relaunch(): Promise<void>;
}