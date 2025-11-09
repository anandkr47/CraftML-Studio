/**
 * Model Selector Component
 * Allows users to select a base model from HuggingFace or train from scratch
 */

import React, { useState, useEffect } from 'react';
import { Search, Sparkles, Zap, AlertCircle } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/Card';
import { Input } from './ui/Input';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { HStack, VStack } from './ui/Stack';
import { HFConnectionPrompt } from './HFConnectionPrompt';
import { useNotificationStore } from '../store/notificationStore';

interface ModelOption {
  id: string;
  name: string;
  description: string;
  size?: string;
  type: 'pretrained' | 'scratch';
  requiresHF: boolean;
}

interface ModelSelectorProps {
  onModelSelect: (model: ModelOption | null) => void;
  selectedModel: ModelOption | null;
}

const SCRATCH_MODELS: ModelOption[] = [
  {
    id: 'scratch-transformer',
    name: 'Transformer (From Scratch)',
    description: 'Train a custom transformer model from scratch using your dataset',
    size: 'Custom',
    type: 'scratch',
    requiresHF: false,
  },
  {
    id: 'scratch-bert',
    name: 'BERT-like (From Scratch)',
    description: 'Build a BERT-style encoder model from your data',
    size: 'Custom',
    type: 'scratch',
    requiresHF: false,
  },
  {
    id: 'scratch-gpt',
    name: 'GPT-like (From Scratch)',
    description: 'Create a GPT-style decoder model trained on your corpus',
    size: 'Custom',
    type: 'scratch',
    requiresHF: false,
  },
];

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  onModelSelect,
  selectedModel,
}) => {
  const [activeTab, setActiveTab] = useState<'pretrained' | 'scratch'>('pretrained');
  const [searchQuery, setSearchQuery] = useState('');
  const [hfModels, setHfModels] = useState<any[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [hfConnected, setHfConnected] = useState(false);

  const { info: showInfo } = useNotificationStore();

  useEffect(() => {
    checkHFConnection();
  }, []);

  useEffect(() => {
    if (activeTab === 'pretrained' && searchQuery.length > 2) {
      searchHFModels();
    }
  }, [searchQuery, activeTab]);

  const checkHFConnection = async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/api/settings/hf-token/status');
      if (response.ok) {
        const data = await response.json();
        setHfConnected(data.is_authenticated);
      }
    } catch (error) {
      console.error('Error checking HF connection:', error);
    }
  };

  const searchHFModels = async () => {
    setLoadingModels(true);
    try {
      const response = await fetch(
        `http://127.0.0.1:5000/api/modelhub/search?query=${encodeURIComponent(searchQuery)}&limit=10`
      );
      if (response.ok) {
        const data = await response.json();
        setHfModels(data.models || []);
      }
    } catch (error) {
      console.error('Error searching models:', error);
    } finally {
      setLoadingModels(false);
    }
  };

  const handleModelSelect = (model: ModelOption) => {
    if (model.requiresHF && !hfConnected) {
      showInfo('Please connect your HuggingFace account first to use pretrained models');
      return;
    }
    onModelSelect(model);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model Selection</CardTitle>
        <CardDescription>
          Choose a pretrained base model or train from scratch with your own architecture
        </CardDescription>
      </CardHeader>
      <CardContent>
        <VStack spacing={4}>
          {/* Tab Selection */}
          <div className="flex gap-2 p-1 bg-neutral-100 dark:bg-neutral-800 rounded-lg">
            <button
              onClick={() => setActiveTab('pretrained')}
              className={`flex-1 px-4 py-2 rounded-md font-medium text-sm transition-all ${
                activeTab === 'pretrained'
                  ? 'bg-white dark:bg-neutral-700 text-brand-600 dark:text-brand-400 shadow-sm'
                  : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200'
              }`}
            >
              <Sparkles className="w-4 h-4 inline mr-2" />
              Pretrained Models
            </button>
            <button
              onClick={() => setActiveTab('scratch')}
              className={`flex-1 px-4 py-2 rounded-md font-medium text-sm transition-all ${
                activeTab === 'scratch'
                  ? 'bg-white dark:bg-neutral-700 text-brand-600 dark:text-brand-400 shadow-sm'
                  : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200'
              }`}
            >
              <Zap className="w-4 h-4 inline mr-2" />
              Train from Scratch
            </button>
          </div>

          {/* Pretrained Models Tab */}
          {activeTab === 'pretrained' && (
            <VStack spacing={4}>
              {/* HF Connection Status */}
              <HFConnectionPrompt compact={hfConnected} />

              {/* Search */}
              <div>
                <Input
                  type="text"
                  placeholder="Search HuggingFace models (e.g., 'bert-base', 'gpt2', 'llama')..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  icon={<Search className="w-4 h-4" />}
                  disabled={!hfConnected}
                />
                {!hfConnected && (
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                    Connect HuggingFace to search and download models
                  </p>
                )}
              </div>

              {/* Model List */}
              {loadingModels && (
                <div className="text-center py-8 text-neutral-500 dark:text-neutral-400">
                  Searching models...
                </div>
              )}

              {!loadingModels && searchQuery.length > 2 && hfModels.length === 0 && (
                <div className="text-center py-8 text-neutral-500 dark:text-neutral-400">
                  No models found for "{searchQuery}"
                </div>
              )}

              {!loadingModels && hfModels.length > 0 && (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {hfModels.map((model) => {
                    const modelOption: ModelOption = {
                      id: model.model_id,
                      name: model.name || model.model_id,
                      description: `${model.downloads?.toLocaleString() || 0} downloads · ${model.likes || 0} likes`,
                      type: 'pretrained',
                      requiresHF: true,
                    };
                    const isSelected = selectedModel?.id === modelOption.id;

                    return (
                      <button
                        key={model.model_id}
                        onClick={() => handleModelSelect(modelOption)}
                        className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                          isSelected
                            ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                            : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300 dark:hover:border-brand-700'
                        }`}
                      >
                        <HStack justify="between" align="start">
                          <div className="flex-1">
                            <h4 className="font-semibold text-neutral-900 dark:text-neutral-100">
                              {model.model_id}
                            </h4>
                            <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
                              {modelOption.description}
                            </p>
                            {model.tags && model.tags.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-2">
                                {model.tags.slice(0, 3).map((tag: string) => (
                                  <Badge key={tag} variant="neutral" className="text-xs">
                                    {tag}
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </div>
                          {isSelected && (
                            <Badge variant="success">Selected</Badge>
                          )}
                        </HStack>
                      </button>
                    );
                  })}
                </div>
              )}

              {searchQuery.length <= 2 && (
                <div className="bg-neutral-50 dark:bg-neutral-800 rounded-lg p-6 text-center">
                  <Search className="w-12 h-12 text-neutral-400 dark:text-neutral-600 mx-auto mb-3" />
                  <p className="text-neutral-600 dark:text-neutral-400">
                    Start typing to search for models
                  </p>
                  <p className="text-sm text-neutral-500 dark:text-neutral-500 mt-1">
                    Popular: bert-base-uncased, gpt2, roberta-base, distilbert-base-uncased
                  </p>
                </div>
              )}
            </VStack>
          )}

          {/* Train from Scratch Tab */}
          {activeTab === 'scratch' && (
            <VStack spacing={4}>
              <div className="bg-brand-50 dark:bg-brand-900/20 border border-brand-200 dark:border-brand-800 rounded-lg p-4">
                <HStack spacing={3} align="start">
                  <AlertCircle className="w-5 h-5 text-brand-600 dark:text-brand-400 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-brand-900 dark:text-brand-100">
                    <p className="font-medium mb-1">Training from Scratch</p>
                    <p className="text-brand-700 dark:text-brand-300">
                      Build a model from scratch using your own dataset. This gives you full control 
                      over the architecture but requires more training data and compute time.
                    </p>
                  </div>
                </HStack>
              </div>

              <div className="space-y-2">
                {SCRATCH_MODELS.map((model) => {
                  const isSelected = selectedModel?.id === model.id;

                  return (
                    <button
                      key={model.id}
                      onClick={() => handleModelSelect(model)}
                      className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                        isSelected
                          ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                          : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300 dark:hover:border-brand-700'
                      }`}
                    >
                      <HStack justify="between" align="start">
                        <div className="flex-1">
                          <HStack spacing={2} align="center">
                            <Zap className="w-5 h-5 text-brand-600 dark:text-brand-400" />
                            <h4 className="font-semibold text-neutral-900 dark:text-neutral-100">
                              {model.name}
                            </h4>
                          </HStack>
                          <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-2">
                            {model.description}
                          </p>
                          <div className="flex gap-2 mt-2">
                            <Badge variant="neutral" className="text-xs">
                              {model.size}
                            </Badge>
                            <Badge variant="success" className="text-xs">
                              No HF Required
                            </Badge>
                          </div>
                        </div>
                        {isSelected && (
                          <Badge variant="success">Selected</Badge>
                        )}
                      </HStack>
                    </button>
                  );
                })}
              </div>

              <div className="bg-neutral-50 dark:bg-neutral-800 rounded-lg p-4">
                <p className="text-sm text-neutral-700 dark:text-neutral-300 font-medium mb-2">
                  Requirements for Training from Scratch:
                </p>
                <ul className="text-sm text-neutral-600 dark:text-neutral-400 space-y-1 list-disc list-inside">
                  <li>Large, high-quality dataset (recommended: 100K+ examples)</li>
                  <li>Sufficient compute resources (GPU recommended)</li>
                  <li>Longer training time compared to fine-tuning</li>
                  <li>Custom vocabulary and tokenizer will be created</li>
                </ul>
              </div>
            </VStack>
          )}
        </VStack>
      </CardContent>
    </Card>
  );
};

export default ModelSelector;

