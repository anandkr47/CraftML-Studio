import { apiService } from '../services/api.service';

export async function fetchSystemMetrics() {
  return apiService.getSystemMetrics();
}
