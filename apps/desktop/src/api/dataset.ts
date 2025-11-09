import { apiService } from '../services/api.service';
import { DatasetSummary } from '../types/api.types';

export async function fetchDatasets(): Promise<{ datasets: DatasetSummary[] }> {
  return apiService.listDatasets();
}

export async function createDataset(_data: {
  name: string;
  file_path: string;
  token_count: number;
  quality_score: number;
}) {
  // Not present in new API; use upload endpoint instead
  return { success: true } as any;
}

export async function updateDataset(_datasetId: number, _data: Partial<{
  name: string;
  file_path: string;
  token_count: number;
  quality_score: number;
}>) {
  return { success: true } as any;
}

export async function deleteDataset(datasetId: number) {
  return apiService.deleteDataset(String(datasetId));
}
