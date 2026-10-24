/**
 * Legacy API Client - Deprecated
 * Use ../services/api.service.ts instead
 * 
 * This file is kept for backward compatibility only.
 */

import { apiService } from '../services/api.service';
import { API_BASE } from '../config';

export { API_BASE };

// Re-export the unified API service only; legacy client removed to avoid TS errors
export const api = apiService;
export default apiService;

