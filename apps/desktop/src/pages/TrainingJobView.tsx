/**
 * Training Job View - Real-time training logs and monitoring
 * Opens in new tab when training starts (like Docker logs)
 */

import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Activity,
  CheckCircle2,
  XCircle,
  Loader2,
  Terminal,
  Clock,
} from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Progress } from '../components/ui/Progress';
import { HStack, VStack } from '../components/ui/Stack';
import {
  getTrainingJobStatus,
  getTrainingJobLogs,
} from '../api/training';

interface JobStatus {
  job_id: string;
  status: string;
  started_at?: string;
  progress?: {
    current_epoch?: number;
    total_epochs?: number;
    current_step?: number;
    total_steps?: number;
    loss?: number | null;
  };
  params?: {
    model_name?: string;
    dataset_path?: string;
    training_method?: string;
  };
}

const TrainingJobView: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [loading, setLoading] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);

  // Helper to format model name for display
  const getModelDisplayName = (params: JobStatus['params']) => {
    if (!params) return 'N/A';
    
    return params.model_name?.split('/').pop() || 'N/A';
  };

  useEffect(() => {
    if (!jobId) return;

    // Initial load
    loadJobData();

    // Poll for updates every 2 seconds
    const interval = setInterval(loadJobData, 2000);

    return () => clearInterval(interval);
  }, [jobId]);

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const loadJobData = async () => {
    if (!jobId) return;

    try {
      // Load status
      const status = await getTrainingJobStatus(jobId);
      setJobStatus(status as JobStatus);
      setLoading(false);

      // Load logs
      const logsData = await getTrainingJobLogs(jobId);
      if (logsData.logs) {
        const logLines = Array.isArray(logsData.logs) 
          ? logsData.logs 
          : logsData.logs.split('\n').filter((l: string) => l.trim());
        setLogs(logLines);
      }
    } catch (error) {
      console.error('Error loading job data:', error);
      setLoading(false);
    }
  };

  const handleScroll = () => {
    if (!logsContainerRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = logsContainerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(isAtBottom);
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="success"><CheckCircle2 className="w-3 h-3 mr-1" />Completed</Badge>;
      case 'failed':
        return <Badge variant="error"><XCircle className="w-3 h-3 mr-1" />Failed</Badge>;
      case 'running':
        return <Badge variant="info"><Activity className="w-3 h-3 mr-1 animate-pulse" />Running</Badge>;
      case 'queued':
        return <Badge variant="warning"><Clock className="w-3 h-3 mr-1" />Queued</Badge>;
      default:
        return <Badge variant="default">{status || 'Unknown'}</Badge>;
    }
  };

  const getMethodBadge = (method?: string) => {
    if (!method) return null;
    
    const methodUpper = method.toUpperCase();
    const variants = {
      'QLORA': 'success',
      'LORA': 'info',
      'FULL': 'warning',
    } as const;
    
    return (
      <Badge variant={variants[methodUpper as keyof typeof variants] || 'default'}>
        {methodUpper}
      </Badge>
    );
  };

  if (!jobId) {
    return (
      <Container maxWidth="xl" className="py-6">
        <div className="text-center py-12">
          <XCircle className="w-16 h-16 text-danger-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-neutral-900 dark:text-neutral-100 mb-2">
            No Job ID
          </h2>
          <p className="text-neutral-600 dark:text-neutral-400 mb-6">
            Please provide a valid training job ID
          </p>
          <Button onClick={() => navigate('/train')}>
            Go to Training Console
          </Button>
        </div>
      </Container>
    );
  }

  if (loading) {
    return (
      <Container maxWidth="xl" className="py-6">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-500 mx-auto mb-4"></div>
          <h2 className="text-2xl font-bold text-neutral-900 dark:text-neutral-100 mb-2">
            Loading Job Details
          </h2>
          <p className="text-neutral-600 dark:text-neutral-400">
            Fetching training job information...
          </p>
        </div>
      </Container>
    );
  }

  const progress = jobStatus?.progress;
  const params = jobStatus?.params;
  const progressPercent = progress?.total_epochs
    ? ((progress.current_epoch || 0) / progress.total_epochs) * 100
    : progress?.total_steps
    ? ((progress.current_step || 0) / progress.total_steps) * 100
    : 0;

  return (
    <div className="min-h-screen bg-neutral-900 text-neutral-100">
      {/* Header */}
      <div className="bg-neutral-800 border-b border-neutral-700 sticky top-0 z-10">
        <Container maxWidth="full" className="py-4">
          <HStack justify="between" align="center">
            <HStack spacing={4}>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/train')}
                className="text-neutral-300 hover:text-neutral-100"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Console
              </Button>
              <div className="h-6 w-px bg-neutral-700" />
              <div>
                <HStack spacing={3} align="center">
                  <Terminal className="w-5 h-5 text-brand-400" />
                  <h1 className="text-lg font-semibold">
                    Training Job: {jobId.substring(0, 12)}...
                  </h1>
                  {getStatusBadge(jobStatus?.status)}
                  {params?.training_method && getMethodBadge(params.training_method)}
                </HStack>
              </div>
            </HStack>
            
            <HStack spacing={3}>
              <Button
                variant="ghost"
                size="sm"
                onClick={loadJobData}
                className="text-neutral-300 hover:text-neutral-100"
              >
                <Activity className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </HStack>
          </HStack>
        </Container>
      </div>

      {/* Stats Bar */}
      {jobStatus && (
        <div className="bg-neutral-800/50 border-b border-neutral-700">
          <Container maxWidth="full" className="py-3">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
              <div>
                <div className="text-neutral-500 mb-1">Model</div>
                <div className="font-mono text-neutral-200">
                  {getModelDisplayName(params)}
                </div>
              </div>
              <div>
                <div className="text-neutral-500 mb-1">Dataset</div>
                <div className="font-mono text-neutral-200">
                  {params?.dataset_path?.split('/').pop()?.split('\\').pop() || 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-neutral-500 mb-1">Epoch</div>
                <div className="font-mono text-neutral-200">
                  {progress?.current_epoch || 0} / {progress?.total_epochs || 0}
                </div>
              </div>
              <div>
                <div className="text-neutral-500 mb-1">Step</div>
                <div className="font-mono text-neutral-200">
                  {progress?.current_step || 0} / {progress?.total_steps || 0}
                </div>
              </div>
              <div>
                <div className="text-neutral-500 mb-1">Loss</div>
                <div className="font-mono text-brand-400">
                  {progress?.loss ? progress.loss.toFixed(4) : 'N/A'}
                </div>
              </div>
            </div>
          </Container>
        </div>
      )}

      {/* Progress Bar */}
      {jobStatus?.status === 'running' && progress && (
        <div className="bg-neutral-800/50 border-b border-neutral-700">
          <Container maxWidth="full" className="py-2">
            <div className="flex items-center gap-4">
              <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
              <div className="flex-1">
                <Progress value={progressPercent} className="h-2" />
              </div>
              <span className="text-sm text-neutral-400 font-mono min-w-[60px] text-right">
                {progressPercent.toFixed(1)}%
              </span>
            </div>
          </Container>
        </div>
      )}

      {/* Logs */}
      <Container maxWidth="full" className="py-0 h-[calc(100vh-200px)]">
        <div
          ref={logsContainerRef}
          onScroll={handleScroll}
          className="h-full overflow-y-auto bg-neutral-950 rounded-lg font-mono text-sm p-4"
          style={{ fontFamily: 'Consolas, Monaco, "Courier New", monospace' }}
        >
          {logs.length > 0 ? (
            logs.map((log, index) => (
              <div
                key={index}
                className="py-0.5 hover:bg-neutral-900/50 transition-colors"
              >
                <span className="text-neutral-500 select-none mr-3">
                  {String(index + 1).padStart(4, ' ')}
                </span>
                <span className="text-neutral-300">{log}</span>
              </div>
            ))
          ) : (
            <div className="flex items-center justify-center h-full text-neutral-600">
              <VStack spacing={3} align="center">
                <Terminal className="w-12 h-12 opacity-50" />
                <p>No logs available yet...</p>
                <p className="text-xs">Waiting for training to start...</p>
              </VStack>
            </div>
          )}
          <div ref={logsEndRef} />
        </div>
      </Container>

      {/* Auto-scroll indicator */}
      {!autoScroll && (
        <div className="fixed bottom-6 right-6">
          <Button
            size="sm"
            onClick={() => {
              setAutoScroll(true);
              logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
            }}
            className="shadow-lg"
          >
            <ArrowLeft className="w-4 h-4 mr-2 rotate-[-90deg]" />
            Scroll to Bottom
          </Button>
        </div>
      )}
    </div>
  );
};

export default TrainingJobView;

