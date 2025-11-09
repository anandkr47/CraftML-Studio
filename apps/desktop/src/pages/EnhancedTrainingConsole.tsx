/**
 * Enhanced Training Console Page
 * Professional training interface with step-by-step workflow
 */

import React, { useEffect, useState } from 'react';
import {
  Play,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  ChevronRight,
  Square,
  Trash2,
  Eye,
} from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Progress } from '../components/ui/Progress';
import { HStack, VStack } from '../components/ui/Stack';
import { Table, Column } from '../components/ui/Table';
import { ModelSelector } from '../components/ModelSelector';
import { DatasetSelector } from '../components/DatasetSelector';
import { TrainingConfigPanel } from '../components/TrainingConfigPanel';
import { TrainingComparison } from '../components/TrainingComparison';
import { TrainingMethodSelector, TrainingMethod } from '../components/TrainingMethodSelector';
import {
  fetchTrainingJobs,
} from '../api/training';
import { useNotificationStore } from '../store/notificationStore';

interface ModelOption {
  id: string;
  name: string;
  description: string;
  size?: string;
  type: 'pretrained' | 'scratch';
  requiresHF: boolean;
}

interface TrainingConfig {
  epochs: number;
  learningRate: number;
  batchSize: number;
  warmupSteps: number;
  gradientAccumulation: number;
  loraRank?: number;
  loraAlpha?: number;
  loraDropout?: number;
}

interface Dataset {
  dataset_id?: string;
  id?: number;
  name: string;
  description?: string;
  format: string;
  size_mb: number;
  num_samples?: number;
  num_examples?: number;
  created_at: string;
  file_path?: string;
  quality_score?: number;
}

interface TrainingJob {
  job_id: string;
  dataset_id?: number;
  status: string;
  started_at: string;
  base_model?: string;
  model_name?: string;
  progress?: number;
  epochs?: number;
  current_epoch?: number;
}

