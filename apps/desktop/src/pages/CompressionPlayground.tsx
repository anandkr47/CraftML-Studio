/**
 * Compression Playground Page
 * Model compression tools with modern UI matching the design system
 */

import React, { useState, useEffect } from 'react';
import {
  Package,
  Zap,
  Scissors,
  GitCompare,
  Play,
  BarChart3,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { Table, Column } from '../components/ui/Table';
import { HStack, VStack } from '../components/ui/Stack';
import { Progress } from '../components/ui/Progress';
import {
  startCompressionJob,
  fetchCompressionJobs,
  getCompressionJobStatus,
  compareModels,
} from '../api/compression';
import { useNotificationStore } from '../store/notificationStore';

interface CompressionJob {
  job_id: string;
  type: string;
  status: string;
  created_at: string;
  model_name?: string;
  compression_ratio?: number;
}

const CompressionPlayground: React.FC = () => {
  const [jobs, setJobs] = useState<CompressionJob[]>([]);
  const [activeJob, setActiveJob] = useState<CompressionJob | null>(null);
  const [status, setStatus] = useState('');
  const [modelA, setModelA] = useState('');
  const [modelB, setModelB] = useState('');
  const [comparison, setComparison] = useState('');
  const [loading, setLoading] = useState(false);

  const { success: showSuccess, error: showError } = useNotificationStore();

  useEffect(() => {
    loadJobs();
  }, []);

  useEffect(() => {
    if (activeJob) {
      const interval = setInterval(async () => {
        try {
          const statusData = await getCompressionJobStatus(activeJob.job_id);
          setStatus(statusData.status);

          if (statusData.status === 'completed') {
            showSuccess('Compression job completed');
            clearInterval(interval);
            await loadJobs();
          } else if (statusData.status === 'failed') {
            showError('Compression job failed');
            clearInterval(interval);
            await loadJobs();
          }
        } catch (error) {
          console.error('Error polling job status:', error);
        }
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [activeJob]);

  const loadJobs = async () => {
    try {
      const data = await fetchCompressionJobs();
      // Ensure data is always an array
      setJobs(Array.isArray(data) ? data : []);
    } catch (error) {
      showError('Failed to load jobs');
      console.error('Error loading jobs:', error);
      setJobs([]);
    }
  };

  const handleStart = async (type: string) => {
    setLoading(true);
    try {
      const job = await startCompressionJob({ type });
      setActiveJob(job);
      setStatus('Started');
      showSuccess(`${type} job started`);
      await loadJobs();
    } catch (error) {
      showError('Failed to start compression job');
      console.error('Error starting compression:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async () => {
    if (!modelA || !modelB) {
      showError('Please enter both model names');
      return;
    }

    setLoading(true);
    try {
      const result = await compareModels(modelA, modelB);
      setComparison(result.comparison || 'No comparison available.');
      showSuccess('Models compared successfully');
    } catch (error) {
      showError('Failed to compare models');
      console.error('Error comparing models:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (jobStatus: string) => {
    switch (jobStatus) {
      case 'completed':
        return <Badge variant="success" size="sm">Completed</Badge>;
      case 'failed':
        return <Badge variant="danger" size="sm">Failed</Badge>;
      case 'running':
        return <Badge variant="info" size="sm">Running</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{jobStatus}</Badge>;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'quantize':
        return <Zap className="w-4 h-4 text-brand-500" />;
      case 'prune':
        return <Scissors className="w-4 h-4 text-warning-500" />;
      case 'distill':
        return <Package className="w-4 h-4 text-success-500" />;
      default:
        return <Package className="w-4 h-4 text-neutral-500" />;
    }
  };

  // Calculate stats
  const totalJobs = jobs.length;
  const completedJobs = jobs.filter(j => j.status === 'completed').length;
  const quantizeJobs = jobs.filter(j => j.type === 'quantize').length;
  const pruneJobs = jobs.filter(j => j.type === 'prune').length;
  const distillJobs = jobs.filter(j => j.type === 'distill').length;

  // Table columns
  const columns: Column<CompressionJob>[] = [
    {
      key: 'job_id',
      header: 'Job ID',
      render: (job) => (
        <span className="font-mono text-sm text-neutral-600 dark:text-neutral-400">
          {job.job_id.substring(0, 8)}...
        </span>
      ),
    },
    {
      key: 'type',
      header: 'Type',
      render: (job) => (
        <HStack spacing={2}>
          {getTypeIcon(job.type)}
          <span className="font-medium text-neutral-900 dark:text-neutral-100 capitalize">
            {job.type}
          </span>
        </HStack>
      ),
    },
    {
      key: 'model_name',
      header: 'Model',
      render: (job) => (
        <span className="text-sm text-neutral-600 dark:text-neutral-400">
          {job.model_name || 'N/A'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (job) => getStatusBadge(job.status),
    },
    {
      key: 'compression_ratio',
      header: 'Ratio',
      render: (job) => (
        <span className="text-sm text-neutral-600 dark:text-neutral-400">
          {job.compression_ratio ? `${job.compression_ratio.toFixed(1)}x` : '-'}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (job) => (
        <span className="text-sm text-neutral-600 dark:text-neutral-400">
          {new Date(job.created_at).toLocaleString()}
        </span>
      ),
    },
  ];

  return (
    <Container maxWidth="xl" className="py-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
          Compression Playground
        </h1>
        <p className="text-neutral-600 dark:text-neutral-400 mt-1">
          Optimize models with quantization, pruning, and distillation
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Total Jobs
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {totalJobs}
                </p>
              </VStack>
              <div className="p-3 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
                <Package className="w-6 h-6 text-brand-600 dark:text-brand-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Quantize
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {quantizeJobs}
                </p>
              </VStack>
              <div className="p-3 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
                <Zap className="w-6 h-6 text-brand-600 dark:text-brand-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Prune
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {pruneJobs}
                </p>
              </VStack>
              <div className="p-3 bg-warning-50 dark:bg-warning-900/20 rounded-lg">
                <Scissors className="w-6 h-6 text-warning-600 dark:text-warning-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Distill
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {distillJobs}
                </p>
              </VStack>
              <div className="p-3 bg-success-50 dark:bg-success-900/20 rounded-lg">
                <Package className="w-6 h-6 text-success-600 dark:text-success-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>
      </div>

      {/* Compression Methods */}
      <Card>
        <CardHeader>
          <CardTitle>Compression Methods</CardTitle>
          <CardDescription>Select a compression technique to optimize your model</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Button
              variant="outline"
              onClick={() => handleStart('quantize')}
              disabled={loading}
              icon={loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
              className="h-24 flex-col gap-2"
            >
              <span className="text-lg font-semibold">Quantize</span>
              <span className="text-xs text-neutral-600 dark:text-neutral-400">
                Reduce precision for faster inference
              </span>
            </Button>

            <Button
              variant="outline"
              onClick={() => handleStart('prune')}
              disabled={loading}
              icon={loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Scissors className="w-4 h-4" />}
              className="h-24 flex-col gap-2"
            >
              <span className="text-lg font-semibold">Prune</span>
              <span className="text-xs text-neutral-600 dark:text-neutral-400">
                Remove redundant parameters
              </span>
            </Button>

            <Button
              variant="outline"
              onClick={() => handleStart('distill')}
              disabled={loading}
              icon={loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Package className="w-4 h-4" />}
              className="h-24 flex-col gap-2"
            >
              <span className="text-lg font-semibold">Distill</span>
              <span className="text-xs text-neutral-600 dark:text-neutral-400">
                Transfer knowledge to smaller model
              </span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Active Job Status */}
      {activeJob && (
        <Card>
          <CardHeader>
            <CardTitle>Active Job</CardTitle>
            <CardDescription>Job ID: {activeJob.job_id}</CardDescription>
          </CardHeader>
          <CardContent>
            <VStack spacing={4}>
              <HStack justify="between">
                <div>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">Type</p>
                  <HStack spacing={2} className="mt-1">
                    {getTypeIcon(activeJob.type)}
                    <p className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 capitalize">
                      {activeJob.type}
                    </p>
                  </HStack>
                </div>
                <div>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">Status</p>
                  <p className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mt-1">
                    {status || 'Initializing...'}
                  </p>
                </div>
              </HStack>
            </VStack>
          </CardContent>
        </Card>
      )}

      {/* Model Comparison */}
      <Card>
        <CardHeader>
          <CardTitle>Model Comparison</CardTitle>
          <CardDescription>Compare compression results between two models</CardDescription>
        </CardHeader>
        <CardContent>
          <VStack spacing={4}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Input
                value={modelA}
                onChange={(e) => setModelA(e.target.value)}
                placeholder="Model A name or path"
              />
              <Input
                value={modelB}
                onChange={(e) => setModelB(e.target.value)}
                placeholder="Model B name or path"
              />
              <Button
                variant="outline"
                onClick={handleCompare}
                disabled={loading || !modelA || !modelB}
                icon={<GitCompare className="w-4 h-4" />}
              >
                Compare
              </Button>
            </div>
            {comparison && (
              <div className="bg-neutral-50 dark:bg-neutral-800 rounded-lg p-4 border border-neutral-200 dark:border-neutral-700">
                <pre className="text-sm text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
                  {comparison}
                </pre>
              </div>
            )}
          </VStack>
        </CardContent>
      </Card>

      {/* Job History */}
      <Card>
        <CardHeader>
          <CardTitle>Job History</CardTitle>
          <CardDescription>
            {jobs.length} job{jobs.length !== 1 ? 's' : ''} total, {completedJobs} completed
          </CardDescription>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <div className="text-center py-12">
              <Package className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
              <p className="text-lg font-medium text-neutral-900 dark:text-neutral-100 mb-2">
                No compression jobs yet
              </p>
              <p className="text-neutral-600 dark:text-neutral-400">
                Start your first compression job to see it here
              </p>
            </div>
          ) : (
            <Table data={jobs} columns={columns} />
          )}
        </CardContent>
      </Card>
    </Container>
  );
};

export default CompressionPlayground;
