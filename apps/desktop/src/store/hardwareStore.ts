/**
 * Hardware Store
 * Manages hardware detection and training recommendations
 */

import { create } from 'zustand';
import type { HardwareInfo, TrainingRecommendation, BackendInfo } from '../types/api.types';

interface HardwareStore {
  hardwareInfo: HardwareInfo | null;
  recommendation: TrainingRecommendation | null;
  backends: { backends: BackendInfo; current_backend: string } | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: number | null;

  // Actions
  setHardwareInfo: (info: HardwareInfo) => void;
  setRecommendation: (rec: TrainingRecommendation) => void;
  setBackends: (backends: { backends: BackendInfo; current_backend: string }) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clear: () => void;
}

export const useHardwareStore = create<HardwareStore>((set) => ({
  hardwareInfo: null,
  recommendation: null,
  backends: null,
  isLoading: false,
  error: null,
  lastUpdated: null,

  setHardwareInfo: (info) =>
    set({ hardwareInfo: info, lastUpdated: Date.now(), error: null }),

  setRecommendation: (rec) =>
    set({ recommendation: rec, lastUpdated: Date.now(), error: null }),

  setBackends: (backends) =>
    set({ backends, lastUpdated: Date.now(), error: null }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error, isLoading: false }),

  clear: () =>
    set({
      hardwareInfo: null,
      recommendation: null,
      backends: null,
      isLoading: false,
      error: null,
      lastUpdated: null,
    }),
}));

