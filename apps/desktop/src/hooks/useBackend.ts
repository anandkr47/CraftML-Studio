/**
 * Hook to manage backend process from frontend
 */

import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';

export function useBackend() {
  const [backendStatus, setBackendStatus] = useState<string>('unknown');
  const [isStarting, setIsStarting] = useState(false);

  const checkStatus = async () => {
    try {
      const status = await invoke<string>('backend_status');
      setBackendStatus(status);
    } catch (error) {
      console.error('Failed to check backend status:', error);
      setBackendStatus('error');
    }
  };

  const startBackend = async () => {
    setIsStarting(true);
    try {
      const result = await invoke<string>('start_backend');
      console.log('Backend start result:', result);
      await checkStatus();
    } catch (error) {
      console.error('Failed to start backend:', error);
    } finally {
      setIsStarting(false);
    }
  };

  const stopBackend = async () => {
    try {
      const result = await invoke<string>('stop_backend');
      console.log('Backend stop result:', result);
      await checkStatus();
    } catch (error) {
      console.error('Failed to stop backend:', error);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 5000); // Check every 5 seconds
    return () => clearInterval(interval);
  }, []);

  return {
    backendStatus,
    isStarting,
    startBackend,
    stopBackend,
    checkStatus,
  };
}

