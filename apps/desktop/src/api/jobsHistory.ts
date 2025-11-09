import { apiService } from '../services/api.service';

export async function fetchAllJobs() {
  return apiService.listTrainingJobs();
}

export async function fetchJobStatus(jobId: string) {
  return apiService.getTrainingStatus(jobId);
}
