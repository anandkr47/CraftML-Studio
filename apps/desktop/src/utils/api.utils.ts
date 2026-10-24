/**
 * API Utility Functions
 * Helper functions for API calls, error handling, and data formatting
 */

import { AxiosError } from 'axios';
import { useNotificationStore } from '../store/notificationStore';

// ============================================================================
// Error Handling
// ============================================================================

export interface ApiError {
  message: string;
  code?: string;
  status?: number;
  details?: any;
}

/**
 * Parse API error and extract useful information
 */
export function parseApiError(error: unknown): ApiError {
  if (error instanceof AxiosError) {
    const data = error.response?.data;
    
    return {
      message: data?.message || data?.detail || error.message || 'An error occurred',
      code: data?.code || error.code,
      status: error.response?.status,
      details: data?.details,
    };
  }

  if (error instanceof Error) {
    return {
      message: error.message,
    };
  }

  return {
    message: String(error) || 'Unknown error',
  };
}

/**
 * Handle API error with notification
 */
export function handleApiError(error: unknown, context?: string): ApiError {
  const apiError = parseApiError(error);
  const { error: showError } = useNotificationStore.getState();
  
  const title = context || 'Error';
  const message = apiError.message;
  
  showError(title, message);
  
  console.error('[API Error]', {
    context,
    error: apiError,
  });
  
  return apiError;
}

/**
 * Async error wrapper with automatic error handling
 */
export async function withErrorHandling<T>(
  promise: Promise<T>,
  context?: string
): Promise<T | null> {
  try {
    return await promise;
  } catch (error) {
    handleApiError(error, context);
    return null;
  }
}

// ============================================================================
// Polling
// ============================================================================

export interface PollingOptions {
  interval: number; // milliseconds
  maxAttempts?: number;
  onUpdate?: (data: any) => void;
  stopCondition?: (data: any) => boolean;
}

/**
 * Poll an API endpoint until a condition is met
 */
export async function pollUntil<T>(
  fetchFn: () => Promise<T>,
  options: PollingOptions
): Promise<T> {
  let attempts = 0;
  const maxAttempts = options.maxAttempts ?? Infinity;

  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const data = await fetchFn();
        attempts++;

        if (options.onUpdate) {
          options.onUpdate(data);
        }

        if (options.stopCondition && options.stopCondition(data)) {
          resolve(data);
          return;
        }

        if (attempts >= maxAttempts) {
          reject(new Error('Max polling attempts reached'));
          return;
        }

        setTimeout(poll, options.interval);
      } catch (error) {
        reject(error);
      }
    };

    poll();
  });
}

/**
 * Poll job status until completion
 */
export async function pollJobStatus(
  getStatusFn: () => Promise<any>,
  options?: Partial<PollingOptions>
): Promise<any> {
  return pollUntil(getStatusFn, {
    interval: options?.interval ?? 2000,
    maxAttempts: options?.maxAttempts ?? 300, // 10 minutes with 2s interval
    onUpdate: options?.onUpdate,
    stopCondition: (data) => {
      const status = data?.status || data?.state;
      return status === 'completed' || status === 'failed' || status === 'SUCCESS' || status === 'FAILURE';
    },
  });
}

// ============================================================================
// Retry Logic
// ============================================================================

export interface RetryOptions {
  maxRetries: number;
  delay: number; // milliseconds
  backoff?: boolean; // exponential backoff
  onRetry?: (attempt: number, error: any) => void;
}

/**
 * Retry a function with exponential backoff
 */
export async function retry<T>(
  fn: () => Promise<T>,
  options: RetryOptions
): Promise<T> {
  let lastError: any;

  for (let attempt = 0; attempt <= options.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      if (attempt === options.maxRetries) {
        throw error;
      }

      const delay = options.backoff
        ? options.delay * Math.pow(2, attempt)
        : options.delay;

      if (options.onRetry) {
        options.onRetry(attempt + 1, error);
      }

      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw lastError;
}

// ============================================================================
// Data Formatting
// ============================================================================

/**
 * Format bytes to human-readable string
 */
export function formatBytes(bytes: number, decimals: number = 2): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Format number to human-readable string with commas
 */
export function formatNumber(num: number): string {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Format duration in milliseconds to human-readable string
 */
export function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    return `${days}d ${hours % 24}h`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

/**
 * Format timestamp to relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(timestamp: number | string): string {
  const now = Date.now();
  const then = typeof timestamp === 'string' ? new Date(timestamp).getTime() : timestamp;
  const diff = now - then;

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days} day${days > 1 ? 's' : ''} ago`;
  if (hours > 0) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  if (minutes > 0) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
  return 'Just now';
}

/**
 * Format percentage
 */
export function formatPercentage(value: number, decimals: number = 1): string {
  return `${value.toFixed(decimals)}%`;
}

// ============================================================================
// Validation
// ============================================================================

/**
 * Validate URL
 */
export function isValidUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * Validate job ID format
 */
export function isValidJobId(jobId: string): boolean {
  // Expected format: prefix_hash (e.g., train_abc123)
  return /^[a-z]+_[a-f0-9]+$/.test(jobId);
}

/**
 * Validate file extension
 */
export function hasValidExtension(filename: string, allowedExtensions: string[]): boolean {
  const ext = filename.split('.').pop()?.toLowerCase();
  return ext ? allowedExtensions.includes(ext) : false;
}

// ============================================================================
// Debounce & Throttle
// ============================================================================

/**
 * Debounce function
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      timeout = null;
      func(...args);
    };

    if (timeout !== null) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(later, wait);
  };
}

/**
 * Throttle function
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean;

  return function executedFunction(...args: Parameters<T>) {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

