/**
 * Training Configuration Panel Component
 * Professional training configuration with presets and validation
 */

import React, { useState } from 'react';
import { Settings, Zap, Target, Cpu, Info, RotateCcw } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Select } from './ui/Select';
import { Badge } from './ui/Badge';
import { HStack, VStack } from './ui/Stack';

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

interface ModelOption {
  type: 'pretrained' | 'scratch';
  id: string;
  name: string;
}

interface TrainingConfigPanelProps {
  selectedModel: ModelOption | null;
  config: TrainingConfig;
  onChange: (config: TrainingConfig) => void;
  onPresetSelect?: (presetName: string) => void;
}

const PRESETS = {
  quick: {
    name: 'Quick Test',
    description: 'Fast training for testing (low quality)',
    icon: <Zap className="w-4 h-4" />,
    config: {
      epochs: 1,
      learningRate: 0.0001,
      batchSize: 8,
      warmupSteps: 50,
      gradientAccumulation: 1,
      loraRank: 8,
      loraAlpha: 16,
      loraDropout: 0.05,
    },
  },
  balanced: {
    name: 'Balanced',
    description: 'Good quality with reasonable training time',
    icon: <Target className="w-4 h-4" />,
    config: {
      epochs: 3,
      learningRate: 0.0002,
      batchSize: 8,
      warmupSteps: 100,
      gradientAccumulation: 2,
      loraRank: 16,
      loraAlpha: 32,
      loraDropout: 0.1,
    },
  },
  highQuality: {
    name: 'High Quality',
    description: 'Best quality, longer training time',
    icon: <Cpu className="w-4 h-4" />,
    config: {
      epochs: 5,
      learningRate: 0.0001,
      batchSize: 4,
      warmupSteps: 200,
      gradientAccumulation: 4,
      loraRank: 32,
      loraAlpha: 64,
      loraDropout: 0.1,
    },
  },
};

