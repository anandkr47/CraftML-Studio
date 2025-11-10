/**
 * Enhanced Dashboard Page
 * Modern dashboard with real-time stats and quick actions
 */

import React, { useEffect, useState } from 'react';
import {
  Activity,
  Cpu,
  HardDrive,
  TrendingUp,
  Clock,
  CheckCircle,
  AlertCircle,
  PlayCircle,
  Loader2,
} from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Progress } from '../components/ui/Progress';
import { HStack, VStack } from '../components/ui/Stack';
import { apiService } from '../services/api.service';
import { useJobStore } from '../store/jobStore';
import { formatRelativeTime } from '../utils/api.utils';

const EnhancedDashboard: React.FC = () => {
  const [systemMetrics, setSystemMetrics] = useState<any>(null);
  const [jobStats, setJobStats] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { getRecentJobs, getRunningJobs } = useJobStore();

  const recentJobs = getRecentJobs(5);
  const runningJobs = getRunningJobs();

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const [metrics, stats] = await Promise.all([
          apiService.getSystemMetrics(),
          apiService.getJobStats(),
        ]);
        setSystemMetrics(metrics);
        setJobStats(stats);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <Container>
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
        </div>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" className="py-6 space-y-6 h-full">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">Dashboard</h1>
        <p className="text-neutral-600 dark:text-neutral-400 mt-1">
          Monitor your AI infrastructure and manage workflows
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Total Jobs
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {jobStats?.total_jobs || 0}
                </p>
              </VStack>
              <div className="p-3 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
                <Activity className="w-6 h-6 text-brand-600 dark:text-brand-400" />
              </div>
            </HStack>
            <div className="mt-4">
              <HStack spacing={2}>
                <Badge variant="success" size="sm">
                  {jobStats?.by_status?.completed || 0} completed
                </Badge>
                <Badge variant="error" size="sm">
                  {jobStats?.by_status?.failed || 0} failed
                </Badge>
              </HStack>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Running Jobs
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {runningJobs.length}
                </p>
              </VStack>
              <div className="p-3 bg-success-50 dark:bg-success-900/20 rounded-lg">
                <PlayCircle className="w-6 h-6 text-success-600 dark:text-success-400" />
              </div>
            </HStack>
            <div className="mt-4">
              <p className="text-sm text-neutral-500 dark:text-neutral-400">
                Active workflows processing
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  GPU Utilization
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {systemMetrics?.gpus?.[0]
                    ? `${Math.round(systemMetrics.gpus[0].gpu_util)}%`
                    : 'N/A'}
                </p>
              </VStack>
              <div className="p-3 bg-warning-50 dark:bg-warning-900/20 rounded-lg">
                <Cpu className="w-6 h-6 text-warning-600 dark:text-warning-400" />
              </div>
            </HStack>
            <div className="mt-4">
              {systemMetrics?.gpus?.[0] && (
                <Progress
                  value={systemMetrics.gpus[0].gpu_util}
                  variant="warning"
                  size="sm"
                />
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Success Rate
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {jobStats?.success_rate
                    ? `${Math.round(jobStats.success_rate * 100)}%`
                    : '0%'}
                </p>
              </VStack>
              <div className="p-3 bg-info-50 dark:bg-info-900/20 rounded-lg">
                <TrendingUp className="w-6 h-6 text-info-600 dark:text-info-400" />
              </div>
            </HStack>
            <div className="mt-4">
              <p className="text-sm text-neutral-500 dark:text-neutral-400">
                Last 30 days performance
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* System Resources */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>System Resources</CardTitle>
            <CardDescription>Real-time hardware monitoring</CardDescription>
          </CardHeader>
          <CardContent>
            <VStack spacing={4}>
              {/* CPU */}
              <div>
                <HStack justify="between" className="mb-2">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-neutral-500 dark:text-neutral-400" />
                    <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                      CPU
                    </span>
                  </div>
                  <span className="text-sm text-neutral-600 dark:text-neutral-400">
                    {systemMetrics?.cpu?.cpu_percent?.toFixed(1)}%
                  </span>
                </HStack>
                <Progress
                  value={systemMetrics?.cpu?.cpu_percent || 0}
                  variant="default"
                  size="sm"
                />
              </div>

              {/* Memory */}
              <div>
                <HStack justify="between" className="mb-2">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-neutral-500 dark:text-neutral-400" />
                    <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                      Memory
                    </span>
                  </div>
                  <span className="text-sm text-neutral-600 dark:text-neutral-400">
                    {systemMetrics?.memory?.percent?.toFixed(1)}%
                  </span>
                </HStack>
                <Progress
                  value={systemMetrics?.memory?.percent || 0}
                  variant="success"
                  size="sm"
                />
              </div>

              {/* Disk */}
              <div>
                <HStack justify="between" className="mb-2">
                  <div className="flex items-center gap-2">
                    <HardDrive className="w-4 h-4 text-neutral-500 dark:text-neutral-400" />
                    <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                      Disk
                    </span>
                  </div>
                  <span className="text-sm text-neutral-600 dark:text-neutral-400">
                    {systemMetrics?.disk?.percent?.toFixed(1)}%
                  </span>
                </HStack>
                <Progress
                  value={systemMetrics?.disk?.percent || 0}
                  variant="warning"
                  size="sm"
                />
              </div>

              {/* GPU */}
              {systemMetrics?.gpus?.[0] && (
                <div>
                  <HStack justify="between" className="mb-2">
                    <div className="flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-neutral-500 dark:text-neutral-400" />
                      <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                        GPU VRAM
                      </span>
                    </div>
                    <span className="text-sm text-neutral-600 dark:text-neutral-400">
                      {Math.round(systemMetrics.gpus[0].memory_util)}%
                    </span>
                  </HStack>
                  <Progress
                    value={systemMetrics.gpus[0].memory_util}
                    variant="error"
                    size="sm"
                  />
                </div>
              )}
            </VStack>
          </CardContent>
        </Card>

        {/* Recent Jobs */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Jobs</CardTitle>
            <CardDescription>Latest workflow activity</CardDescription>
          </CardHeader>
          <CardContent>
            <VStack spacing={3}>
              {recentJobs.length === 0 ? (
                <p className="text-sm text-neutral-500 dark:text-neutral-400 text-center py-8">
                  No recent jobs
                </p>
              ) : (
                recentJobs.map((job) => (
                  <div
                    key={job.id}
                    className="flex items-start gap-3 p-3 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
                  >
                    {job.status === 'completed' ? (
                      <CheckCircle className="w-5 h-5 text-success-500 flex-shrink-0 mt-0.5" />
                    ) : job.status === 'failed' ? (
                      <AlertCircle className="w-5 h-5 text-error-500 flex-shrink-0 mt-0.5" />
                    ) : (
                      <Clock className="w-5 h-5 text-warning-500 flex-shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">
                        {job.type.charAt(0).toUpperCase() + job.type.slice(1)}
                      </p>
                      <p className="text-xs text-neutral-500 dark:text-neutral-400">
                        {formatRelativeTime(job.startTime)}
                      </p>
                    </div>
                    <Badge
                      variant={
                        job.status === 'completed'
                          ? 'success'
                          : job.status === 'failed'
                          ? 'error'
                          : 'warning'
                      }
                      size="sm"
                    >
                      {job.status}
                    </Badge>
                  </div>
                ))
              )}
            </VStack>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Start a new workflow</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Button variant="outline" fullWidth>
              <PlayCircle className="w-4 h-4" />
              Start Training
            </Button>
            <Button variant="outline" fullWidth>
              <Activity className="w-4 h-4" />
              Run Crawler
            </Button>
            <Button variant="outline" fullWidth>
              <Cpu className="w-4 h-4" />
              Compress Model
            </Button>
            <Button variant="outline" fullWidth>
              <TrendingUp className="w-4 h-4" />
              Deploy Model
            </Button>
          </div>
        </CardContent>
      </Card>
    </Container>
  );
};

export default EnhancedDashboard;

