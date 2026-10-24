/**
 * Job State Management using Zustand
 * Tracks training, compression, and deployment jobs
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Job {
  id: string;
  type: 'training' | 'compression' | 'deployment';
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress?: number;
  startTime: number;
  endTime?: number;
  metadata?: any;
  logs?: string[];
}

interface JobStore {
  jobs: Job[];
  
  // Actions
  addJob: (job: Job) => void;
  updateJob: (id: string, updates: Partial<Job>) => void;
  removeJob: (id: string) => void;
  setJobs: (jobs: Job[]) => void;
  
  // Queries
  getJob: (id: string) => Job | undefined;
  getJobsByType: (type: Job['type']) => Job[];
  getRunningJobs: () => Job[];
  getRecentJobs: (limit?: number) => Job[];
  
  // Utilities
  clearCompleted: () => void;
  clearAll: () => void;
}

export const useJobStore = create<JobStore>()(
  persist(
    (set, get) => ({
      jobs: [],

      addJob: (job) => {
        set((state) => ({
          jobs: [...state.jobs, job],
        }));
      },

      updateJob: (id, updates) => {
        set((state) => ({
          jobs: state.jobs.map((job) =>
            job.id === id ? { ...job, ...updates } : job
          ),
        }));
      },

      removeJob: (id) => {
        set((state) => ({
          jobs: state.jobs.filter((job) => job.id !== id),
        }));
      },

      setJobs: (jobs) => {
        set({ jobs });
      },

      getJob: (id) => {
        return get().jobs.find((job) => job.id === id);
      },

      getJobsByType: (type) => {
        return get().jobs.filter((job) => job.type === type);
      },

      getRunningJobs: () => {
        return get().jobs.filter((job) => job.status === 'running');
      },

      getRecentJobs: (limit = 10) => {
        return get()
          .jobs.sort((a, b) => b.startTime - a.startTime)
          .slice(0, limit);
      },

      clearCompleted: () => {
        set((state) => ({
          jobs: state.jobs.filter(
            (job) => job.status !== 'completed' && job.status !== 'failed'
          ),
        }));
      },

      clearAll: () => {
        set({ jobs: [] });
      },
    }),
    {
      name: 'craftml-job-storage', // localStorage key
      partialize: (state) => ({
        jobs: state.jobs.slice(-100), // Only persist last 100 jobs
      }),
    }
  )
);

