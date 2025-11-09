/**
 * API Type Definitions
 * TypeScript interfaces for all API requests and responses
 */

// ============================================================================
// Common Types
// ============================================================================

export interface ApiResponse<T = any> {
  status: string;
  data?: T;
  message?: string;
  error?: string;
}

export interface JobResponse {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================================
// Hardware Types
// ============================================================================

export interface HardwareInfo {
  platform: string;
  device_type: 'cuda' | 'rocm' | 'mps' | 'cpu';
  device_name: string;
  backend: 'cuda' | 'rocm' | 'metal' | 'cpu';
  cuda_available: boolean;
  rocm_available: boolean;
  mps_available: boolean;
  gpu_count: number;
  total_vram_gb: number;
  recommended_strategy: 'lora' | 'qlora' | 'full';
}

export interface TrainingRecommendation {
  device: string;
  device_map: string | null;
  strategy: 'lora' | 'qlora' | 'full';
  use_4bit: boolean;
  use_8bit: boolean;
  fp16: boolean;
  bf16: boolean;
  use_flash_attention: boolean;
  gradient_checkpointing: boolean;
  per_device_train_batch_size: number;
  gradient_accumulation_steps: number;
}

export interface BackendInfo {
  cuda: {
    available: boolean;
    description: string;
    platforms: string[];
  };
  rocm: {
    available: boolean;
    description: string;
    platforms: string[];
  };
  metal: {
    available: boolean;
    description: string;
    platforms: string[];
  };
  cpu: {
    available: boolean;
    description: string;
    platforms: string[];
  };
  current_backend: string;
}

export interface TrainingStrategy {
  name: string;
  description: string;
  vram_required_gb: number;
  recommended: boolean;
  speed: string;
  quality: string;
}

// ============================================================================
// Training Types
// ============================================================================

export interface TrainingStartRequest {
  model_name: string;
  dataset_path: string;
  output_dir?: string;
  lora_config?: LoRAConfig;
  training_config?: TrainingConfig;
}

export interface LoRAConfig {
  r?: number;
  lora_alpha?: number;
  lora_dropout?: number;
  target_modules?: string[];
}

export interface TrainingConfig {
  num_epochs?: number;
  batch_size?: number;
  learning_rate?: number;
  warmup_steps?: number;
  use_4bit?: boolean;
  use_8bit?: boolean;
  max_grad_norm?: number;
}

export interface TrainingStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress?: {
    current_epoch: number;
    total_epochs: number;
    current_step: number;
    total_steps: number;
    loss: number | null;
  };
  params?: {
    model_name?: string;
    dataset_path?: string;
    training_method?: string;
    train_from_scratch?: boolean;
    model_type?: string;
    [key: string]: any;
  };
  metrics?: Record<string, any>;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export interface TrainingJob {
  job_id: string;
  status: string;
  started_at: string;
  model_name?: string;
}

export interface TrainingJobCounts {
  total: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
  pending: number;
}

// ============================================================================
// Crawler Types
// ============================================================================

export interface CrawlerStartRequest {
  seed_urls: string[];
  max_depth?: number;
  max_pages?: number;
  timeout?: number;
  batch_size?: number;
  use_playwright?: boolean;
  headless?: boolean;
  query?: string;
  ai_filter?: boolean;
  relevance_threshold?: number;
  top_k?: number;
  use_faiss?: boolean;
}

export interface CrawlerStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: {
    pages_crawled: number;
    pages_total: number;
    current_url: string | null;
  };
  batches?: Array<{
    batch_id: number;
    pages: number;
    cleaned: boolean;
  }>;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export interface CrawledPage {
  url: string;
  title: string;
  content: string;
  timestamp: string;
}

export interface CrawlerJob {
  job_id: string;
  status: string;
  started_at: string;
  pages_crawled?: number;
}

// ============================================================================
// Compression Types
// ============================================================================

export interface CompressionStartRequest {
  model_path: string;
  output_path: string;
  method: 'int8' | 'int4' | 'gptq' | 'pruning' | 'distillation';
  options?: Record<string, any>;
}

export interface CompressionStatus {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  method?: string;
  started_at?: string;
  completed_at?: string;
  result?: {
    output_path: string;
    compression_ratio?: number;
    size_reduction_mb?: number;
  };
  error?: string;
}

export interface ModelComparison {
  model_a: {
    path: string;
    total_params: number;
    trainable_params: number;
    size_mb: number;
  };
  model_b: {
    path: string;
    total_params: number;
    trainable_params: number;
    size_mb: number;
  };
  compression_ratio: string;
  size_reduction_mb: number;
  size_reduction_percent: number;
}

// ============================================================================
// Deployment Types
// ============================================================================

export interface LocalDeploymentRequest {
  model_path: string;
  port?: number;
  device?: string;
}

export interface HuggingFaceDeploymentRequest {
  model_path: string;
  repo_name: string;
  hf_token?: string;
  private?: boolean;
  create_space?: boolean;
}

export interface DeploymentInfo {
  deployment_id: string;
  type: 'local' | 'huggingface' | 'docker';
  status: 'pending' | 'deploying' | 'running' | 'completed' | 'failed' | 'stopped';
  url?: string;
  endpoints?: Record<string, string>;
  started_at?: string;
  progress?: number;
  error?: string;
}

// ============================================================================
// Model Conversion Types
// ============================================================================

export interface ConversionRequest {
  model_path: string;
  output_format: 'gguf' | 'onnx' | 'safetensors';
  output_path: string;
  quantization?: string;
  opset_version?: number;
  optimize?: boolean;
}

export interface ConversionResult {
  status: 'success' | 'failed';
  output_path?: string;
  format?: string;
  size_mb?: number;
  quantization?: string;
  error?: string;
}

export interface SupportedFormat {
  description: string;
  quantizations?: string[];
  optimizations?: boolean;
  use_case: string;
}

// ============================================================================
// Docker Types
// ============================================================================

export interface DockerBuildRequest {
  model_path: string;
  image_name: string;
  output_dir: string;
  device?: 'cpu' | 'gpu';
  port?: number;
}

export interface DockerBuildResult {
  status: 'success' | 'failed';
  image_name?: string;
  build_dir?: string;
  dockerfile?: string;
  docker_compose?: string;
  usage?: {
    run: string;
    compose: string;
  };
  error?: string;
}

// ============================================================================
// Task & Job Types
// ============================================================================

export interface TaskStatus {
  task_id: string;
  state: 'PENDING' | 'STARTED' | 'RETRY' | 'FAILURE' | 'SUCCESS';
  info?: any;
  result?: any;
  traceback?: string;
}

export interface JobHistoryItem {
  job_id: string;
  type: 'training' | 'crawler' | 'compression' | 'deployment';
  status: string;
  started_at: string;
  completed_at?: string;
  params?: Record<string, any>;
}

export interface JobStats {
  total_jobs: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  success_rate: number;
}

// ============================================================================
// Deduplication Types
// ============================================================================

export interface DeduplicationRequest {
  texts: string[];
  method: 'hash' | 'semantic' | 'hybrid';
  threshold?: number;
  namespace?: string;
  use_faiss?: boolean;
}

export interface DeduplicationResult {
  unique_texts: string[];
  duplicates_removed: number;
  method_used: string;
  processing_time_ms: number;
}

export interface DeduplicationStats {
  total_hashes: number;
  namespace_count: number;
  memory_usage_mb: number;
}

// ============================================================================
// Monitoring Types
// ============================================================================

export interface SystemMetrics {
  cpu: {
    cpu_count: number;
    cpu_percent: number;
    cpu_percent_per_core: number[];
  };
  memory: {
    total: number;
    available: number;
    used: number;
    percent: number;
  };
  disk: {
    total: number;
    used: number;
    free: number;
    percent: number;
  };
  gpus: GPUInfo[];
  timestamp: string;
}

export interface GPUInfo {
  id: number;
  name: string;
  memory_total: number;
  memory_used: number;
  memory_free: number;
  memory_util: number;
  gpu_util: number;
  temperature: number;
}

// ============================================================================
// Dataset Types
// ============================================================================

export interface DatasetSummary {
  dataset_id: string;
  name: string;
  path: string;
  size_mb: number;
  num_samples?: number;
  created_at: string;
  format: 'jsonl' | 'csv' | 'txt';
}

export interface DatasetUploadResponse {
  dataset_id: string;
  name: string;
  num_samples: number;
  uploaded_at: string;
  path: string;
}

export interface DatasetConvertRequest {
  input_path: string;
  output_path: string;
  output_format: 'jsonl' | 'csv' | 'instruction' | 'chat';
  text_column?: string;
  label_column?: string;
}

// ============================================================================
// Model Hub Types
// ============================================================================

export interface ModelSearchResult {
  id: string;
  name: string;
  author: string;
  downloads: number;
  likes: number;
  tags: string[];
  description?: string;
  model_type?: string;
}

export interface LocalModel {
  name: string;
  path: string;
  size_mb: number;
  downloaded_at: string;
}

// ============================================================================
// WebSocket Types
// ============================================================================

export interface WebSocketMessage {
  type: 'log' | 'metric' | 'status' | 'system';
  job_id?: string;
  data: any;
  timestamp: string;
}

export interface LogMessage {
  job_id: string;
  message: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  timestamp: string;
}

export interface MetricMessage {
  job_id: string;
  metrics: Record<string, number>;
  timestamp: string;
}

