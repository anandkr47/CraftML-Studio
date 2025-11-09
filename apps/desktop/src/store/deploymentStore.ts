/**
 * Deployment Store
 * Manages model deployments
 */

import { create } from 'zustand';
import type { DeploymentInfo } from '../types/api.types';

interface DeploymentStore {
  deployments: Record<string, DeploymentInfo>;
  activeDeployments: string[];

  // Actions
  addDeployment: (deployment: DeploymentInfo) => void;
  updateDeployment: (deploymentId: string, updates: Partial<DeploymentInfo>) => void;
  removeDeployment: (deploymentId: string) => void;
  setDeployments: (deployments: DeploymentInfo[]) => void;
  getDeployment: (deploymentId: string) => DeploymentInfo | undefined;
  getActiveDeployments: () => DeploymentInfo[];
  clearAll: () => void;
}

export const useDeploymentStore = create<DeploymentStore>((set, get) => ({
  deployments: {},
  activeDeployments: [],

  addDeployment: (deployment) => {
    set((state) => ({
      deployments: {
        ...state.deployments,
        [deployment.deployment_id]: deployment,
      },
      activeDeployments:
        deployment.status === 'running'
          ? [...state.activeDeployments, deployment.deployment_id]
          : state.activeDeployments,
    }));
  },

  updateDeployment: (deploymentId, updates) => {
    set((state) => {
      const existing = state.deployments[deploymentId];
      if (!existing) return state;

      const updated = { ...existing, ...updates };
      const isActive = updated.status === 'running';
      const wasActive = state.activeDeployments.includes(deploymentId);

      return {
        deployments: {
          ...state.deployments,
          [deploymentId]: updated,
        },
        activeDeployments:
          isActive && !wasActive
            ? [...state.activeDeployments, deploymentId]
            : !isActive && wasActive
            ? state.activeDeployments.filter((id) => id !== deploymentId)
            : state.activeDeployments,
      };
    });
  },

  removeDeployment: (deploymentId) => {
    set((state) => {
      const { [deploymentId]: removed, ...rest } = state.deployments;
      return {
        deployments: rest,
        activeDeployments: state.activeDeployments.filter((id) => id !== deploymentId),
      };
    });
  },

  setDeployments: (deployments) => {
    const deploymentsMap = deployments.reduce((acc, dep) => {
      acc[dep.deployment_id] = dep;
      return acc;
    }, {} as Record<string, DeploymentInfo>);

    const activeIds = deployments
      .filter((dep) => dep.status === 'running')
      .map((dep) => dep.deployment_id);

    set({
      deployments: deploymentsMap,
      activeDeployments: activeIds,
    });
  },

  getDeployment: (deploymentId) => {
    return get().deployments[deploymentId];
  },

  getActiveDeployments: () => {
    const state = get();
    return state.activeDeployments
      .map((id) => state.deployments[id])
      .filter(Boolean);
  },

  clearAll: () => {
    set({ deployments: {}, activeDeployments: [] });
  },
}));

