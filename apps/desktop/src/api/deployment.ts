import { apiService } from '../services/api.service';

export async function startDeploymentJob(params: any) {
  // Decide deployment type
  if (params?.type === 'huggingface') {
    return apiService.deployHuggingFace({
      model_path: params.model_path,
      repo_name: params.repo_name,
      hf_token: params.hf_token,
      private: params.private,
      create_space: params.create_space,
    });
  }
  // default to local
  return apiService.deployLocal({
    model_path: params.model_path,
    port: params.port,
    device: params.device,
  });
}

export async function fetchDeploymentJobs() {
  return apiService.listDeployments();
}

export async function getDeploymentJobStatus(jobId: string) {
  return apiService.getDeploymentStatus(jobId);
}

export async function getDeploymentEndpoints() {
  return apiService.getActiveEndpoints();
}
