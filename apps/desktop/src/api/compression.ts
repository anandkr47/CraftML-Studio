import { apiService } from '../services/api.service';

export async function startCompressionJob(params: any) {
  return apiService.startCompression(params);
}

export async function fetchCompressionJobs() {
  return apiService.listCompressionJobs();
}

export async function getCompressionJobStatus(jobId: string) {
  return apiService.getCompressionStatus(jobId);
}

export async function compareModels(modelA: string, modelB: string) {
  return apiService.compareModels(modelA, modelB);
}
