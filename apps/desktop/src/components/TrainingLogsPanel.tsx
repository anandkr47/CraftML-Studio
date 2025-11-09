/**
 * Training Logs Panel Component
 * Professional log viewer with search, filtering, and export
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Terminal,
  Download,
  Search,
  Filter,
  CheckCircle2,
  AlertCircle,
  Info,
  XCircle,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  Trash2,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';
import { HStack, VStack } from './ui/Stack';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
}

interface TrainingLogsPanelProps {
  jobId: string | null;
  logs: string;
  isRunning: boolean;
  onClear?: () => void;
}

export const TrainingLogsPanel: React.FC<TrainingLogsPanelProps> = ({
  jobId,
  logs,
  isRunning,
  onClear,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterLevel, setFilterLevel] = useState<string>('all');
  const [isExpanded, setIsExpanded] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);

  // Parse logs into structured entries
  const parseLogEntry = (line: string): LogEntry | null => {
    if (!line.trim()) return null;

    // Extract timestamp
    const timestampMatch = line.match(/\[([\d-:\s]+)\]/);
    const timestamp = timestampMatch ? timestampMatch[1] : new Date().toLocaleTimeString();

    // Determine level
    let level: LogEntry['level'] = 'info';
    if (line.includes('ERROR') || line.includes('Failed')) level = 'error';
    else if (line.includes('WARNING') || line.includes('WARN')) level = 'warning';
    else if (line.includes('SUCCESS') || line.includes('completed')) level = 'success';

    // Extract message
    const message = line.replace(/\[[\d-:\s]+\]/, '').trim();

    return { timestamp, level, message };
  };

  const logEntries = logs
    .split('\n')
    .map(parseLogEntry)
    .filter((entry): entry is LogEntry => entry !== null);

  // Filter logs
  const filteredLogs = logEntries.filter((entry) => {
    const matchesSearch = entry.message.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLevel = filterLevel === 'all' || entry.level === filterLevel;
    return matchesSearch && matchesLevel;
  });

  // Auto-scroll effect
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // Handle manual scroll - disable auto-scroll if user scrolls up
  const handleScroll = () => {
    if (logsContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = logsContainerRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
      setAutoScroll(isAtBottom);
    }
  };

  const handleExportLogs = () => {
    const blob = new Blob([logs], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `training-logs-${jobId || 'unknown'}-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getLevelIcon = (level: LogEntry['level']) => {
    switch (level) {
      case 'success':
        return <CheckCircle2 className="w-4 h-4 text-success-500" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-danger-500" />;
      case 'warning':
        return <AlertCircle className="w-4 h-4 text-warning-500" />;
      default:
        return <Info className="w-4 h-4 text-info-500" />;
    }
  };

  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'success':
        return 'text-success-600 dark:text-success-400';
      case 'error':
        return 'text-danger-600 dark:text-danger-400';
      case 'warning':
        return 'text-warning-600 dark:text-warning-400';
      default:
        return 'text-neutral-600 dark:text-neutral-400';
    }
  };

  return (
    <Card className={isExpanded ? 'fixed inset-4 z-50' : ''}>
      <CardHeader>
        <HStack justify="between" align="center">
          <HStack spacing={3} align="center">
            <Terminal className="w-5 h-5 text-brand-600 dark:text-brand-400" />
            <div>
              <CardTitle>Training Logs</CardTitle>
              {jobId && (
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                  Job ID: {jobId}
                </p>
              )}
            </div>
            {isRunning && (
              <Badge variant="info" className="animate-pulse">
                Live
              </Badge>
            )}
          </HStack>
          <HStack spacing={2}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAutoScroll(!autoScroll)}
              icon={autoScroll ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            >
              {autoScroll ? 'Pause' : 'Resume'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleExportLogs}
              icon={<Download className="w-4 h-4" />}
              disabled={!logs}
            >
              Export
            </Button>
            {onClear && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onClear}
                icon={<Trash2 className="w-4 h-4" />}
              >
                Clear
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              icon={isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            />
          </HStack>
        </HStack>

        {/* Search and Filter */}
        <HStack spacing={3} className="mt-4">
          <div className="flex-1">
            <Input
              type="text"
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              icon={<Search className="w-4 h-4" />}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setFilterLevel('all')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                filterLevel === 'all'
                  ? 'bg-brand-100 dark:bg-brand-900/30 text-brand-700 dark:text-brand-300'
                  : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilterLevel('error')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                filterLevel === 'error'
                  ? 'bg-danger-100 dark:bg-danger-900/30 text-danger-700 dark:text-danger-300'
                  : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800'
              }`}
            >
              Errors
            </button>
            <button
              onClick={() => setFilterLevel('warning')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                filterLevel === 'warning'
                  ? 'bg-warning-100 dark:bg-warning-900/30 text-warning-700 dark:text-warning-300'
                  : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800'
              }`}
            >
              Warnings
            </button>
          </div>
        </HStack>
      </CardHeader>

      <CardContent>
        <div
          ref={logsContainerRef}
          onScroll={handleScroll}
          className={`bg-neutral-900 dark:bg-neutral-950 rounded-lg p-4 font-mono text-sm overflow-y-auto ${
            isExpanded ? 'h-[calc(100vh-280px)]' : 'h-96'
          }`}
        >
          {filteredLogs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-neutral-500">
              {logs ? 'No logs match your filters' : 'No logs available'}
            </div>
          ) : (
            <VStack spacing={1}>
              {filteredLogs.map((entry, index) => (
                <div
                  key={index}
                  className="flex items-start gap-3 py-1 hover:bg-neutral-800/50 dark:hover:bg-neutral-900/50 rounded px-2 -mx-2"
                >
                  <div className="flex-shrink-0 mt-0.5">{getLevelIcon(entry.level)}</div>
                  <span className="text-neutral-400 text-xs flex-shrink-0 mt-0.5">
                    {entry.timestamp}
                  </span>
                  <span className={`flex-1 ${getLevelColor(entry.level)}`}>
                    {entry.message}
                  </span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </VStack>
          )}
        </div>

        {/* Status bar */}
        <div className="mt-4 flex items-center justify-between text-xs text-neutral-500 dark:text-neutral-400">
          <span>
            {filteredLogs.length} / {logEntries.length} lines
            {searchQuery && ` (filtered by "${searchQuery}")`}
          </span>
          {!autoScroll && (
            <button
              onClick={() => setAutoScroll(true)}
              className="text-brand-600 dark:text-brand-400 hover:underline"
            >
              Scroll to bottom ↓
            </button>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default TrainingLogsPanel;

