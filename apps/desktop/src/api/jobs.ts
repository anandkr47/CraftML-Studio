import { apiService } from '../services/api.service';

export async function fetchJobCounts() {
  return apiService.getTrainingJobCounts();
}
