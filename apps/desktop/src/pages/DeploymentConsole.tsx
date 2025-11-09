/**
 * Deployment Console Page
 * Model deployment interface with modern UI matching the design system
 */

import React, { useState, useEffect } from 'react';
import {
  Rocket,
  Server,
  Container as ContainerIcon,
  Cloud,
  GitCompare,
  ExternalLink,
  Loader2,
  CheckCircle2,
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
  startDeploymentJob,
  getDeploymentJobStatus,
  getDeploymentEndpoints,
} from '../api/deployment';
import { fetchAllJobs, fetchJobStatus } from '../api/jobsHistory';
import { compareModels } from '../api/compare';
import { useNotificationStore } from '../store/notificationStore';

interface DeploymentJob {
  job_id: string;
  type: string;
  status: string;
  started_at: string;
  progress?: number;
  endpoint?: string;
}

interface DeploymentResponse {
  deployment_id: string;
  url?: string;
  endpoints?: Record<string, string>;
  repo_url?: string;
  space_url?: string;
}

const DeploymentConsole: React.FC = () => {
  const [activeJob, setActiveJob] = useState<DeploymentJob | DeploymentResponse | null>(null);
  const [status, setStatus] = useState('');
  const [endpoints, setEndpoints] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [allJobs, setAllJobs] = useState<DeploymentJob[]>([]);
  const [jobStatuses, setJobStatuses] = useState<{ [key: string]: string }>({});
  const [progress, setProgress] = useState<number>(0);
  const [modelA, setModelA] = useState('');
  const [modelB, setModelB] = useState('');
  const [comparison, setComparison] = useState('');

  const { success: showSuccess, error: showError } = useNotificationStore();

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (activeJob && 'job_id' in activeJob) {
      // Poll for status updates
      const interval = setInterval(async () => {
        try {
          const statusData = await getDeploymentJobStatus(activeJob.job_id);
          setStatus(statusData.status);
          setProgress(typeof statusData.progress === 'number' ? statusData.progress : 0);

          if (statusData.status === 'completed') {
            showSuccess('Deployment completed successfully');
            clearInterval(interval);
            await loadData();
          } else if (statusData.status === 'failed') {
            showError('Deployment failed');
            clearInterval(interval);
            await loadData();
          }
        } catch (error) {
          console.error('Error polling deployment status:', error);
        }
      }, 2000);

      return () => {
        clearInterval(interval);
      };
    }
  }, [activeJob]);

  const loadData = async () => {
    try {
      // Load endpoints
      const endpointData = await getDeploymentEndpoints();
      setEndpoints(endpointData.endpoints || []);

      // Load all jobs
      const jobs = await fetchAllJobs();
      // Ensure jobs is always an array
      const jobsArray = Array.isArray(jobs) ? jobs : [];
      setAllJobs(jobsArray);

      // Fetch live status for each job
      jobsArray.forEach(async (job: DeploymentJob) => {
        try {
          const statusData = await fetchJobStatus(job.job_id);
          setJobStatuses((prev) => ({ ...prev, [job.job_id]: statusData.status }));
        } catch (error) {
          console.error('Error fetching job status:', error);
        }
      });
    } catch (error) {
      showError('Failed to load deployment data');
      console.error('Error loading data:', error);
    }
  };

  const handleDeploy = async (type: string) => {
    setLoading(true);
    try {
      const job = await startDeploymentJob({ type });
      setActiveJob(job);
      setStatus('Started');
      setProgress(0);
      showSuccess(`${type} deployment started`);
      await loadData();
    } catch (error) {
      showError('Failed to start deployment');
      console.error('Error starting deployment:', error);
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
      setComparison((result as any).comparison || JSON.stringify(result, null, 2) || 'No comparison available.');
      showSuccess('Models compared successfully');
    } catch (error) {
      showError('Failed to compare models');
      console.error('Error comparing models:', error);
      setComparison('Failed to compare models');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (jobStatus: string) => {
    switch (jobStatus) {
      case 'completed':
        return <Badge variant="success" size="sm">Completed</Badge>;
      case 'failed':
        return <Badge variant="error" size="sm">Failed</Badge>;
      case 'running':
        return <Badge variant="info" size="sm">Running</Badge>;
      default:
        return <Badge variant="default" size="sm">{jobStatus}</Badge>;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'local':
        return <Server className="w-4 h-4 text-brand-500" />;
      case 'docker':
        return <ContainerIcon className="w-4 h-4 text-success-500" />;
      case 'hf_spaces':
        return <Cloud className="w-4 h-4 text-info-500" />;
      default:
        return <Rocket className="w-4 h-4 text-neutral-500" />;
    }
  };

  // Calculate stats
  const totalJobs = allJobs.length;
  const completedJobs = allJobs.filter(j => jobStatuses[j.job_id] === 'completed' || j.status === 'completed').length;
  const localJobs = allJobs.filter(j => j.type === 'local').length;
  const dockerJobs = allJobs.filter(j => j.type === 'docker').length;
  const hfSpacesJobs = allJobs.filter(j => j.type === 'hf_spaces').length;

  // Table columns
  const columns: Column<DeploymentJob>[] = [
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
      key: 'status',
      header: 'Status',
      render: (job) => getStatusBadge(jobStatuses[job.job_id] || job.status),
    },
    {
      key: 'endpoint',
      header: 'Endpoint',
      render: (job) => (
        job.endpoint ? (
          <a
            href={`http://${job.endpoint}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 flex items-center gap-1"
          >
            <span className="text-sm">{job.endpoint}</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        ) : (
          <span className="text-sm text-neutral-400">-</span>
        )
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
    <Container maxWidth="xl" className="py-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
          Deployment Console
        </h1>
        <p className="text-neutral-600 dark:text-neutral-400 mt-1">
          Deploy models to various platforms and environments
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Total Deployments
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {totalJobs}
                </p>
              </VStack>
              <div className="p-3 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
                <Rocket className="w-6 h-6 text-brand-600 dark:text-brand-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Local
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {localJobs}
                </p>
              </VStack>
              <div className="p-3 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
                <Server className="w-6 h-6 text-brand-600 dark:text-brand-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Docker
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {dockerJobs}
                </p>
              </VStack>
              <div className="p-3 bg-success-50 dark:bg-success-900/20 rounded-lg">
                <ContainerIcon className="w-6 h-6 text-success-600 dark:text-success-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  HF Spaces
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {hfSpacesJobs}
                </p>
              </VStack>
              <div className="p-3 bg-info-50 dark:bg-info-900/20 rounded-lg">
                <Cloud className="w-6 h-6 text-info-600 dark:text-info-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>
      </div>

      {/* Deployment Options */}
      <Card>
        <CardHeader>
          <CardTitle>Deployment Options</CardTitle>
          <CardDescription>Choose a deployment target for your model</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Button
              variant="outline"
              onClick={() => handleDeploy('local')}
              disabled={loading}
              leftIcon={loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Server className="w-4 h-4" />}
              className="h-24 flex-col gap-2"
            >
              <span className="text-lg font-semibold">Deploy Locally</span>
              <span className="text-xs text-neutral-600 dark:text-neutral-400">
                Run model on local server
              </span>
            </Button>

            <Button
              variant="outline"
              onClick={() => handleDeploy('docker')}
              disabled={loading}
              leftIcon={loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ContainerIcon className="w-4 h-4" />}
              className="h-24 flex-col gap-2"
            >
              <span className="text-lg font-semibold">Export Docker</span>
              <span className="text-xs text-neutral-600 dark:text-neutral-400">
                Create Docker container
              </span>
            </Button>

            <Button
              variant="outline"
              onClick={() => handleDeploy('hf_spaces')}
              disabled={loading}
              leftIcon={loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Cloud className="w-4 h-4" />}
              className="h-24 flex-col gap-2"
            >
              <span className="text-lg font-semibold">HF Spaces</span>
              <span className="text-xs text-neutral-600 dark:text-neutral-400">
                Deploy to Hugging Face
              </span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Active Job Status */}
      {activeJob && 'job_id' in activeJob && (
        <Card>
          <CardHeader>
            <CardTitle>Active Deployment</CardTitle>
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
              <div>
                <HStack justify="between" className="mb-2">
                  <span className="text-sm text-neutral-600 dark:text-neutral-400">Progress</span>
                  <span className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                    {progress}%
                  </span>
                </HStack>
                <Progress value={progress} variant="default" />
              </div>
            </VStack>
          </CardContent>
        </Card>
      )}

      {/* Active Endpoints */}
      {endpoints.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Active Endpoints</CardTitle>
            <CardDescription>{endpoints.length} endpoint{endpoints.length !== 1 ? 's' : ''} deployed</CardDescription>
          </CardHeader>
          <CardContent>
            <VStack spacing={3}>
              {endpoints.map((endpoint, idx) => (
                <a
                  key={idx}
                  href={`http://${endpoint}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-3 bg-neutral-50 dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 hover:border-brand-500 dark:hover:border-brand-500 transition-colors group"
                >
                  <HStack spacing={3}>
                    <div className="p-2 bg-success-50 dark:bg-success-900/20 rounded-lg">
                      <CheckCircle2 className="w-5 h-5 text-success-600 dark:text-success-400" />
                    </div>
                    <div>
                      <p className="font-medium text-neutral-900 dark:text-neutral-100">{endpoint}</p>
                      <p className="text-xs text-neutral-600 dark:text-neutral-400">Live endpoint</p>
                    </div>
                  </HStack>
                  <ExternalLink className="w-5 h-5 text-neutral-400 group-hover:text-brand-500 transition-colors" />
                </a>
              ))}
            </VStack>
          </CardContent>
        </Card>
      )}

      {/* Model Comparison */}
      <Card>
        <CardHeader>
          <CardTitle>Model Comparison</CardTitle>
          <CardDescription>Compare deployed models</CardDescription>
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
                leftIcon={<GitCompare className="w-4 h-4" />}
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

      {/* Deployment History */}
      <Card>
        <CardHeader>
          <CardTitle>Deployment History</CardTitle>
          <CardDescription>
            {allJobs.length} deployment{allJobs.length !== 1 ? 's' : ''} total, {completedJobs} completed
          </CardDescription>
        </CardHeader>
        <CardContent>
          {allJobs.length === 0 ? (
            <div className="text-center py-12">
              <Rocket className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
              <p className="text-lg font-medium text-neutral-900 dark:text-neutral-100 mb-2">
                No deployments yet
              </p>
              <p className="text-neutral-600 dark:text-neutral-400">
                Start your first deployment to see it here
              </p>
            </div>
          ) : (
            <Table data={allJobs} columns={columns} />
          )}
        </CardContent>
      </Card>
    </Container>
  );
};

export default DeploymentConsole;
