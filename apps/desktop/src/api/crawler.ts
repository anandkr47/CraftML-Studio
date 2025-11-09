import { apiService } from '../services/api.service';

export async function startCrawlerJob(params: any) {
  return apiService.startCrawler(params);
}

export async function fetchCrawlerJobs() {
  return apiService.listCrawlerJobs();
}

export async function getCrawlerJobStatus(jobId: string) {
  return apiService.getCrawlerStatus(jobId);
}

export async function stopCrawlerJob(jobId: string) {
  return apiService.stopCrawler(jobId);
}

export async function getCrawlerPreview(jobId: string) {
  return apiService.getCrawlerPreview(jobId);
}
