/**
 * Training Console Page
 * Model training interface with modern UI matching the design system
 */

import React, { useEffect, useState } from 'react';
import {
  Play,
  Square,
  GitCompare,
  BarChart3,
  Cpu,
  Download,
  FileText,
  Loader2,
  CheckCircle2,
  XCircle,
  Activity,
} from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { Select } from '../components/ui/Select';
import { Table, Column } from '../components/ui/Table';
import { HStack, VStack } from '../components/ui/Stack';
import { Progress } from '../components/ui/Progress';
import LogsPanel from '../components/LogsPanel';
import ModelHubPanel from '../components/ModelHubPanel';
import { ModelSelector } from '../components/ModelSelector';
import {
  fetchTrainingJobs,
  startTrainingJob,
  getTrainingJobStatus,
  getTrainingJobLogs,
} from '../api/training';
import { compareTrainingJobs } from '../api/trainingCompare';
import { useNotificationStore } from '../store/notificationStore';

interface ModelOption {
  id: string;
  name: string;
  description: string;
  size?: string;
  type: 'pretrained' | 'scratch';
  requiresHF: boolean;
}

interface TrainingJob {
  job_id: string;
  dataset_id: number;
  status: string;
  started_at: string;
  base_model?: string;
  progress?: number;
  epochs?: number;
  current_epoch?: number;
}

