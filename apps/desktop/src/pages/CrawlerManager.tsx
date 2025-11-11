/**
 * Crawler Manager Page
 * Web crawler with modern UI matching the design system
 */

import React, { useState, useEffect } from 'react';
import {
  Globe,
  Play,
  Square,
  BarChart3,
  GitCompare,
  Loader2,
  CheckCircle2,
  XCircle,
  Link as LinkIcon,
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
  startCrawlerJob,
  fetchCrawlerJobs,
  getCrawlerJobStatus,
  stopCrawlerJob,
  getCrawlerPreview,
} from '../api/crawler';
import { compareCrawlJobs } from '../api/crawlerCompare';
import { useNotificationStore } from '../store/notificationStore';

interface CrawlJob {
  job_id: string;
  query: string;
  status: string;
  started_at: string;
  depth?: number;
  max_pages?: number;
  pages_crawled?: number;
}

const CrawlerManager: React.FC = () => {
  const [input, setInput] = useState('');
  const [depth, setDepth] = useState(2);
  const [maxPages, setMaxPages] = useState(100);
  const [activeJob, setActiveJob] = useState<CrawlJob | null>(null);
  const [status, setStatus] = useState('');
  const [preview, setPreview] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [jobHistory, setJobHistory] = useState<CrawlJob[]>([]);
  const [jobA, setJobA] = useState('');
  const [jobB, setJobB] = useState('');
  const [comparison, setComparison] = useState('');

  const { success: showSuccess, error: showError, info: showInfo } = useNotificationStore();

  useEffect(() => {
    loadJobs();
  }, []);

  useEffect(() => {
    if (activeJob) {
      // Poll for status updates
      const interval = setInterval(async () => {
        try {
          const statusData = await getCrawlerJobStatus(activeJob.job_id);
          setStatus(statusData.status);
          
          if (statusData.status === 'completed') {
            showSuccess('Crawl job completed successfully');
            clearInterval(interval);
          } else if (statusData.status === 'failed') {
            showError('Crawl job failed');
            clearInterval(interval);
          }

          // Get preview
          const previewData = await getCrawlerPreview(activeJob.job_id);
          const items = Array.isArray(previewData.data) ? previewData.data : [];
          setPreview(items.map((it: any) => (typeof it === 'string' ? it : it.url || JSON.stringify(it))));
        } catch (error) {
          console.error('Error polling job status:', error);
        }
      }, 2000);

      return () => {
        clearInterval(interval);
      };
    }
  }, [activeJob]);

  const loadJobs = async () => {
    try {
      const jobs = await fetchCrawlerJobs();
      // Ensure jobs is always an array
      setJobHistory(Array.isArray(jobs) ? jobs : []);
    } catch (error) {
      showError('Failed to load jobs');
      console.error('Error loading jobs:', error);
      setJobHistory([]);
    }
  };

  const handleStart = async () => {
    if (!input.trim()) {
      showError('Please enter a domain or keywords');
      return;
    }

    setLoading(true);
    try {
      // Convert input to seed_urls array (could be comma-separated URLs)
      const urls = input.split(',').map(url => url.trim()).filter(url => url.length > 0);
      
      const job = await startCrawlerJob({ 
        seed_urls: urls.length > 0 ? urls : [input],
        max_depth: depth,
        max_pages: maxPages 
      });
      setActiveJob({
        job_id: job.job_id,
        query: input,
        status: 'running',
        started_at: new Date().toISOString(),
        depth,
        max_pages: maxPages,
        pages_crawled: 0,
      });
      showSuccess('Crawl job started');
      await loadJobs();
    } catch (error) {
      showError('Failed to start crawl');
      console.error('Error starting crawl:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (!activeJob) return;

    try {
      await stopCrawlerJob(activeJob.job_id);
      setStatus('Stopped');
      showInfo('Crawl job stopped');
      setActiveJob(null);
      await loadJobs();
    } catch (error) {
      showError('Failed to stop crawl');
      console.error('Error stopping crawl:', error);
    }
  };

  const handleCompare = async () => {
    if (!jobA || !jobB) {
      showError('Please select two jobs to compare');
      return;
    }

    setLoading(true);
    try {
      const result = await compareCrawlJobs(jobA, jobB);
      setComparison(result.comparison || 'No comparison available.');
      showSuccess('Jobs compared successfully');
    } catch (error) {
      showError('Failed to compare jobs');
      console.error('Error comparing jobs:', error);
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

  // Calculate stats
  const totalJobs = jobHistory.length;
  const completedJobs = jobHistory.filter(j => j.status === 'completed').length;
  const failedJobs = jobHistory.filter(j => j.status === 'failed').length;
  const successRate = totalJobs > 0 ? Math.round((completedJobs / totalJobs) * 100) : 0;

  // Table columns
  const columns: Column<CrawlJob>[] = [
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
      key: 'query',
      header: 'Query',
      render: (job) => (
        <HStack spacing={2}>
          <Globe className="w-4 h-4 text-brand-500" />
          <span className="font-medium text-neutral-900 dark:text-neutral-100">
            {job.query}
          </span>
        </HStack>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (job) => getStatusBadge(job.status),
    },
    {
      key: 'pages_crawled',
      header: 'Pages',
      render: (job) => (
        <span className="text-sm text-neutral-600 dark:text-neutral-400">
          {job.pages_crawled || 0} / {job.max_pages || 0}
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
    <Container maxWidth="xl" className="py-6 space-y-6 h-full">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
          Web Crawler
        </h1>
        <p className="text-neutral-600 dark:text-neutral-400 mt-1">
          Crawl websites and extract structured data
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
                <Globe className="w-6 h-6 text-brand-600 dark:text-brand-400" />
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

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Success Rate
                </p>
                <p className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {successRate}%
                </p>
              </VStack>
              <div className="p-3 bg-info-50 dark:bg-info-900/20 rounded-lg">
                <BarChart3 className="w-6 h-6 text-info-600 dark:text-info-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>
      </div>

      {/* Crawl Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Start New Crawl</CardTitle>
          <CardDescription>Configure and start a new web crawl job</CardDescription>
        </CardHeader>
        <CardContent>
          <VStack spacing={4}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-1">
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  Seed URLs
                </label>
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="https://example.com (or comma-separated URLs)"
                  leftIcon={<Globe className="w-4 h-4" />}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  Crawl Depth
                </label>
                <Input
                  type="number"
                  value={depth}
                  onChange={(e) => setDepth(Number(e.target.value))}
                  min={1}
                  max={5}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  Max Pages
                </label>
                <Input
                  type="number"
                  value={maxPages}
                  onChange={(e) => setMaxPages(Number(e.target.value))}
                  min={1}
                  max={1000}
                />
              </div>
            </div>
            <HStack spacing={3}>
              <Button
                variant="primary"
                onClick={handleStart}
                disabled={loading || !input.trim()}
                leftIcon={loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              >
                {loading ? 'Starting...' : 'Start Crawl'}
              </Button>
              <Button
                variant="danger"
                onClick={handleStop}
                disabled={!activeJob}
                leftIcon={<Square className="w-4 h-4" />}
              >
                Stop
              </Button>
            </HStack>
          </VStack>
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
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">Status</p>
                  <p className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mt-1">
                    {status || 'Initializing...'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">Query</p>
                  <p className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mt-1">
                    {activeJob.query}
                  </p>
                </div>
              </HStack>
              {activeJob.pages_crawled !== undefined && (
                <div>
                  <HStack justify="between" className="mb-2">
                    <span className="text-sm text-neutral-600 dark:text-neutral-400">Progress</span>
                    <span className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                      {activeJob.pages_crawled} / {activeJob.max_pages}
                    </span>
                  </HStack>
                  <Progress 
                    value={(activeJob.pages_crawled / (activeJob.max_pages || 1)) * 100} 
                    variant="default"
                  />
                </div>
              )}
            </VStack>
          </CardContent>
        </Card>
      )}

      {/* Job Comparison */}
      <Card>
        <CardHeader>
          <CardTitle>Compare Jobs</CardTitle>
          <CardDescription>Compare results from two different crawl jobs</CardDescription>
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

      {/* Preview */}
      {preview.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Data Preview</CardTitle>
            <CardDescription>{preview.length} items crawled</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {preview.slice(0, 10).map((item, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm text-neutral-700 dark:text-neutral-300">
                  <LinkIcon className="w-4 h-4 mt-0.5 text-brand-500 flex-shrink-0" />
                  <span className="break-all">{item}</span>
                </li>
              ))}
              {preview.length > 10 && (
                <li className="text-sm text-neutral-500 dark:text-neutral-400 italic">
                  ... and {preview.length - 10} more items
                </li>
              )}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Job History */}
      <Card>
        <CardHeader>
          <CardTitle>Job History</CardTitle>
          <CardDescription>
            {jobHistory.length} job{jobHistory.length !== 1 ? 's' : ''} total
          </CardDescription>
        </CardHeader>
        <CardContent>
          {jobHistory.length === 0 ? (
            <div className="text-center py-12">
              <Globe className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
              <p className="text-lg font-medium text-neutral-900 dark:text-neutral-100 mb-2">
                No crawl jobs yet
              </p>
              <p className="text-neutral-600 dark:text-neutral-400">
                Start your first crawl job to see it here
              </p>
            </div>
          ) : (
            <Table data={jobHistory} columns={columns} />
          )}
        </CardContent>
      </Card>
    </Container>
  );
};

export default CrawlerManager;
