/**
 * Training Job Comparison Component
 * Side-by-side comparison of training jobs with metrics visualization
 */

import React, { useState } from 'react';
import { GitCompare, TrendingUp, TrendingDown, Minus, X } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Select } from './ui/Select';
import { Badge } from './ui/Badge';
import { HStack, VStack } from './ui/Stack';

interface TrainingJob {
  job_id: string;
  base_model?: string;
  status: string;
  started_at: string;
  epochs?: number;
  current_epoch?: number;
  metrics?: {
    final_loss?: number;
    final_accuracy?: number;
    training_time?: number;
    avg_epoch_time?: number;
  };
}

interface TrainingComparisonProps {
  jobs: TrainingJob[];
  onClose?: () => void;
}

export const TrainingComparison: React.FC<TrainingComparisonProps> = ({
  jobs,
  onClose,
}) => {
  const [jobAId, setJobAId] = useState<string>('');
  const [jobBId, setJobBId] = useState<string>('');

  const jobA = jobs.find((j) => j.job_id === jobAId);
  const jobB = jobs.find((j) => j.job_id === jobBId);

  const completedJobs = jobs.filter((j) => j.status === 'completed');

  const compareMetric = (
    valueA: number | undefined,
    valueB: number | undefined,
    lowerIsBetter: boolean = true
  ) => {
    if (valueA === undefined || valueB === undefined) return null;
    
    const diff = valueA - valueB;
    const percentDiff = ((diff / valueB) * 100).toFixed(1);
    
    if (Math.abs(diff) < 0.001) {
      return { icon: <Minus className="w-4 h-4" />, color: 'text-neutral-500', text: '~' };
    }
    
    const isBetter = lowerIsBetter ? diff < 0 : diff > 0;
    
    return {
      icon: isBetter ? (
        <TrendingUp className="w-4 h-4" />
      ) : (
        <TrendingDown className="w-4 h-4" />
      ),
      color: isBetter ? 'text-success-600 dark:text-success-400' : 'text-danger-600 dark:text-danger-400',
      text: `${isBetter ? '+' : ''}${percentDiff}%`,
    };
  };

  const MetricRow: React.FC<{
    label: string;
    valueA: any;
    valueB: any;
    unit?: string;
    lowerIsBetter?: boolean;
  }> = ({ label, valueA, valueB, unit = '', lowerIsBetter = true }) => {
    const comparison = typeof valueA === 'number' && typeof valueB === 'number'
      ? compareMetric(valueA, valueB, lowerIsBetter)
      : null;

    return (
      <div className="grid grid-cols-7 gap-4 py-3 border-b border-neutral-200 dark:border-neutral-700 last:border-0">
        <div className="col-span-2 font-medium text-neutral-700 dark:text-neutral-300">
          {label}
        </div>
        <div className="col-span-2 text-center">
          {valueA !== undefined ? (
            <span className="text-neutral-900 dark:text-neutral-100">
              {typeof valueA === 'number' ? valueA.toFixed(4) : valueA}{unit}
            </span>
          ) : (
            <span className="text-neutral-400">N/A</span>
          )}
        </div>
        <div className="col-span-1 flex items-center justify-center">
          {comparison && (
            <div className={`flex items-center gap-1 ${comparison.color}`}>
              {comparison.icon}
              <span className="text-sm font-medium">{comparison.text}</span>
            </div>
          )}
        </div>
        <div className="col-span-2 text-center">
          {valueB !== undefined ? (
            <span className="text-neutral-900 dark:text-neutral-100">
              {typeof valueB === 'number' ? valueB.toFixed(4) : valueB}{unit}
            </span>
          ) : (
            <span className="text-neutral-400">N/A</span>
          )}
        </div>
      </div>
    );
  };

  if (completedJobs.length < 2) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-12">
            <GitCompare className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
              Not Enough Jobs to Compare
            </h3>
            <p className="text-neutral-600 dark:text-neutral-400">
              Complete at least 2 training jobs to use the comparison feature.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <HStack justify="between" align="center">
          <HStack spacing={3} align="center">
            <GitCompare className="w-5 h-5 text-brand-600 dark:text-brand-400" />
            <CardTitle>Training Job Comparison</CardTitle>
          </HStack>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose} icon={<X className="w-4 h-4" />} />
          )}
        </HStack>
      </CardHeader>

      <CardContent>
        <VStack spacing={6}>
          {/* Job Selection */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                Job A
              </label>
              <Select
                value={jobAId}
                onChange={(e) => setJobAId(e.target.value)}
              >
                <option value="">Select a job...</option>
                {completedJobs.map((job) => (
                  <option key={job.job_id} value={job.job_id}>
                    {job.job_id.substring(0, 12)}... - {job.base_model || 'From Scratch'}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                Job B
              </label>
              <Select
                value={jobBId}
                onChange={(e) => setJobBId(e.target.value)}
              >
                <option value="">Select a job...</option>
                {completedJobs.map((job) => (
                  <option key={job.job_id} value={job.job_id} disabled={job.job_id === jobAId}>
                    {job.job_id.substring(0, 12)}... - {job.base_model || 'From Scratch'}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {/* Comparison Table */}
          {jobA && jobB ? (
            <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden">
              {/* Header */}
              <div className="grid grid-cols-7 gap-4 bg-neutral-50 dark:bg-neutral-800 p-4 font-semibold text-neutral-700 dark:text-neutral-300">
                <div className="col-span-2">Metric</div>
                <div className="col-span-2 text-center">Job A</div>
                <div className="col-span-1 text-center">Diff</div>
                <div className="col-span-2 text-center">Job B</div>
              </div>

              {/* Body */}
              <div className="p-4">
                <VStack spacing={0}>
                  {/* Job Info */}
                  <MetricRow
                    label="Job ID"
                    valueA={jobA.job_id.substring(0, 8) + '...'}
                    valueB={jobB.job_id.substring(0, 8) + '...'}
                  />
                  <MetricRow
                    label="Model"
                    valueA={jobA.base_model || 'From Scratch'}
                    valueB={jobB.base_model || 'From Scratch'}
                  />
                  <MetricRow
                    label="Started"
                    valueA={new Date(jobA.started_at).toLocaleString()}
                    valueB={new Date(jobB.started_at).toLocaleString()}
                  />

                  {/* Training Metrics */}
                  <div className="py-3 mt-4 mb-2">
                    <h4 className="font-semibold text-neutral-900 dark:text-neutral-100">
                      Training Metrics
                    </h4>
                  </div>

                  <MetricRow
                    label="Epochs"
                    valueA={jobA.epochs}
                    valueB={jobB.epochs}
                    lowerIsBetter={false}
                  />
                  <MetricRow
                    label="Final Loss"
                    valueA={jobA.metrics?.final_loss}
                    valueB={jobB.metrics?.final_loss}
                    lowerIsBetter={true}
                  />
                  <MetricRow
                    label="Final Accuracy"
                    valueA={jobA.metrics?.final_accuracy}
                    valueB={jobB.metrics?.final_accuracy}
                    unit="%"
                    lowerIsBetter={false}
                  />
                  <MetricRow
                    label="Training Time"
                    valueA={jobA.metrics?.training_time}
                    valueB={jobB.metrics?.training_time}
                    unit=" min"
                    lowerIsBetter={true}
                  />
                  <MetricRow
                    label="Avg Epoch Time"
                    valueA={jobA.metrics?.avg_epoch_time}
                    valueB={jobB.metrics?.avg_epoch_time}
                    unit=" min"
                    lowerIsBetter={true}
                  />
                </VStack>
              </div>

              {/* Summary */}
              <div className="bg-neutral-50 dark:bg-neutral-800 p-4">
                <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
                  Summary
                </h4>
                <p className="text-sm text-neutral-600 dark:text-neutral-400">
                  {jobA.metrics?.final_loss && jobB.metrics?.final_loss ? (
                    jobA.metrics.final_loss < jobB.metrics.final_loss ? (
                      <>
                        <Badge variant="success" className="mr-2">Job A</Badge>
                        achieved better performance with {((1 - jobA.metrics.final_loss / jobB.metrics.final_loss) * 100).toFixed(1)}% lower loss.
                      </>
                    ) : jobA.metrics.final_loss > jobB.metrics.final_loss ? (
                      <>
                        <Badge variant="success" className="mr-2">Job B</Badge>
                        achieved better performance with {((1 - jobB.metrics.final_loss / jobA.metrics.final_loss) * 100).toFixed(1)}% lower loss.
                      </>
                    ) : (
                      'Both jobs achieved similar performance.'
                    )
                  ) : (
                    'Metrics not available for comparison.'
                  )}
                </p>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-neutral-500 dark:text-neutral-400">
              Select two jobs above to compare their metrics
            </div>
          )}
        </VStack>
      </CardContent>
    </Card>
  );
};

export default TrainingComparison;