const EnhancedTrainingConsole: React.FC = () => {
  // Model & Config State
  const [selectedModel, setSelectedModel] = useState<ModelOption | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [trainingMethod, setTrainingMethod] = useState<TrainingMethod>('qlora');
  const [config, setConfig] = useState<TrainingConfig>({
    epochs: 3,
    learningRate: 0.0002,
    batchSize: 8,
    warmupSteps: 100,
    gradientAccumulation: 2,
    loraRank: 16,
    loraAlpha: 32,
    loraDropout: 0.1,
  });

  // Job State
  const [loading, setLoading] = useState(false);
  const [jobHistory, setJobHistory] = useState<TrainingJob[]>([]);

  // UI State
  const [showComparison, setShowComparison] = useState(false);

  const { success: showSuccess, error: showError } = useNotificationStore();

  useEffect(() => {
    loadJobs();
    
    // Refresh job list every 5 seconds
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadJobs = async () => {
    try {
      const jobs = await fetchTrainingJobs();
      setJobHistory(Array.isArray(jobs) ? jobs : []);
    } catch (error) {
      showError('Failed to load training jobs');
      console.error('Error loading jobs:', error);
      setJobHistory([]);
    }
  };

  const handleStopJob = async (jobId: string) => {
    try {
      const response = await fetch(`http://127.0.0.1:5000/api/train/stop/${jobId}`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to stop job');
      }

      showSuccess('Training job stopped');
      await loadJobs();
    } catch (error) {
      showError('Failed to stop training job');
      console.error('Error stopping job:', error);
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    if (!confirm('Are you sure you want to delete this job? This cannot be undone.')) {
      return;
    }

    try {
      const response = await fetch(`http://127.0.0.1:5000/api/train/delete/${jobId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete job');
      }

      showSuccess('Training job deleted');
      await loadJobs();
    } catch (error: any) {
      showError(error.message || 'Failed to delete training job');
      console.error('Error deleting job:', error);
    }
  };

  const handleStartTraining = async () => {
    if (!selectedModel) {
      showError('Please select a model first');
      return;
    }

    if (!selectedDataset) {
      showError('Please select a dataset');
      return;
    }

    setLoading(true);
    try {
      const trainFromScratch = selectedModel.type === 'scratch';

      const payload: any = {
        dataset_path: selectedDataset.file_path || `resources/datasets/${selectedDataset.name}`,
        train_from_scratch: trainFromScratch,
        training_method: trainingMethod, // Add selected training method
        training_config: {
          num_epochs: config.epochs,
          batch_size: config.batchSize,
          learning_rate: config.learningRate,
          warmup_steps: config.warmupSteps,
          gradient_accumulation_steps: config.gradientAccumulation,
          use_4bit: trainingMethod === 'qlora', // Enable 4-bit for QLoRA
          use_8bit: false,
        },
      };

      // Add model_name only for fine-tuning
      if (!trainFromScratch) {
        payload.model_name = selectedModel.id;
        payload.lora_config = {
          r: config.loraRank || 16,
          lora_alpha: config.loraAlpha || 32,
          lora_dropout: config.loraDropout || 0.1,
        };
      } else {
        // Add model_type for training from scratch
        payload.model_type = selectedModel.id;
      }

      console.log('Training request payload:', payload);

      // Call backend API directly with correct payload
      const response = await fetch('http://127.0.0.1:5000/api/train/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        console.error('Training start error:', errorData);
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail || errorData);
        throw new Error(errorMessage);
      }

      const job = await response.json();
      showSuccess(`Training started! Opening logs in new tab...`);
      
      // Wait a moment to ensure DB write completes
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Refresh job list first to ensure it's in the UI
      await loadJobs();
      
      // Then open job view in new tab
      window.open(`/train/job/${job.job_id}`, '_blank');
    } catch (error: any) {
      showError(error.message || 'Failed to start training');
      console.error('Error starting training:', error);
    } finally {
      setLoading(false);
    }
  };


  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="success" size="sm">Completed</Badge>;
      case 'failed':
        return <Badge variant="error" size="sm">Failed</Badge>;
      case 'running':
      case 'queued':
        return <Badge variant="info" size="sm">Running</Badge>;
      default:
        return <Badge variant="default" size="sm">{status}</Badge>;
    }
  };

  // Calculate stats
  const totalJobs = jobHistory.length;
  const completedJobs = jobHistory.filter((j) => j.status === 'completed').length;
  const failedJobs = jobHistory.filter((j) => j.status === 'failed').length;
  const runningJobs = jobHistory.filter((j) => j.status === 'running' || j.status === 'queued').length;
  const activeJobs = jobHistory.filter((j) => j.status === 'running' || j.status === 'queued');

  // Step indicators
  const steps = [
    { number: 1, name: 'Select Model', completed: !!selectedModel },
    { number: 2, name: 'Select Dataset', completed: !!selectedDataset },
    { number: 3, name: 'Choose Method', completed: !!selectedModel && !!selectedDataset && !!trainingMethod },
    { number: 4, name: 'Configure Training', completed: !!selectedModel && !!selectedDataset && config.epochs > 0 },
    { number: 5, name: 'Start Training', completed: false },
  ];

  // Table columns
  const columns: Column<TrainingJob>[] = [
    {
      key: 'job_id',
      header: 'Job ID',
      render: (job) => (
        <button
          onClick={() => window.open(`/train/job/${job.job_id}`, '_blank')}
          className="font-mono text-sm text-brand-600 dark:text-brand-400 hover:underline cursor-pointer"
        >
          {job.job_id.substring(0, 12)}...
        </button>
      ),
    },
    {
      key: 'base_model',
      header: 'Model',
      render: (job) => (
        <span className="font-medium text-neutral-900 dark:text-neutral-100">
          {job.base_model || 'From Scratch'}
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
        <div className="min-w-[100px]">
          {job.status === 'running' || job.status === 'queued' ? (
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-neutral-600 dark:text-neutral-400">
                  Epoch {job.current_epoch || 0}/{job.epochs || 0}
                </span>
                <span className="text-neutral-600 dark:text-neutral-400">
                  {Math.round(((job.current_epoch || 0) / (job.epochs || 1)) * 100)}%
                </span>
              </div>
              <Progress
                value={((job.current_epoch || 0) / (job.epochs || 1)) * 100}
                size="sm"
              />
            </div>
          ) : (
            <span className="text-sm text-neutral-600 dark:text-neutral-400">
              {job.status === 'completed' ? '100%' : '-'}
            </span>
          )}
        </div>
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
    {
      key: 'actions',
      header: 'Actions',
      render: (job) => (
        <HStack spacing={2}>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => window.open(`/train/job/${job.job_id}`, '_blank')}
            title="View logs"
          >
            <Eye className="w-4 h-4" />
          </Button>
          
          {(job.status === 'running' || job.status === 'queued') && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => handleStopJob(job.job_id)}
              title="Stop training"
            >
              <Square className="w-4 h-4 text-warning-600" />
            </Button>
          )}
          
          {(job.status === 'completed' || job.status === 'failed' || job.status === 'stopped') && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => handleDeleteJob(job.job_id)}
              title="Delete job"
            >
              <Trash2 className="w-4 h-4 text-danger-600" />
            </Button>
          )}
        </HStack>
      ),
    },
  ];

  return (
    <Container maxWidth="2xl" className="py-6">
      <VStack spacing={6}>
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
            Training Console
          </h1>
          <p className="text-neutral-600 dark:text-neutral-400 mt-1">
            Train and fine-tune models with your datasets
          </p>
        </div>

        {/* Active Training Jobs - Docker Style */}
        {activeJobs.length > 0 && (
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="w-5 h-5 text-brand-600 dark:text-brand-400 animate-pulse" />
                <h3 className="font-semibold text-neutral-900 dark:text-neutral-100">
                  Active Training Jobs ({activeJobs.length})
                </h3>
              </div>
              <div className="space-y-3">
                {activeJobs.map((job) => (
                  <div
                    key={job.job_id}
                    className="flex items-center justify-between p-4 bg-brand-50 dark:bg-brand-900/10 rounded-lg border border-brand-200 dark:border-brand-800"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <Loader2 className="w-4 h-4 text-brand-600 dark:text-brand-400 animate-spin" />
                        <span className="font-mono text-sm font-medium text-neutral-900 dark:text-neutral-100">
                          {job.job_id}
                        </span>
                        {getStatusBadge(job.status)}
                      </div>
                      <div className="flex items-center gap-4 text-sm text-neutral-600 dark:text-neutral-400">
                        <span>Model: {job.base_model || 'From Scratch'}</span>
                        <span>•</span>
                        <span>
                          Epoch {job.current_epoch || 0}/{job.epochs || 0}
                        </span>
                        {job.progress && (
                          <>
                            <span>•</span>
                            <span>
                              {Math.round(((job.current_epoch || 0) / (job.epochs || 1)) * 100)}%
                            </span>
                          </>
                        )}
                      </div>
                      {job.epochs && job.current_epoch !== undefined && (
                        <div className="mt-2">
                          <Progress
                            value={((job.current_epoch || 0) / (job.epochs || 1)) * 100}
                            size="sm"
                          />
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => window.open(`/train/job/${job.job_id}`, '_blank')}
                      >
                        <Eye className="w-4 h-4 mr-2" />
                        View Logs
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => handleStopJob(job.job_id)}
                      >
                        <Square className="w-4 h-4 mr-2" />
                        Stop
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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

        {/* Progress Steps */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              {steps.map((step, index) => (
                <React.Fragment key={step.number}>
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex items-center justify-center w-10 h-10 rounded-full font-semibold ${
                        step.completed
                          ? 'bg-success-100 dark:bg-success-900/30 text-success-700 dark:text-success-300'
                          : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400'
                      }`}
                    >
                      {step.completed ? <CheckCircle2 className="w-5 h-5" /> : step.number}
                    </div>
                    <span
                      className={`text-sm font-medium ${
                        step.completed
                          ? 'text-neutral-900 dark:text-neutral-100'
                          : 'text-neutral-500 dark:text-neutral-400'
                      }`}
                    >
                      {step.name}
                    </span>
                  </div>
                  {index < steps.length - 1 && (
                    <ChevronRight className="w-5 h-5 text-neutral-400" />
                  )}
                </React.Fragment>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Step 1: Model Selection */}
        <ModelSelector onModelSelect={setSelectedModel} selectedModel={selectedModel} />

        {/* Step 2: Dataset Selection */}
        {selectedModel && (
          <DatasetSelector
            selectedModel={selectedModel}
            selectedDataset={selectedDataset}
            onDatasetSelect={setSelectedDataset}
          />
        )}

        {/* Step 2.5: Training Method Selection */}
        {selectedModel && selectedDataset && selectedModel.type === 'pretrained' && (
          <TrainingMethodSelector
            selectedModel={selectedModel}
            selectedMethod={trainingMethod}
            onMethodSelect={setTrainingMethod}
          />
        )}

        {/* Step 3: Training Configuration */}
        {selectedModel && selectedDataset && (
          <TrainingConfigPanel
            selectedModel={selectedModel}
            config={config}
            onChange={setConfig}
          />
        )}

        {/* Start Training Button */}
        {selectedModel && selectedDataset && (
          <Card>
            <CardContent className="pt-6">
              <HStack justify="between" align="center">
                <div>
                  <h3 className="font-semibold text-neutral-900 dark:text-neutral-100">
                    Ready to start training?
                  </h3>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
                    Model: {selectedModel.name} • Dataset: {selectedDataset.name} • Method: {trainingMethod.toUpperCase()} • Epochs: {config.epochs}
                  </p>
                </div>
                <HStack spacing={3}>
                  <Button
                    variant="primary"
                    onClick={handleStartTraining}
                    disabled={loading}
                  >
                    {loading ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Starting...</>
                    ) : (
                      <><Play className="w-4 h-4 mr-2" />Start Training</>
                    )}
                  </Button>
                </HStack>
              </HStack>
            </CardContent>
          </Card>
        )}

        {/* Job Comparison Toggle */}
        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="center">
              <div>
                <h3 className="font-semibold text-neutral-900 dark:text-neutral-100">
                  Job Comparison
                </h3>
                <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
                  Compare metrics between different training runs
                </p>
              </div>
              <Button
                variant={showComparison ? 'primary' : 'outline'}
                onClick={() => setShowComparison(!showComparison)}
              >
                {showComparison ? 'Hide' : 'Show'} Comparison
              </Button>
            </HStack>
          </CardContent>
        </Card>

        {/* Comparison View */}
        {showComparison && (
          <TrainingComparison jobs={jobHistory} onClose={() => setShowComparison(false)} />
        )}

        {/* Job History */}
        <Card>
          <CardContent className="pt-6">
            <h3 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-4">
              Training History
            </h3>
            {jobHistory.length > 0 ? (
              <Table data={jobHistory} columns={columns} />
            ) : (
              <div className="text-center py-12 text-neutral-500 dark:text-neutral-400">
                <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No training jobs yet. Start your first training above!</p>
              </div>
            )}
          </CardContent>
        </Card>
      </VStack>
    </Container>
  );
};

export default EnhancedTrainingConsole;

