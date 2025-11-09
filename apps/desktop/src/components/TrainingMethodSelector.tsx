/**
 * Training Method Selector Component
 * Suggests optimal training method based on hardware and allows user override
 */

import React, { useState, useEffect } from 'react';
import {
  Zap,
  TrendingDown,
  Sparkles,
  Info,
  CheckCircle2,
  AlertTriangle,
  Cpu,
  HardDrive,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/Card';
import { Badge } from './ui/Badge';
import { HStack, VStack } from './ui/Stack';

export type TrainingMethod = 'qlora' | 'lora' | 'full';

interface GPUInfo {
  available: boolean;
  name?: string;
  vram_total?: number; // in GB
  backend?: 'cuda' | 'rocm' | 'mps' | 'cpu';
}

interface TrainingMethodInfo {
  id: TrainingMethod;
  name: string;
  description: string;
  icon: React.ReactNode;
  vramRequired: string;
  speed: string;
  accuracy: string;
  pros: string[];
  cons: string[];
  recommended: boolean;
  minVRAM: number; // GB
  color: 'brand' | 'success' | 'warning';
}

interface TrainingMethodSelectorProps {
  selectedModel?: { id: string; name: string; type: 'pretrained' | 'scratch' } | null;
  selectedMethod: TrainingMethod;
  onMethodSelect: (method: TrainingMethod) => void;
  gpuInfo?: GPUInfo;
}

export const TrainingMethodSelector: React.FC<TrainingMethodSelectorProps> = ({
  selectedModel: _selectedModel,
  selectedMethod,
  onMethodSelect,
  gpuInfo,
}) => {
  const [detectedGPU, setDetectedGPU] = useState<GPUInfo>({
    available: false,
  });

  useEffect(() => {
    // Use provided GPU info or fetch from API
    if (gpuInfo) {
      setDetectedGPU(gpuInfo);
    } else {
      fetchGPUInfo();
    }
  }, [gpuInfo]);

  const fetchGPUInfo = async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/api/monitor/metrics');
      if (response.ok) {
        const data = await response.json();
        if (data.gpus && data.gpus.length > 0) {
          const gpu = data.gpus[0];
          setDetectedGPU({
            available: true,
            name: gpu.name,
            vram_total: gpu.memory_total / 1024, // Convert MB to GB
            backend: 'cuda',
          });
        } else {
          setDetectedGPU({ available: false, backend: 'cpu' });
        }
      }
    } catch (error) {
      console.error('Failed to fetch GPU info:', error);
      setDetectedGPU({ available: false, backend: 'cpu' });
    }
  };

  // Training method configurations
  const methods: TrainingMethodInfo[] = [
    {
      id: 'qlora',
      name: 'QLoRA',
      description: '4-bit Quantized LoRA - Maximum efficiency',
      icon: <Zap className="w-5 h-5" />,
      vramRequired: '4-8 GB',
      speed: 'Good',
      accuracy: 'Very Good',
      pros: [
        'Runs on low-end GPUs (6GB or less)',
        '50-75% less memory than LoRA',
        'Good balance of speed and quality',
        'Recommended for most users',
      ],
      cons: [
        'Slightly slower than LoRA',
        'Requires bitsandbytes library',
      ],
      recommended: true,
      minVRAM: 4,
      color: 'success',
    },
    {
      id: 'lora',
      name: 'LoRA',
      description: 'Low-Rank Adaptation - Fast and efficient',
      icon: <TrendingDown className="w-5 h-5" />,
      vramRequired: '8-16 GB',
      speed: 'Very Fast',
      accuracy: 'Very Good',
      pros: [
        'Very efficient training',
        'Faster than QLoRA',
        'Good accuracy',
        'Works on mid-range GPUs',
      ],
      cons: [
        'Needs more VRAM than QLoRA',
        'Slightly less accurate than full fine-tuning',
      ],
      recommended: false,
      minVRAM: 8,
      color: 'brand',
    },
    {
      id: 'full',
      name: 'Full Fine-tuning',
      description: 'Train all parameters - Best accuracy',
      icon: <Sparkles className="w-5 h-5" />,
      vramRequired: '24-48+ GB',
      speed: 'Slow',
      accuracy: 'Excellent',
      pros: [
        'Best possible accuracy',
        'Full model adaptation',
        'No compromises',
      ],
      cons: [
        'Requires massive VRAM (24GB+)',
        'Very slow training',
        'Expensive hardware needed',
        'Large checkpoint files',
      ],
      recommended: false,
      minVRAM: 24,
      color: 'warning',
    },
  ];

  // Determine recommended method based on GPU
  const getRecommendedMethod = (): TrainingMethod => {
    if (!detectedGPU.available || !detectedGPU.vram_total) {
      return 'qlora'; // Default to most efficient
    }

    const vram = detectedGPU.vram_total;
    if (vram >= 24) return 'lora'; // Can afford LoRA for speed
    if (vram >= 8) return 'lora';
    return 'qlora'; // Low VRAM, use QLoRA
  };

  const recommendedMethod = getRecommendedMethod();

  // Check if method is feasible with current hardware
  const isMethodFeasible = (method: TrainingMethodInfo): boolean => {
    if (!detectedGPU.available || !detectedGPU.vram_total) {
      return method.id === 'qlora'; // Only QLoRA works well on CPU
    }
    return detectedGPU.vram_total >= method.minVRAM;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Training Method</CardTitle>
        <CardDescription>
          Choose your training strategy based on hardware and requirements
        </CardDescription>
      </CardHeader>
      <CardContent>
        <VStack spacing={6}>
          {/* Hardware Info */}
          <div className="bg-gradient-to-r from-neutral-50 to-neutral-100 dark:from-neutral-800 dark:to-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-lg p-4">
            <HStack spacing={3} align="start">
              <div className="p-2 bg-brand-100 dark:bg-brand-900/40 rounded-lg">
                {detectedGPU.available ? (
                  <Cpu className="w-5 h-5 text-brand-600 dark:text-brand-400" />
                ) : (
                  <HardDrive className="w-5 h-5 text-neutral-600 dark:text-neutral-400" />
                )}
              </div>
              <div className="flex-1">
                <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-1">
                  Detected Hardware
                </h4>
                {detectedGPU.available && detectedGPU.name ? (
                  <VStack spacing={1}>
                    <p className="text-sm text-neutral-700 dark:text-neutral-300">
                      <strong>GPU:</strong> {detectedGPU.name}
                    </p>
                    <p className="text-sm text-neutral-700 dark:text-neutral-300">
                      <strong>VRAM:</strong> {detectedGPU.vram_total?.toFixed(1)} GB
                    </p>
                    <p className="text-sm text-neutral-700 dark:text-neutral-300">
                      <strong>Backend:</strong>{' '}
                      <Badge variant="success" size="sm">
                        {detectedGPU.backend?.toUpperCase()}
                      </Badge>
                    </p>
                    <p className="text-xs text-success-600 dark:text-success-400 mt-1">
                      ✓ Recommended: <strong>{methods.find(m => m.id === recommendedMethod)?.name}</strong>
                    </p>
                  </VStack>
                ) : (
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">
                    No GPU detected - CPU training (QLoRA recommended)
                  </p>
                )}
              </div>
            </HStack>
          </div>

          {/* Method Selection Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {methods.map((method) => {
              const isSelected = selectedMethod === method.id;
              const isFeasible = isMethodFeasible(method);
              const isRecommended = method.id === recommendedMethod;

              return (
                <button
                  key={method.id}
                  type="button"
                  onClick={() => onMethodSelect(method.id)}
                  disabled={!isFeasible}
                  className={`relative p-5 rounded-lg border-2 transition-all text-left ${
                    isSelected
                      ? `border-${method.color}-500 bg-${method.color}-50 dark:bg-${method.color}-900/20 shadow-md`
                      : isFeasible
                      ? 'border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 hover:shadow-sm'
                      : 'border-neutral-100 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900 opacity-50 cursor-not-allowed'
                  }`}
                >
                  {/* Recommended Badge */}
                  {isRecommended && (
                    <div className="absolute top-2 right-2">
                      <Badge variant="success" size="sm">
                        Recommended
                      </Badge>
                    </div>
                  )}

                  {/* Warning Badge for Infeasible */}
                  {!isFeasible && (
                    <div className="absolute top-2 right-2">
                      <Badge variant="error" size="sm">
                        Insufficient VRAM
                      </Badge>
                    </div>
                  )}

                  <VStack spacing={3}>
                    {/* Icon and Title */}
                    <HStack spacing={3} align="center">
                      <div
                        className={`p-2 rounded-lg ${
                          isSelected
                            ? `bg-${method.color}-100 dark:bg-${method.color}-900/40`
                            : 'bg-neutral-100 dark:bg-neutral-800'
                        }`}
                      >
                        <div
                          className={
                            isSelected
                              ? `text-${method.color}-600 dark:text-${method.color}-400`
                              : 'text-neutral-600 dark:text-neutral-400'
                          }
                        >
                          {method.icon}
                        </div>
                      </div>
                      <div className="flex-1">
                        <h4
                          className={`font-bold ${
                            isSelected
                              ? `text-${method.color}-900 dark:text-${method.color}-100`
                              : 'text-neutral-900 dark:text-neutral-100'
                          }`}
                        >
                          {method.name}
                        </h4>
                      </div>
                      {isSelected && (
                        <CheckCircle2 className={`w-5 h-5 text-${method.color}-600`} />
                      )}
                    </HStack>

                    {/* Description */}
                    <p className="text-xs text-neutral-600 dark:text-neutral-400">
                      {method.description}
                    </p>

                    {/* Stats */}
                    <div className="space-y-1 text-xs">
                      <div className="flex justify-between">
                        <span className="text-neutral-600 dark:text-neutral-400">VRAM:</span>
                        <span className="font-medium text-neutral-900 dark:text-neutral-100">
                          {method.vramRequired}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-600 dark:text-neutral-400">Speed:</span>
                        <span className="font-medium text-neutral-900 dark:text-neutral-100">
                          {method.speed}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-600 dark:text-neutral-400">Accuracy:</span>
                        <span className="font-medium text-neutral-900 dark:text-neutral-100">
                          {method.accuracy}
                        </span>
                      </div>
                    </div>

                    {/* Pros/Cons Preview */}
                    <div className="pt-2 border-t border-neutral-200 dark:border-neutral-700">
                      <div className="flex items-start gap-1">
                        <Info className="w-3 h-3 text-neutral-500 mt-0.5" />
                        <p className="text-xs text-neutral-600 dark:text-neutral-400">
                          {method.pros[0]}
                        </p>
                      </div>
                    </div>
                  </VStack>
                </button>
              );
            })}
          </div>

          {/* Detailed Info for Selected Method */}
          {selectedMethod && (
            <div className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <Info className="w-5 h-5 text-neutral-600 dark:text-neutral-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h5 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-3">
                    About {methods.find((m) => m.id === selectedMethod)?.name}
                  </h5>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Pros */}
                    <div>
                      <p className="text-xs font-medium text-success-700 dark:text-success-400 mb-2">
                        ✓ Advantages
                      </p>
                      <ul className="space-y-1">
                        {methods
                          .find((m) => m.id === selectedMethod)
                          ?.pros.map((pro, idx) => (
                            <li key={idx} className="text-xs text-neutral-700 dark:text-neutral-300 flex gap-2">
                              <span className="text-success-600 dark:text-success-400">•</span>
                              {pro}
                            </li>
                          ))}
                      </ul>
                    </div>

                    {/* Cons */}
                    <div>
                      <p className="text-xs font-medium text-warning-700 dark:text-warning-400 mb-2">
                        ⚠ Limitations
                      </p>
                      <ul className="space-y-1">
                        {methods
                          .find((m) => m.id === selectedMethod)
                          ?.cons.map((con, idx) => (
                            <li key={idx} className="text-xs text-neutral-700 dark:text-neutral-300 flex gap-2">
                              <span className="text-warning-600 dark:text-warning-400">•</span>
                              {con}
                            </li>
                          ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Hardware Warning */}
          {!isMethodFeasible(methods.find((m) => m.id === selectedMethod)!) && (
            <div className="bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-700 rounded-lg p-4">
              <HStack spacing={3} align="start">
                <AlertTriangle className="w-5 h-5 text-warning-600 dark:text-warning-400 flex-shrink-0" />
                <div>
                  <h5 className="text-sm font-semibold text-warning-900 dark:text-warning-100 mb-1">
                    Hardware Limitation
                  </h5>
                  <p className="text-xs text-warning-700 dark:text-warning-300">
                    Your current GPU may not have enough VRAM for this method. Training might fail or be very slow. Consider using QLoRA instead.
                  </p>
                </div>
              </HStack>
            </div>
          )}
        </VStack>
      </CardContent>
    </Card>
  );
};

