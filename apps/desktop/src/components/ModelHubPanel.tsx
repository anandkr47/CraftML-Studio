/**
 * Model Hub Panel Component
 * Browse and select models with lazy loading and modern UI
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Search,
  Filter,
  Download,
  Trash2,
  Package,
  Loader2,
  CheckCircle2,
  HardDrive,
  Cpu,
  Database,
  Zap,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/Card';
import { Input } from './ui/Input';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { Select } from './ui/Select';
import { HStack, VStack } from './ui/Stack';
import { Skeleton } from './ui/Skeleton';
import {
  fetchModelList,
  fetchCachedModels,
  downloadModel,
  deleteCachedModel,
  compressModel,
} from '../api/modelhub';
import { useNotificationStore } from '../store/notificationStore';

const ICONS: Record<string, string> = {
  'TinyLlama-1.1B': '🦙',
  'LLaMA 3 7B': '🐘',
  'Phi-3-mini': '🐍',
  'Mistral 7B': '⚡',
  'GPT-2': '🤖',
  'BERT': '📚',
  'T5': '🔄',
};

const TYPES = ['All', 'Language', 'Vision', 'Multimodal'];

interface Model {
  name: string;
  type?: string;
  params?: string;
  bits?: string;
  size?: string;
  license?: string;
  dataset?: string;
  tokens?: number;
  description?: string;
}

interface ModelHubPanelProps {
  onSelect?: (model: string) => void;
}

const ITEMS_PER_PAGE = 10;

const ModelHubPanel: React.FC<ModelHubPanelProps> = ({ onSelect }) => {
  const [search, setSearch] = useState('');
  const [type, setType] = useState('All');
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState<string | null>(null);
  const [cached, setCached] = useState<string[]>([]);
  const [cacheLoading, setCacheLoading] = useState(false);
  const [compressing, setCompressing] = useState<string | null>(null);
  const [displayedItems, setDisplayedItems] = useState(ITEMS_PER_PAGE);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const observerTarget = useRef<HTMLDivElement>(null);
  const { success: showSuccess, error: showError } = useNotificationStore();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [modelList, cachedList] = await Promise.all([
        fetchModelList(),
        fetchCachedModels(),
      ]);
      setModels(Array.isArray(modelList) ? modelList : []);
      setCached(Array.isArray(cachedList) ? cachedList : []);
    } catch (error) {
      showError('Failed to load models');
      console.error('Error loading models:', error);
    } finally {
      setLoading(false);
    }
  };

  // Filter models
  const filtered = models.filter(
    (m) =>
      (!search || m.name?.toLowerCase().includes(search.toLowerCase())) &&
      (type === 'All' || !type || m.type?.toLowerCase() === type.toLowerCase())
  );

  // Lazy loaded models
  const visibleModels = filtered.slice(0, displayedItems);
  const hasMore = displayedItems < filtered.length;

  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoadingMore) {
          setIsLoadingMore(true);
          // Simulate loading delay for smooth UX
          setTimeout(() => {
            setDisplayedItems((prev) => Math.min(prev + ITEMS_PER_PAGE, filtered.length));
            setIsLoadingMore(false);
          }, 300);
        }
      },
      { threshold: 0.1 }
    );

    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }

    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, filtered.length]);

  // Reset displayed items when search/filter changes
  useEffect(() => {
    setDisplayedItems(ITEMS_PER_PAGE);
  }, [search, type]);

  const handleSelect = async (model: string) => {
    setSelecting(model);
    try {
      await downloadModel(model);
      if (onSelect) onSelect(model);
      showSuccess(`Model ${model} selected`);
      await loadData(); // Refresh cached models
    } catch (error) {
      showError('Failed to download model');
      console.error('Error downloading model:', error);
    } finally {
      setSelecting(null);
    }
  };

  const handleDeleteCached = async (model: string) => {
    setCacheLoading(true);
    try {
      await deleteCachedModel(model);
      showSuccess(`Model ${model} deleted from cache`);
      await loadData();
    } catch (error) {
      showError('Failed to delete cached model');
      console.error('Error deleting model:', error);
    } finally {
      setCacheLoading(false);
    }
  };

  const handleCompress = async (model: string) => {
    setCompressing(model);
    try {
      await compressModel(model);
      showSuccess(`Model ${model} compressed successfully`);
    } catch (error) {
      showError('Failed to compress model');
      console.error('Error compressing model:', error);
    } finally {
      setCompressing(null);
    }
  };

  const getModelIcon = (modelName: string) => {
    return ICONS[modelName] || '🧠';
  };

  return (
    <VStack spacing={6}>
      {/* Model Browser */}
      <Card>
        <CardHeader>
          <HStack justify="between" align="center">
            <div>
              <CardTitle>Model Hub</CardTitle>
              <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
                Browse and select from {models.length} available models
              </p>
            </div>
            <div className="p-3 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
              <Package className="w-6 h-6 text-brand-600 dark:text-brand-400" />
            </div>
          </HStack>
        </CardHeader>
        <CardContent>
          <VStack spacing={4}>
            {/* Search and Filters */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                placeholder="Search models..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                icon={<Search className="w-4 h-4" />}
              />
              <Select
                value={type}
                onChange={(e) => setType(e.target.value)}
                options={TYPES.map((t) => ({ value: t, label: t }))}
                icon={<Filter className="w-4 h-4" />}
              />
            </div>

            {/* Model List */}
            {loading ? (
              <VStack spacing={3}>
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-24 w-full" />
                ))}
              </VStack>
            ) : (
              <>
                <div className="max-h-[400px] overflow-y-auto pr-2 space-y-3">
                  {visibleModels.map((m) => {
                    const isCached = cached.includes(m.name);
                    const isSelecting = selecting === m.name;

                    return (
                      <Card
                        key={m.name}
                        className="hover:shadow-md transition-shadow border border-neutral-200 dark:border-neutral-700"
                      >
                        <CardContent className="pt-4">
                          <HStack justify="between" align="start">
                            <HStack spacing={3} align="start" className="flex-1">
                              <div className="text-3xl">{getModelIcon(m.name)}</div>
                              <VStack spacing={1} className="flex-1">
                                <HStack spacing={2} align="center">
                                  <h3 className="font-semibold text-neutral-900 dark:text-neutral-100">
                                    {m.name || 'Unknown Model'}
                                  </h3>
                                  {isCached && (
                                    <Badge variant="success" size="sm">
                                      <CheckCircle2 className="w-3 h-3 mr-1" />
                                      Cached
                                    </Badge>
                                  )}
                                </HStack>
                                {m.description && (
                                  <p className="text-sm text-neutral-600 dark:text-neutral-400">
                                    {m.description}
                                  </p>
                                )}
                                <HStack spacing={2} className="flex-wrap">
                                  {m.params && (
                                    <Badge variant="neutral" size="sm">
                                      <Cpu className="w-3 h-3 mr-1" />
                                      {m.params}
                                    </Badge>
                                  )}
                                  {m.size && (
                                    <Badge variant="neutral" size="sm">
                                      <HardDrive className="w-3 h-3 mr-1" />
                                      {m.size}
                                    </Badge>
                                  )}
                                  {m.bits && (
                                    <Badge variant="info" size="sm">
                                      <Zap className="w-3 h-3 mr-1" />
                                      {m.bits}
                                    </Badge>
                                  )}
                                  {m.type && (
                                    <Badge variant="brand" size="sm">
                                      {m.type}
                                    </Badge>
                                  )}
                                </HStack>
                                {(m.dataset || m.tokens) && (
                                  <div className="text-xs text-neutral-500 dark:text-neutral-400 flex items-center gap-2">
                                    {m.dataset && (
                                      <span className="flex items-center gap-1">
                                        <Database className="w-3 h-3" />
                                        {m.dataset}
                                      </span>
                                    )}
                                    {m.tokens && (
                                      <span>• {m.tokens.toLocaleString()} tokens</span>
                                    )}
                                  </div>
                                )}
                              </VStack>
                            </HStack>
                            <Button
                              variant={isCached ? 'outline' : 'primary'}
                              size="sm"
                              onClick={() => handleSelect(m.name)}
                              disabled={isSelecting}
                              icon={
                                isSelecting ? (
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                  <Download className="w-4 h-4" />
                                )
                              }
                            >
                              {isSelecting ? 'Selecting...' : isCached ? 'Use' : 'Select'}
                            </Button>
                          </HStack>
                        </CardContent>
                      </Card>
                    );
                  })}

                  {/* Loading indicator for infinite scroll */}
                  {hasMore && (
                    <div ref={observerTarget} className="py-4 text-center">
                      {isLoadingMore && (
                        <HStack justify="center" spacing={2}>
                          <Loader2 className="w-5 h-5 animate-spin text-brand-500" />
                          <span className="text-sm text-neutral-600 dark:text-neutral-400">
                            Loading more models...
                          </span>
                        </HStack>
                      )}
                    </div>
                  )}
                </div>

                {/* No results */}
                {filtered.length === 0 && (
                  <div className="text-center py-12">
                    <Package className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
                    <p className="text-lg font-medium text-neutral-900 dark:text-neutral-100 mb-2">
                      No models found
                    </p>
                    <p className="text-neutral-600 dark:text-neutral-400">
                      Try adjusting your search or filter
                    </p>
                  </div>
                )}

                {/* Results summary */}
                {filtered.length > 0 && (
                  <p className="text-sm text-neutral-600 dark:text-neutral-400 text-center">
                    Showing {visibleModels.length} of {filtered.length} models
                    {filtered.length !== models.length && ` (filtered from ${models.length})`}
                  </p>
                )}
              </>
            )}
          </VStack>
        </CardContent>
      </Card>

      {/* Cached Models */}
      <Card>
        <CardHeader>
          <HStack justify="between" align="center">
            <div>
              <CardTitle>Cached Models</CardTitle>
              <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
                {cached.length} model{cached.length !== 1 ? 's' : ''} in local cache
              </p>
            </div>
            <div className="p-3 bg-success-50 dark:bg-success-900/20 rounded-lg">
              <HardDrive className="w-6 h-6 text-success-600 dark:text-success-400" />
            </div>
          </HStack>
        </CardHeader>
        <CardContent>
          {cacheLoading ? (
            <VStack spacing={2}>
              {[...Array(2)].map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </VStack>
          ) : cached.length > 0 ? (
            <VStack spacing={2}>
              {cached.map((model) => (
                <Card
                  key={model}
                  className="border border-neutral-200 dark:border-neutral-700"
                >
                  <CardContent className="pt-4">
                    <HStack justify="between" align="center">
                      <HStack spacing={3}>
                        <div className="p-2 bg-success-50 dark:bg-success-900/20 rounded-lg">
                          <CheckCircle2 className="w-5 h-5 text-success-600 dark:text-success-400" />
                        </div>
                        <div>
                          <p className="font-mono text-sm font-medium text-neutral-900 dark:text-neutral-100">
                            {model}
                          </p>
                          <p className="text-xs text-neutral-600 dark:text-neutral-400">
                            Ready to use
                          </p>
                        </div>
                      </HStack>
                      <HStack spacing={2}>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleCompress(model)}
                          disabled={compressing === model}
                          icon={
                            compressing === model ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Zap className="w-4 h-4" />
                            )
                          }
                        >
                          {compressing === model ? 'Compressing...' : 'Compress'}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteCached(model)}
                          disabled={cacheLoading}
                          icon={<Trash2 className="w-4 h-4" />}
                          className="text-danger-600 hover:text-danger-700 hover:bg-danger-50 dark:hover:bg-danger-900/20"
                        >
                          Delete
                        </Button>
                      </HStack>
                    </HStack>
                  </CardContent>
                </Card>
              ))}
            </VStack>
          ) : (
            <div className="text-center py-8">
              <HardDrive className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
              <p className="text-neutral-600 dark:text-neutral-400">No cached models</p>
              <p className="text-sm text-neutral-500 dark:text-neutral-500 mt-1">
                Select a model from above to cache it locally
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </VStack>
  );
};

export default ModelHubPanel;
