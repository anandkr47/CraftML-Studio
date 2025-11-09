import { apiService } from "../services/api.service";

export async function fetchGpuInfo() {
  const res = await apiService.getSystemMetrics();
  if (res && Array.isArray(res.gpus) && res.gpus.length > 0) {
    const gpu = res.gpus[0];
    return {
      name: gpu.name,
      memoryUtil: gpu.memory_util / 100,
      load: gpu.gpu_util / 100,
    };
  }
  return null;
}
