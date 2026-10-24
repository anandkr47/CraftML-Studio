/**
 * Model Selector Component
 * Allows users to select a base model from HuggingFace to fine-tune
 */

import React, { useState, useEffect } from 'react';
import { Search } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/Card';
import { Input } from './ui/Input';
// import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { HStack, VStack } from './ui/Stack';
import { HFConnectionPrompt } from './HFConnectionPrompt';
import { useNotificationStore } from '../store/notificationStore';
import { API_BASE } from '../config';

interface ModelOption {
  id: string;
  name: string;
  description: string;
  size?: string;
  type: 'pretrained';
  requiresHF: boolean;
}

interface ModelSelectorProps {
  onModelSelect: (model: ModelOption | null) => void;
  selectedModel: ModelOption | null;
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  onModelSelect,
  selectedModel,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [hfModels, setHfModels] = useState<any[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [hfConnected, setHfConnected] = useState(false);

  const { info: showInfo } = useNotificationStore();

  useEffect(() => {
    checkHFConnection();
  }, []);

  useEffect(() => {
    if (searchQuery.length > 2) {
      searchHFModels();
    }
  }, [searchQuery]);

  const checkHFConnection = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/settings/hf-token/status`);
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
        `${API_BASE}/api/modelhub/search?query=${encodeURIComponent(searchQuery)}&limit=10`
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
          Choose a pretrained base model to fine-tune with LoRA / QLoRA
        </CardDescription>
      </CardHeader>
      <CardContent>
        <VStack spacing={4}>
          {/* Pretrained Models Tab */}
          {(
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
                  leftIcon={<Search className="w-4 h-4" />}
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
                                  <Badge key={tag} variant="default" className="text-xs">
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

        </VStack>
      </CardContent>
    </Card>
  );
};

export default ModelSelector;

