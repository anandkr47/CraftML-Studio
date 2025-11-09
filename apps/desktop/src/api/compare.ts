import { apiService } from '../services/api.service';

export async function compareDatasets(datasetA: number, datasetB: number) {
  // Fallback implementation: dataset comparison not exposed in unified API
  // Return a placeholder response to avoid UI errors
  return {
    status: 'success',
    comparison: `Dataset comparison between ${datasetA} and ${datasetB} is not available.`,
  } as any;
}

export async function compareModels(modelA: string, modelB: string) {
  return apiService.compareModels(modelA, modelB);
}
