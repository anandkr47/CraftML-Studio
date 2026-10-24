/**
 * Unified API Service
 * Complete integration with all backend endpoints
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import * as Types from '../types/api.types';
import { API_BASE } from '../config';

// API Configuration
export const API_BASE_URL = API_BASE;

class APIService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.code === 'ECONNREFUSED') {
          console.error('[API] Backend not running at', API_BASE_URL);
        }
        return Promise.reject(error);
      }
    );
  }

  // =========================================================================
  // Generic Methods
  // =========================================================================

  private async get<T>(url: string, params?: any): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  private async post<T>(url: string, data?: any, config?: any): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  private async delete<T>(url: string): Promise<T> {
    const response = await this.client.delete<T>(url);
    return response.data;
  }

  // =========================================================================
  // Health Check
  // =========================================================================

  async healthCheck(): Promise<{ status: string; service: string }> {
    return this.get('/api/health');
  }

  // =========================================================================
  // Hardware API
  // =========================================================================

  async getHardwareInfo(): Promise<Types.HardwareInfo> {
    return this.get('/api/hardware/info');
  }

  async getTrainingRecommendation(strategy?: string): Promise<Types.TrainingRecommendation> {
    return this.get('/api/hardware/recommend', { strategy });
  }

  async listBackends(): Promise<{ backends: Types.BackendInfo; current_backend: string }> {
    return this.get('/api/hardware/backends');
  }

  async listTrainingStrategies(): Promise<{
    strategies: Record<string, Types.TrainingStrategy>;
    recommended: string;
    your_vram_gb: number;
  }> {
    return this.get('/api/hardware/strategies');
  }

  // =========================================================================
  // Training API
  // =========================================================================

  async startTraining(params: Types.TrainingStartRequest): Promise<Types.JobResponse> {
    return this.post('/api/train/start', params);
  }

  async getTrainingStatus(jobId: string): Promise<Types.TrainingStatus> {
    return this.get(`/api/train/status/${jobId}`);
  }

  async getTrainingLogs(jobId: string, limit?: number, offset?: number): Promise<{
    job_id: string;
    logs: string[];
    total: number;
  }> {
    return this.get(`/api/train/logs/${jobId}`, { limit, offset });
  }

  async stopTraining(jobId: string): Promise<{ success: boolean }> {
    return this.post(`/api/train/stop/${jobId}`);
  }

  async listTrainingJobs(): Promise<{ jobs: Types.TrainingJob[] }> {
    return this.get('/api/train/jobs');
  }

  async getTrainingJobCounts(): Promise<Types.TrainingJobCounts> {
    return this.get('/api/train/job_counts');
  }

  // =========================================================================
  // Compression API
  // =========================================================================

  async startCompression(params: Types.CompressionStartRequest): Promise<Types.JobResponse> {
    return this.post('/api/compress/start', params);
  }

  async getCompressionStatus(jobId: string): Promise<Types.CompressionStatus> {
    return this.get(`/api/compress/status/${jobId}`);
  }

  async compareModels(modelAPath: string, modelBPath: string): Promise<Types.ModelComparison> {
    return this.post('/api/compress/compare', {
      model_a_path: modelAPath,
      model_b_path: modelBPath,
    });
  }

  async listCompressionJobs(): Promise<{ jobs: any[] }> {
    return this.get('/api/compress/jobs');
  }

  async listCompressionMethods(): Promise<{ methods: string[] }> {
    return this.get('/api/compress/methods');
  }

  // =========================================================================
  // Deployment API
  // =========================================================================

  async deployLocal(params: Types.LocalDeploymentRequest): Promise<{
    deployment_id: string;
    url: string;
    endpoints: Record<string, string>;
  }> {
    return this.post('/api/deploy/local', params);
  }

  async deployHuggingFace(params: Types.HuggingFaceDeploymentRequest): Promise<{
    deployment_id: string;
    repo_url: string;
    space_url?: string;
  }> {
    return this.post('/api/deploy/huggingface', params);
  }

  async getDeploymentStatus(deploymentId: string): Promise<Types.DeploymentInfo> {
    return this.get(`/api/deploy/status/${deploymentId}`);
  }

  async listDeployments(): Promise<{ deployments: Types.DeploymentInfo[] }> {
    return this.get('/api/deploy/list');
  }

  async stopDeployment(deploymentId: string): Promise<{ success: boolean }> {
    return this.post(`/api/deploy/stop/${deploymentId}`);
  }

  async getActiveEndpoints(): Promise<{ endpoints: any[] }> {
    return this.get('/api/deploy/endpoints');
  }

  // =========================================================================
  // Model Conversion API
  // =========================================================================

  async convertModel(params: Types.ConversionRequest): Promise<Types.ConversionResult> {
    return this.post('/api/convert/convert', params);
  }

  async getSupportedFormats(): Promise<{
    formats: string[];
    details: Record<string, Types.SupportedFormat>;
  }> {
    return this.get('/api/convert/supported-formats');
  }

  // =========================================================================
  // Docker API
  // =========================================================================

  async buildDockerImage(params: Types.DockerBuildRequest): Promise<Types.DockerBuildResult> {
    return this.post('/api/docker/build', params);
  }

  async checkDocker(): Promise<{ docker_available: boolean; message: string }> {
    return this.get('/api/docker/check');
  }

  async createDockerFiles(outputDir: string, device: string = 'cpu', port: number = 8000): Promise<{
    status: string;
    files: Record<string, string>;
    message: string;
  }> {
    return this.post('/api/docker/create-files', null, {
      params: { output_dir: outputDir, device, port },
    });
  }

  // =========================================================================
  // Job History API
  // =========================================================================

  async getJobHistory(jobType?: string, status?: string, limit?: number): Promise<{
    jobs: Types.JobHistoryItem[];
    total: number;
  }> {
    return this.get('/api/jobs/history', { job_type: jobType, status, limit });
  }

  async getJobDetails(jobId: string): Promise<Types.JobHistoryItem> {
    return this.get(`/api/jobs/${jobId}`);
  }

  async getJobLogs(jobId: string): Promise<{ job_id: string; logs: string[] }> {
    return this.get(`/api/jobs/${jobId}/logs`);
  }

  async getJobStats(): Promise<Types.JobStats> {
    return this.get('/api/jobs/stats');
  }

  async deleteJob(jobId: string): Promise<{ success: boolean; message: string }> {
    return this.delete(`/api/jobs/${jobId}`);
  }

  // =========================================================================
  // Monitoring API
  // =========================================================================

  async getSystemMetrics(): Promise<Types.SystemMetrics> {
    return this.get('/api/monitor/metrics');
  }

  async getGPUMetrics(): Promise<{ gpus: Types.GPUInfo[] }> {
    return this.get('/api/monitor/gpu');
  }

  async getCPUMetrics(): Promise<any> {
    return this.get('/api/monitor/cpu');
  }

  async getMemoryMetrics(): Promise<any> {
    return this.get('/api/monitor/memory');
  }

  async getDiskMetrics(): Promise<any> {
    return this.get('/api/monitor/disk');
  }

  // =========================================================================
  // Dataset API
  // =========================================================================

  async listDatasets(): Promise<{ datasets: Types.DatasetSummary[] }> {
    return this.get('/api/dataset/list');
  }

  async uploadDataset(file: File): Promise<Types.DatasetUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await this.client.post('/api/dataset-upload/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async getDatasetInfo(datasetId: string): Promise<Types.DatasetSummary> {
    return this.get(`/api/dataset/${datasetId}`);
  }

  async deleteDataset(datasetId: string): Promise<{ success: boolean }> {
    return this.delete(`/api/dataset/${datasetId}`);
  }

  async convertDataset(params: Types.DatasetConvertRequest): Promise<{
    success: boolean;
    output_path: string;
    samples: number;
  }> {
    return this.post('/api/dataset/convert', params);
  }

  // =========================================================================
  // Model Hub API
  // =========================================================================

  async searchModels(query: string, limit?: number): Promise<{
    models: Types.ModelSearchResult[];
    total: number;
  }> {
    return this.get('/api/modelhub/search', { query, limit });
  }

  async downloadModel(modelName: string, destination?: string): Promise<{
    job_id: string;
    message: string;
  }> {
    return this.post('/api/modelhub/download', { model_name: modelName, destination });
  }

  async listLocalModels(): Promise<{ models: Types.LocalModel[] }> {
    return this.get('/api/modelhub/local');
  }

  async getModelInfo(modelName: string): Promise<Types.ModelSearchResult> {
    return this.get(`/api/modelhub/info/${modelName}`);
  }
}

// Export singleton instance
export const apiService = new APIService();
export default apiService;