const TrainingConsole: React.FC = () => {
  const [activeJob, setActiveJob] = useState<TrainingJob | null>(null);
  const [jobStatus, setJobStatus] = useState('');
  const [logs, setLogs] = useState('');
  const [loading, setLoading] = useState(false);
  const [jobHistory, setJobHistory] = useState<TrainingJob[]>([]);
  const [datasetId, setDatasetId] = useState<number>(1);
  const [selectedModel, setSelectedModel] = useState<ModelOption | null>(null);
  const [baseModel, setBaseModel] = useState<string>('');
  const [epochs, setEpochs] = useState<number>(3);
  const [learningRate, setLearningRate] = useState<number>(0.0001);
  const [batchSize, setBatchSize] = useState<number>(8);
  const [trainingMethod, setTrainingMethod] = useState<'qlora' | 'lora' | 'full'>('qlora');
  const [jobA, setJobA] = useState('');
  const [jobB, setJobB] = useState('');
  const [comparison, setComparison] = useState('');
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);

  const { success: showSuccess, error: showError, info: showInfo } = useNotificationStore();

  useEffect(() => {
    loadJobs();
  }, []);

  useEffect(() => {
    if (activeJob) {
      // Poll for status and logs
      const interval = setInterval(async () => {
        try {
          const statusData = await getTrainingJobStatus(activeJob.job_id);
          setJobStatus(statusData.status);

          // Update active job with progress data
          if (statusData.progress) {
            setActiveJob(prev => ({
              ...prev,
              current_epoch: statusData.progress.current_epoch,
              total_epochs: statusData.progress.total_epochs,
              progress: statusData.progress
            }));
          }

          if (statusData.status === 'completed') {
            showSuccess('Training job completed successfully');
            clearInterval(interval);
            setPollingInterval(null);
            await loadJobs();
          } else if (statusData.status === 'failed') {
            showError('Training job failed');
            clearInterval(interval);
            setPollingInterval(null);
            await loadJobs();
          }

          // Get logs
          const logsData = await getTrainingJobLogs(activeJob.job_id);
          if (logsData.logs) {
            const logLines = Array.isArray(logsData.logs) 
              ? logsData.logs 
              : logsData.logs.split('\n').filter((l: string) => l.trim());
            setLogs(logLines.join('\n'));
          }
        } catch (error) {
          console.error('Error polling job status:', error);
        }
      }, 2000);

      setPollingInterval(interval);

      return () => {
        if (interval) clearInterval(interval);
      };
    }
  }, [activeJob]);

  const loadJobs = async () => {
    try {
      const jobs = await fetchTrainingJobs();
      // Ensure jobs is always an array
      setJobHistory(Array.isArray(jobs) ? jobs : []);
    } catch (error) {
      showError('Failed to load training jobs');
      console.error('Error loading jobs:', error);
      setJobHistory([]);
    }
  };

  const handleModelSelect = (model: ModelOption | null) => {
    setSelectedModel(model);
    if (model) {
      if (model.type === 'pretrained') {
        setBaseModel(model.id);
      } else {
        setBaseModel(''); // Clear base model for scratch training
      }
    }
  };

  const handleStartTraining = async () => {
    if (!selectedModel || !datasetId) {
      showError('Please select a model and dataset');
      return;
    }

    setLoading(true);
    try {
      const trainFromScratch = selectedModel.type === 'scratch';
      
      const job = await startTrainingJob({
        dataset_id: datasetId,
        params: {
          base_model: trainFromScratch ? null : selectedModel.id,
          train_from_scratch: trainFromScratch,
          model_type: trainFromScratch ? selectedModel.id : undefined,
          training_method: trainingMethod, // Add training method
          epochs,
          learning_rate: learningRate,
          batch_size: batchSize,
        },
      });
      setActiveJob(job);
      setJobStatus('Started');
      showSuccess(`Training job started${trainFromScratch ? ' from scratch' : ''}`);
      await loadJobs();
    } catch (error) {
      showError('Failed to start training');
      console.error('Error starting training:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStopTraining = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    showInfo('Training monitoring stopped');
  };

  const handleCompare = async () => {
    if (!jobA || !jobB) {
      showError('Please select two jobs to compare');
      return;
    }

    setLoading(true);
    try {
      const result = await compareTrainingJobs(jobA, jobB);
      setComparison(result.comparison || 'No comparison available.');
      showSuccess('Jobs compared successfully');
    } catch (error) {
      showError('Failed to compare jobs');
      console.error('Error comparing jobs:', error);
      setComparison('Failed to compare jobs');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="success" size="sm">Completed</Badge>;
      case 'failed':
        return <Badge variant="danger" size="sm">Failed</Badge>;
      case 'running':
        return <Badge variant="info" size="sm">Running</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{status}</Badge>;
    }
  };

  // Calculate stats
  const totalJobs = jobHistory.length;
  const completedJobs = jobHistory.filter(j => j.status === 'completed').length;
  const failedJobs = jobHistory.filter(j => j.status === 'failed').length;
  const runningJobs = jobHistory.filter(j => j.status === 'running').length;

  // Table columns
  const columns: Column<TrainingJob>[] = [
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
      key: 'base_model',
      header: 'Model',
      render: (job) => (
        <span className="font-medium text-neutral-900 dark:text-neutral-100">
          {job.base_model || 'N/A'}
        </span>
      ),
    },
    {
      key: 'dataset_id',
      header: 'Dataset',
      render: (job) => (
        <span className="text-sm text-neutral-600 dark:text-neutral-400">
          Dataset #{job.dataset_id}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (job) => getStatusBadge(job.status),
    },
    {
      key: 'progress',
      header: 'Progress',
      render: (job) => (
        <span className="text-sm text-neutral-600 dark:text-neutral-400">
          {job.current_epoch || 0} / {job.epochs || 0}
        </span>
      ),
    },
    {
      key: 'started_at',
      header: 'Started',
      render: (job) => (
        <span className="text-sm text-neutral-600 dark:text-neutral-400">
          {new Date(job.started_at).toLocaleString()}
        </span>
      ),
    },
  ];

  return (
    <Container maxWidth="xl" className="py-6">
      <div className="space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
              Training Console
            </h1>
            <p className="text-neutral-600 dark:text-neutral-400 mt-1">
              Train and fine-tune models with your datasets
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
                    <Activity className="w-6 h-6 text-brand-600 dark:text-brand-400" />
                  </div>
                </HStack>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <HStack justify="between" align="start">
                  <VStack spacing={1}>
                    <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                      Running
                    </p>
                    <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                      {runningJobs}
                    </p>
                  </VStack>
                  <div className="p-3 bg-info-50 dark:bg-info-900/20 rounded-lg">
                    <Loader2 className="w-6 h-6 text-info-600 dark:text-info-400" />
                  </div>
                </HStack>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <HStack justify="between" align="start">
                  <VStack spacing={1}>
                    <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                      Completed
                    </p>
                    <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                      {completedJobs}
                    </p>
                  </VStack>
                  <div className="p-3 bg-success-50 dark:bg-success-900/20 rounded-lg">
                    <CheckCircle2 className="w-6 h-6 text-success-600 dark:text-success-400" />
                  </div>
                </HStack>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <HStack justify="between" align="start">
                  <VStack spacing={1}>
                    <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                      Failed
                    </p>
                    <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                      {failedJobs}
                    </p>
                  </VStack>
                  <div className="p-3 bg-danger-50 dark:bg-danger-900/20 rounded-lg">
                    <XCircle className="w-6 h-6 text-danger-600 dark:text-danger-400" />
                  </div>
                </HStack>
              </CardContent>
            </Card>
          </div>

          {/* Model Selection */}
          <ModelSelector
            onModelSelect={handleModelSelect}
            selectedModel={selectedModel}
          />

          {/* Training Configuration */}
          <Card>
            <CardHeader>
              <CardTitle>Training Configuration</CardTitle>
              <CardDescription>Configure hyperparameters and training method</CardDescription>
            </CardHeader>
            <CardContent>
              <VStack spacing={4}>
                {/* Training Method Selector */}
                {selectedModel && selectedModel.type === 'pretrained' && (
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                      Training Method
                    </label>
                    <div className="grid grid-cols-3 gap-3">
                      <button
                        onClick={() => setTrainingMethod('qlora')}
                        className={`p-4 rounded-lg border-2 text-left transition-all ${
                          trainingMethod === 'qlora'
                            ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                            : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300'
                        }`}
                      >
                        <div className="font-semibold text-neutral-900 dark:text-neutral-100">QLoRA ⚡</div>
                        <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-1">
                          4-bit, Fastest, 50-75% less memory
                        </div>
                      </button>
                      <button
                        onClick={() => setTrainingMethod('lora')}
                        className={`p-4 rounded-lg border-2 text-left transition-all ${
                          trainingMethod === 'lora'
                            ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                            : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300'
                        }`}
                      >
                        <div className="font-semibold text-neutral-900 dark:text-neutral-100">LoRA 🚀</div>
                        <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-1">
                          Standard, Fast, Memory efficient
                        </div>
                      </button>
                      <button
                        onClick={() => setTrainingMethod('full')}
                        className={`p-4 rounded-lg border-2 text-left transition-all ${
                          trainingMethod === 'full'
                            ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                            : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300'
                        }`}
                      >
                        <div className="font-semibold text-neutral-900 dark:text-neutral-100">Full 🎯</div>
                        <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-1">
                          All parameters, Best quality
                        </div>
                      </button>
                    </div>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-2">
                      {trainingMethod === 'qlora' && '✨ Recommended: QLoRA is fastest and uses least memory - great for most use cases'}
                      {trainingMethod === 'lora' && '⚡ LoRA provides good balance between speed and quality'}
                      {trainingMethod === 'full' && '🎯 Full fine-tuning gives best results but requires more resources'}
                    </p>
                  </div>
                )}
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                      Dataset ID
                    </label>
                    <Input
                      type="number"
                      value={datasetId}
                      onChange={(e) => setDatasetId(Number(e.target.value))}
                      min={1}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                      Base Model
                    </label>
                    <Input
                      value={baseModel}
                      onChange={(e) => setBaseModel(e.target.value)}
                      placeholder="e.g., meta-llama/Llama-2-7b"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                      Epochs
                    </label>
                    <Input
                      type="number"
                      value={epochs}
                      onChange={(e) => setEpochs(Number(e.target.value))}
                      min={1}
                      max={100}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                      Learning Rate
                    </label>
                    <Input
                      type="number"
                      step="0.00001"
                      value={learningRate}
                      onChange={(e) => setLearningRate(Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                      Batch Size
                    </label>
                    <Input
                      type="number"
                      value={batchSize}
                      onChange={(e) => setBatchSize(Number(e.target.value))}
                      min={1}
                      max={128}
                    />
                  </div>
                </div>
                <HStack spacing={3}>
                  <Button
                    variant="primary"
                    onClick={handleStartTraining}
                    disabled={loading || (!baseModel && selectedModel?.type !== 'scratch')}
                    icon={loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  >
                    {loading ? 'Starting...' : 'Start Training'}
                  </Button>
                  <Button
                    variant="danger"
                    onClick={handleStopTraining}
                    disabled={!activeJob}
                    icon={<Square className="w-4 h-4" />}
                  >
                    Stop Monitoring
                  </Button>
                </HStack>
              </VStack>
            </CardContent>
          </Card>

          {/* Active Job Status */}
          {activeJob && (
            <Card>
              <CardHeader>
                <CardTitle>Active Training Job</CardTitle>
                <CardDescription>Job ID: {activeJob.job_id}</CardDescription>
              </CardHeader>
              <CardContent>
                <VStack spacing={4}>
                  <HStack justify="between">
                    <div>
                      <p className="text-sm text-neutral-600 dark:text-neutral-400">Status</p>
                      <p className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mt-1">
                        {jobStatus || 'Initializing...'}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-neutral-600 dark:text-neutral-400">Model</p>
                      <p className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mt-1">
                        {activeJob.base_model || baseModel}
                      </p>
                    </div>
                  </HStack>
                  {(activeJob.current_epoch !== undefined || activeJob.progress) && (
                    <div>
                      <HStack justify="between" className="mb-2">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">Training Progress</span>
                        <span className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                          Epoch {activeJob.current_epoch || activeJob.progress?.current_epoch || 0} / {activeJob.epochs || activeJob.progress?.total_epochs || 1}
                        </span>
                      </HStack>
                      <Progress 
                        value={((activeJob.current_epoch || activeJob.progress?.current_epoch || 0) / (activeJob.epochs || activeJob.progress?.total_epochs || 1)) * 100} 
                        variant="brand"
                      />
                      {activeJob.progress?.loss && (
                        <div className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
                          Loss: {activeJob.progress.loss.toFixed(4)}
                        </div>
                      )}
                    </div>
                  )}
                </VStack>
              </CardContent>
            </Card>
          )}

          {/* Logs */}
          <Card>
            <CardHeader>
              <CardTitle>Training Logs</CardTitle>
              <CardDescription>Real-time logs from the training process</CardDescription>
            </CardHeader>
            <CardContent>
              <LogsPanel logs={logs} />
            </CardContent>
          </Card>

          {/* Job Comparison */}
          <Card>
            <CardHeader>
              <CardTitle>Compare Training Jobs</CardTitle>
              <CardDescription>Compare metrics between two training runs</CardDescription>
            </CardHeader>
            <CardContent>
              <VStack spacing={4}>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Input
                    value={jobA}
                    onChange={(e) => setJobA(e.target.value)}
                    placeholder="Job A ID"
                  />
                  <Input
                    value={jobB}
                    onChange={(e) => setJobB(e.target.value)}
                    placeholder="Job B ID"
                  />
                  <Button
                    variant="outline"
                    onClick={handleCompare}
                    disabled={loading || !jobA || !jobB}
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
              <CardTitle>Training History</CardTitle>
              <CardDescription>
                {jobHistory.length} job{jobHistory.length !== 1 ? 's' : ''} total
              </CardDescription>
            </CardHeader>
            <CardContent>
              {jobHistory.length === 0 ? (
                <div className="text-center py-12">
                  <Activity className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
                  <p className="text-lg font-medium text-neutral-900 dark:text-neutral-100 mb-2">
                    No training jobs yet
                  </p>
                  <p className="text-neutral-600 dark:text-neutral-400">
                    Start your first training job to see it here
                  </p>
                </div>
              ) : (
                <Table data={jobHistory} columns={columns} />
              )}
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
              <CardDescription>Export metrics and manage trained models</CardDescription>
            </CardHeader>
            <CardContent>
              <HStack spacing={3} className="flex-wrap">
                <Button
                  variant="outline"
                  onClick={() => showInfo('Export metrics feature coming soon')}
                  icon={<BarChart3 className="w-4 h-4" />}
                >
                  Export Metrics
                </Button>
                <Button
                  variant="outline"
                  onClick={() => showInfo('Download model feature coming soon')}
                  icon={<Download className="w-4 h-4" />}
                >
                  Download Model
                </Button>
                <Button
                  variant="outline"
                  onClick={() => showInfo('View details feature coming soon')}
                  icon={<FileText className="w-4 h-4" />}
                >
                  View Details
                </Button>
              </HStack>
            </CardContent>
          </Card>
      </div>
    </Container>
  );
};

export default TrainingConsole;
