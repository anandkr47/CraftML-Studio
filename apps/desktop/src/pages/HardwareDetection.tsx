/**
 * Hardware Detection Page
 * Auto-detect hardware and show training recommendations
 */

import React, { useEffect, useState } from 'react';
import { Cpu, Zap, HardDrive, Activity, CheckCircle, AlertTriangle } from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Spinner } from '../components/ui/Spinner';
import { VStack, HStack } from '../components/ui/Stack';
import { apiService } from '../services/api.service';
import { useHardwareStore } from '../store/hardwareStore';
import { useNotificationStore } from '../store/notificationStore';

const HardwareDetection: React.FC = () => {
  const { hardwareInfo, recommendation, setHardwareInfo, setRecommendation, setLoading, setError } =
    useHardwareStore();
  const { success, error: showError } = useNotificationStore();
  const [isDetecting, setIsDetecting] = useState(false);

  const detectHardware = async () => {
    setIsDetecting(true);
    setLoading(true);
    setError(null);

    try {
      const [info, rec] = await Promise.all([
        apiService.getHardwareInfo(),
        apiService.getTrainingRecommendation(),
      ]);

      setHardwareInfo(info);
      setRecommendation(rec);
      success('Hardware detected', 'System configuration analyzed successfully');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to detect hardware';
      setError(message);
      showError('Detection failed', message);
    } finally {
      setIsDetecting(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!hardwareInfo) {
      detectHardware();
    }
  }, []);

  const getDeviceTypeBadge = (deviceType: string) => {
    const variants: Record<string, 'success' | 'warning' | 'info' | 'default'> = {
      cuda: 'success',
      rocm: 'warning',
      mps: 'info',
      cpu: 'default',
    };
    return variants[deviceType] || 'default';
  };

  return (
    <Container maxWidth="xl" className="py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
            Hardware Detection
          </h1>
          <p className="text-neutral-600 dark:text-neutral-400 mt-1">
            Auto-detect your system and get training recommendations
          </p>
        </div>
        <Button
          onClick={detectHardware}
          isLoading={isDetecting}
          leftIcon={<Zap className="w-4 h-4" />}
        >
          Re-detect
        </Button>
      </div>

      {isDetecting && !hardwareInfo ? (
        <div className="flex justify-center py-12">
          <Spinner size="lg" label="Detecting hardware..." />
        </div>
      ) : hardwareInfo ? (
        <>
          {/* Hardware Info */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardContent className="pt-6">
                <VStack spacing={3}>
                  <div className="p-3 bg-brand-50 dark:bg-brand-900/20 rounded-lg w-fit">
                    <Cpu className="w-6 h-6 text-brand-600 dark:text-brand-400" />
                  </div>
                  <div>
                    <p className="text-sm text-neutral-600 dark:text-neutral-400">Device Type</p>
                    <p className="text-2xl font-bold text-neutral-900 dark:text-neutral-100 mt-1">
                      {hardwareInfo.device_type.toUpperCase()}
                    </p>
                  </div>
                  <Badge variant={getDeviceTypeBadge(hardwareInfo.device_type)}>
                    {hardwareInfo.backend}
                  </Badge>
                </VStack>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <VStack spacing={3}>
                  <div className="p-3 bg-success-50 dark:bg-success-900/20 rounded-lg w-fit">
                    <Activity className="w-6 h-6 text-success-600 dark:text-success-400" />
                  </div>
                  <div>
                    <p className="text-sm text-neutral-600 dark:text-neutral-400">GPU Count</p>
                    <p className="text-2xl font-bold text-neutral-900 dark:text-neutral-100 mt-1">
                      {hardwareInfo.gpu_count}
                    </p>
                  </div>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">
                    {hardwareInfo.device_name}
                  </p>
                </VStack>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <VStack spacing={3}>
                  <div className="p-3 bg-warning-50 dark:bg-warning-900/20 rounded-lg w-fit">
                    <HardDrive className="w-6 h-6 text-warning-600 dark:text-warning-400" />
                  </div>
                  <div>
                    <p className="text-sm text-neutral-600 dark:text-neutral-400">Total VRAM</p>
                    <p className="text-2xl font-bold text-neutral-900 dark:text-neutral-100 mt-1">
                      {hardwareInfo.total_vram_gb.toFixed(1)} GB
                    </p>
                  </div>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">Available memory</p>
                </VStack>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <VStack spacing={3}>
                  <div className="p-3 bg-info-50 dark:bg-info-900/20 rounded-lg w-fit">
                    <Zap className="w-6 h-6 text-info-600 dark:text-info-400" />
                  </div>
                  <div>
                    <p className="text-sm text-neutral-600 dark:text-neutral-400">
                      Recommended Strategy
                    </p>
                    <p className="text-2xl font-bold text-neutral-900 dark:text-neutral-100 mt-1 uppercase">
                      {hardwareInfo.recommended_strategy}
                    </p>
                  </div>
                  <Badge variant="info">Optimal for your hardware</Badge>
                </VStack>
              </CardContent>
            </Card>
          </div>

          {/* Training Recommendation */}
          {recommendation && (
            <Card>
              <CardHeader>
                <CardTitle>Training Recommendation</CardTitle>
                <CardDescription>
                  Optimized settings for your hardware configuration
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-success-500" />
                      Precision Settings
                    </h3>
                    <div className="space-y-2">
                      <HStack justify="between">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">4-bit</span>
                        <Badge variant={recommendation.use_4bit ? 'success' : 'default'} size="sm">
                          {recommendation.use_4bit ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </HStack>
                      <HStack justify="between">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">8-bit</span>
                        <Badge variant={recommendation.use_8bit ? 'success' : 'default'} size="sm">
                          {recommendation.use_8bit ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </HStack>
                      <HStack justify="between">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">FP16</span>
                        <Badge variant={recommendation.fp16 ? 'success' : 'default'} size="sm">
                          {recommendation.fp16 ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </HStack>
                      <HStack justify="between">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">BF16</span>
                        <Badge variant={recommendation.bf16 ? 'success' : 'default'} size="sm">
                          {recommendation.bf16 ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </HStack>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 flex items-center gap-2">
                      <Zap className="w-4 h-4 text-warning-500" />
                      Optimization Settings
                    </h3>
                    <div className="space-y-2">
                      <HStack justify="between">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">
                          Flash Attention
                        </span>
                        <Badge
                          variant={recommendation.use_flash_attention ? 'success' : 'default'}
                          size="sm"
                        >
                          {recommendation.use_flash_attention ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </HStack>
                      <HStack justify="between">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">
                          Gradient Checkpointing
                        </span>
                        <Badge
                          variant={recommendation.gradient_checkpointing ? 'success' : 'default'}
                          size="sm"
                        >
                          {recommendation.gradient_checkpointing ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </HStack>
                      <HStack justify="between">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">
                          Device Map
                        </span>
                        <Badge variant="info" size="sm">
                          {recommendation.device_map || 'auto'}
                        </Badge>
                      </HStack>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 flex items-center gap-2">
                      <Activity className="w-4 h-4 text-info-500" />
                      Batch Settings
                    </h3>
                    <div className="space-y-2">
                      <HStack justify="between">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">
                          Batch Size
                        </span>
                        <span className="text-sm font-mono font-semibold text-neutral-900 dark:text-neutral-100">
                          {recommendation.per_device_train_batch_size}
                        </span>
                      </HStack>
                      <HStack justify="between">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">
                          Gradient Accumulation
                        </span>
                        <span className="text-sm font-mono font-semibold text-neutral-900 dark:text-neutral-100">
                          {recommendation.gradient_accumulation_steps}
                        </span>
                      </HStack>
                      <HStack justify="between">
                        <span className="text-sm text-neutral-600 dark:text-neutral-400">
                          Strategy
                        </span>
                        <Badge variant="primary" size="sm">
                          {recommendation.strategy.toUpperCase()}
                        </Badge>
                      </HStack>
                    </div>
                  </div>
                </div>

                <div className="mt-6 p-4 bg-info-50 dark:bg-info-900/20 rounded-lg border border-info-200 dark:border-info-800">
                  <HStack align="start" spacing={3}>
                    <AlertTriangle className="w-5 h-5 text-info-600 dark:text-info-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-info-900 dark:text-info-100">
                        Hardware-Optimized Configuration
                      </p>
                      <p className="text-sm text-info-700 dark:text-info-300 mt-1">
                        These settings are automatically optimized for your{' '}
                        <strong>{hardwareInfo.device_name}</strong> with{' '}
                        <strong>{hardwareInfo.total_vram_gb.toFixed(1)} GB VRAM</strong>. Using
                        these settings will provide the best balance between performance and memory
                        usage.
                      </p>
                    </div>
                  </HStack>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}
    </Container>
  );
};

export default HardwareDetection;

