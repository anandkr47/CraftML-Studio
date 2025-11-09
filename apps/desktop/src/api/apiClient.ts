/**
 * Legacy API Client - Deprecated
 * Use ../services/api.service.ts instead
 * 
 * This file is kept for backward compatibility only.
 */

import { apiService } from '../services/api.service';

// Re-export the unified API service
export const API_BASE = 'http://127.0.0.1:5000';

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => {
        return response;
      },
      (error: AxiosError) => {
        if (error.code === 'ECONNREFUSED') {
          console.error('Backend not running. Please start the backend server.');
        }
        return Promise.reject(error);
      }
    );
  }

  // Generic request methods
  async get<T>(url: string, params?: any): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  async post<T>(url: string, data?: any): Promise<T> {
    const response = await this.client.post<T>(url, data);
    return response.data;
  }

  async put<T>(url: string, data?: any): Promise<T> {
    const response = await this.client.put<T>(url, data);
    return response.data;
  }

  async delete<T>(url: string): Promise<T> {
    const response = await this.client.delete<T>(url);
    return response.data;
  }

  // Health check
  async healthCheck(): Promise<{ status: string; service: string }> {
    return this.get('/api/health');
  }

  // Crawler API
  async startCrawl(params: {
    seed_urls: string[];
    max_depth?: number;
    max_pages?: number;
  }): Promise<{ job_id: string }> {
    return this.post('/api/crawler/start', params);
  }

  async getCrawlStatus(jobId: string): Promise<any> {
    return this.get(`/api/crawler/status/${jobId}`);
  }

  async getCrawlPreview(jobId: string): Promise<any> {
    return this.get(`/api/crawler/preview/${jobId}`);
  }

  async stopCrawl(jobId: string): Promise<any> {
    return this.post(`/api/crawler/stop/${jobId}`);
  }

  async listCrawlJobs(): Promise<{ jobs: any[] }> {
    return this.get('/api/crawler/jobs');
  }

  // Training API
  async startTraining(params: {
    model_name: string;
    dataset_path: string;
    output_dir?: string;
    lora_config?: any;
    training_config?: any;
  }): Promise<{ job_id: string }> {
    return this.post('/api/train/start', params);
  }

  async getTrainingStatus(jobId: string): Promise<any> {
    return this.get(`/api/train/status/${jobId}`);
  }

  async getTrainingLogs(jobId: string): Promise<any> {
    return this.get(`/api/train/logs/${jobId}`);
  }

  async stopTraining(jobId: string): Promise<any> {
    return this.post(`/api/train/stop/${jobId}`);
  }

  async listTrainingJobs(): Promise<{ jobs: any[] }> {
    return this.get('/api/train/jobs');
  }

  async getTrainingJobCounts(): Promise<{
    total: number;
    running: number;
    completed: number;
    failed: number;
  }> {
    return this.get('/api/train/job_counts');
  }

  // Compression API
  async startCompression(params: {
    model_path: string;
    output_path: string;
    method: 'int8' | 'int4' | 'gptq' | 'pruning' | 'distillation';
    options?: any;
  }): Promise<{ job_id: string }> {
    return this.post('/api/compress/start', params);
  }

  async getCompressionStatus(jobId: string): Promise<any> {
    return this.get(`/api/compress/status/${jobId}`);
  }

  // Deployment API
  async deployLocal(params: {
    model_path: string;
    port?: number;
  }): Promise<{ deployment_id: string; url: string }> {
    return this.post('/api/deploy/local', params);
  }

  async deployHuggingFace(params: {
    model_path: string;
    repo_name: string;
    hf_token?: string;
    private?: boolean;
  }): Promise<{ repo_url: string }> {
    return this.post('/api/deploy/huggingface', params);
  }

  async listDeployments(): Promise<{ deployments: any[] }> {
    return this.get('/api/deploy/list');
  }

  async stopDeployment(deploymentId: string): Promise<any> {
    return this.post(`/api/deploy/stop/${deploymentId}`);
  }

  // Monitoring API
  async getSystemMetrics(): Promise<any> {
    return this.get('/api/monitor/system');
  }

  async getGPUMetrics(): Promise<any> {
    return this.get('/api/monitor/gpu');
  }

  async getResourceHistory(limit?: number): Promise<any> {
    return this.get('/api/monitor/history', { limit });
  }

  // Dataset API
  async listDatasets(): Promise<{ datasets: any[] }> {
    return this.get('/api/dataset/list');
  }

  async uploadDataset(file: File): Promise<{ dataset_id: string }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.post('/api/dataset/upload', formData);
  }

  async deleteDataset(datasetId: string): Promise<any> {
    return this.delete(`/api/dataset/${datasetId}`);
  }

  // Model Hub API
  async searchModels(query: string): Promise<any> {
    return this.get('/api/modelhub/search', { query });
  }

  async downloadModel(modelName: string): Promise<{ job_id: string }> {
    return this.post('/api/modelhub/download', { model_name: modelName });
  }

  async listLocalModels(): Promise<{ models: any[] }> {
    return this.get('/api/modelhub/local');
  }
}

// Export the new unified API service
export const api = apiService;
export default apiService;

