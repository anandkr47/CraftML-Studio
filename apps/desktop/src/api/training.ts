import { apiService } from '../services/api.service';

export async function fetchTrainingJobs() {
  const res = await apiService.listTrainingJobs();
  // Backend returns { jobs: [...], total }; normalize
  // Some callers expect array; keep compatibility
  // @ts-ignore
  return Array.isArray(res) ? res : (res?.jobs ?? []);
}

export async function startTrainingJob(data: {
  dataset_id: number;
  params: any;
}) {
  return apiService.startTraining({
    model_name: data.params?.base_model,
    dataset_id: data.dataset_id, // Backend resolves this to a file path
    training_method: data.params?.training_method || 'qlora', // Default to QLoRA
    training_config: {
      num_epochs: data.params?.epochs || data.params?.num_epochs || 3,
      batch_size: data.params?.batch_size || 4,
      learning_rate: data.params?.learning_rate || 2e-4,
    },
    lora_config: data.params?.lora_config,
  } as any);
}

export async function getTrainingJobStatus(jobId: string) {
  try {
    return await apiService.getTrainingStatus(jobId);
  } catch (error) {
    console.error('Error fetching job status:', error);
    return { status: 'unknown', progress: null };
  }
}

export async function getTrainingJobLogs(jobId: string) {
  try {
    return await apiService.getTrainingLogs(jobId);
  } catch (error) {
    console.error('Error fetching job logs:', error);
    return { logs: 'Error loading logs' };
  }
}