export const TrainingConfigPanel: React.FC<TrainingConfigPanelProps> = ({
  selectedModel,
  config,
  onChange,
  onPresetSelect,
}) => {
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const isFromScratch = selectedModel?.type === 'scratch';

  const handlePresetClick = (presetKey: string) => {
    const preset = PRESETS[presetKey as keyof typeof PRESETS];
    onChange(preset.config);
    setActivePreset(presetKey);
    onPresetSelect?.(preset.name);
  };

  const handleConfigChange = (field: keyof TrainingConfig, value: number) => {
    onChange({ ...config, [field]: value });
    setActivePreset(null); // Clear preset when manually changing
  };

  const handleReset = () => {
    onChange(PRESETS.balanced.config);
    setActivePreset('balanced');
  };

  const estimateTrainingTime = () => {
    // Rough estimation based on config
    const baseTime = config.epochs * 10; // 10 min per epoch baseline
    const batchFactor = 8 / config.batchSize; // Smaller batch = slower
    const accumulationFactor = config.gradientAccumulation;
    
    const totalMinutes = baseTime * batchFactor / accumulationFactor;
    
    if (totalMinutes < 60) {
      return `~${Math.round(totalMinutes)} minutes`;
    } else {
      return `~${(totalMinutes / 60).toFixed(1)} hours`;
    }
  };

  return (
    <Card>
      <CardHeader>
        <HStack justify="between" align="start">
          <div>
            <CardTitle>
              <Settings className="w-5 h-5 inline mr-2" />
              Training Configuration
            </CardTitle>
            <CardDescription>
              {isFromScratch
                ? 'Configure from-scratch training parameters'
                : 'Configure fine-tuning and LoRA parameters'}
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            leftIcon={<RotateCcw className="w-4 h-4" />}
          >
            Reset
          </Button>
        </HStack>
      </CardHeader>

      <CardContent>
        <VStack spacing={6}>
          {/* Presets */}
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-3">
              Quick Presets
            </label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {Object.entries(PRESETS).map(([key, preset]) => (
                <button
                  key={key}
                  onClick={() => handlePresetClick(key)}
                  className={`p-4 rounded-lg border-2 text-left transition-all ${
                    activePreset === key
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                      : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300 dark:hover:border-brand-700'
                  }`}
                >
                  <HStack spacing={2} align="center" className="mb-2">
                    <div className="p-1.5 bg-brand-100 dark:bg-brand-900/40 rounded">
                      {preset.icon}
                    </div>
                    <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                      {preset.name}
                    </span>
                  </HStack>
                  <p className="text-xs text-neutral-600 dark:text-neutral-400">
                    {preset.description}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Basic Parameters */}
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-3">
              Basic Parameters
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  Epochs
                  <span className="text-neutral-500 ml-1">*</span>
                </label>
                <Input
                  type="number"
                  value={config.epochs}
                  onChange={(e) => handleConfigChange('epochs', parseInt(e.target.value))}
                  min={1}
                  max={100}
                />
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                  Number of complete passes through the dataset
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  Learning Rate
                  <span className="text-neutral-500 ml-1">*</span>
                </label>
                <Input
                  type="number"
                  value={config.learningRate}
                  onChange={(e) => handleConfigChange('learningRate', parseFloat(e.target.value))}
                  step={0.0001}
                  min={0.00001}
                  max={0.01}
                />
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                  Step size for weight updates (0.0001 - 0.001)
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  Batch Size
                  <span className="text-neutral-500 ml-1">*</span>
                </label>
                <Input
                  type="number"
                  value={config.batchSize}
                  onChange={(e) => handleConfigChange('batchSize', parseInt(e.target.value))}
                  min={1}
                  max={128}
                />
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                  Samples processed per training step
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  Gradient Accumulation
                </label>
                <Input
                  type="number"
                  value={config.gradientAccumulation}
                  onChange={(e) => handleConfigChange('gradientAccumulation', parseInt(e.target.value))}
                  min={1}
                  max={16}
                />
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                  Effective batch size = batch × accumulation
                </p>
              </div>
            </div>
          </div>

          {/* LoRA Parameters (only for fine-tuning) */}
          {!isFromScratch && (
            <div>
              <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-3">
                LoRA Configuration
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                    LoRA Rank (r)
                  </label>
                  <Input
                    type="number"
                    value={config.loraRank || 16}
                    onChange={(e) => handleConfigChange('loraRank', parseInt(e.target.value))}
                    min={1}
                    max={128}
                  />
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                    Low-rank dimension (8-32 typical)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                    LoRA Alpha
                  </label>
                  <Input
                    type="number"
                    value={config.loraAlpha || 32}
                    onChange={(e) => handleConfigChange('loraAlpha', parseInt(e.target.value))}
                    min={1}
                    max={128}
                  />
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                    Scaling parameter (typically 2× rank)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                    LoRA Dropout
                  </label>
                  <Input
                    type="number"
                    value={config.loraDropout || 0.1}
                    onChange={(e) => handleConfigChange('loraDropout', parseFloat(e.target.value))}
                    step={0.05}
                    min={0}
                    max={0.5}
                  />
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                    Dropout probability (0.0-0.2)
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Advanced Parameters */}
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-3">
              Advanced Settings
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  Warmup Steps
                </label>
                <Input
                  type="number"
                  value={config.warmupSteps}
                  onChange={(e) => handleConfigChange('warmupSteps', parseInt(e.target.value))}
                  min={0}
                  max={1000}
                />
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                  Gradual learning rate increase steps
                </p>
              </div>
            </div>
          </div>

          {/* Info Panel */}
          <div className="bg-brand-50 dark:bg-brand-900/20 border border-brand-200 dark:border-brand-800 rounded-lg p-4">
            <HStack spacing={3} align="start">
              <Info className="w-5 h-5 text-brand-600 dark:text-brand-400 flex-shrink-0 mt-0.5" />
              <VStack spacing={2}>
                <div>
                  <p className="text-sm font-medium text-brand-900 dark:text-brand-100">
                    Estimated Training Time
                  </p>
                  <p className="text-lg font-bold text-brand-700 dark:text-brand-300">
                    {estimateTrainingTime()}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4 text-xs text-brand-700 dark:text-brand-300">
                  <div>
                    <span className="font-medium">Effective Batch:</span>{' '}
                    {config.batchSize * config.gradientAccumulation}
                  </div>
                  <div>
                    <span className="font-medium">Total Steps:</span>{' '}
                    {config.epochs * 100} (est.)
                  </div>
                </div>
                {activePreset && (
                  <Badge variant="info" size="sm" className="mt-2">
                    Using {PRESETS[activePreset as keyof typeof PRESETS].name} preset
                  </Badge>
                )}
              </VStack>
            </HStack>
          </div>
        </VStack>
      </CardContent>
    </Card>
  );
};

export default TrainingConfigPanel;

