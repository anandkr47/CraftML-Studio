/**
 * Settings Page
 * Manage application settings including HuggingFace integration
 */

import React, { useState, useEffect } from 'react';
import {
  Key,
  Check,
  X,
  ExternalLink,
  Shield,
  Info,
  Loader2,
  Trash2,
  Eye,
  EyeOff,
} from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { HStack, VStack } from '../components/ui/Stack';
import { useNotificationStore } from '../store/notificationStore';
import { apiService } from '../services/api.service';

interface HFTokenStatus {
  is_authenticated: boolean;
  username?: string;
  token_preview?: string;
}

const Settings: React.FC = () => {
  const [hfToken, setHfToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [tokenStatus, setTokenStatus] = useState<HFTokenStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);

  const { success: showSuccess, error: showError, info: showInfo } = useNotificationStore();

  useEffect(() => {
    checkTokenStatus();
  }, []);

  const checkTokenStatus = async () => {
    setStatusLoading(true);
    try {
      const response = await fetch('http://127.0.0.1:5000/api/settings/hf-token/status');
      if (response.ok) {
        const data = await response.json();
        setTokenStatus(data);
      }
    } catch (error) {
      console.error('Error checking token status:', error);
    } finally {
      setStatusLoading(false);
    }
  };

  const handleSaveToken = async () => {
    if (!hfToken.trim()) {
      showError('Please enter a HuggingFace token');
      return;
    }

    if (!hfToken.startsWith('hf_')) {
      showError('Invalid token format. HuggingFace tokens start with "hf_"');
      return;
    }

    setLoading(true);
    setVerifying(true);
    try {
      const response = await fetch('http://127.0.0.1:5000/api/settings/hf-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: hfToken }),
      });

      const data = await response.json();

      if (response.ok) {
        showSuccess('HuggingFace token saved successfully!');
        setHfToken('');
        await checkTokenStatus();
      } else {
        showError(data.detail || 'Failed to save token');
      }
    } catch (error) {
      showError('Failed to connect to server');
      console.error('Error saving token:', error);
    } finally {
      setLoading(false);
      setVerifying(false);
    }
  };

  const handleRemoveToken = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://127.0.0.1:5000/api/settings/hf-token', {
        method: 'DELETE',
      });

      if (response.ok) {
        showSuccess('HuggingFace token removed');
        setTokenStatus(null);
        await checkTokenStatus();
      } else {
        showError('Failed to remove token');
      }
    } catch (error) {
      showError('Failed to connect to server');
      console.error('Error removing token:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="xl" className="py-6">
      <VStack spacing={6}>
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
            Settings
          </h1>
          <p className="text-neutral-600 dark:text-neutral-400 mt-1">
            Configure application settings and integrations
          </p>
        </div>

        {/* HuggingFace Integration */}
        <Card>
          <CardHeader>
            <HStack justify="between" align="start">
              <div>
                <CardTitle>🤗 HuggingFace Integration</CardTitle>
                <CardDescription>
                  Connect your HuggingFace account to access gated models and private repositories
                </CardDescription>
              </div>
              {statusLoading ? (
                <Loader2 className="w-5 h-5 animate-spin text-brand-500" />
              ) : tokenStatus?.is_authenticated ? (
                <Badge variant="success">
                  <Check className="w-3 h-3 mr-1" />
                  Connected
                </Badge>
              ) : (
                <Badge variant="neutral">
                  <X className="w-3 h-3 mr-1" />
                  Not Connected
                </Badge>
              )}
            </HStack>
          </CardHeader>
          <CardContent>
            <VStack spacing={4}>
              {/* Info Box */}
              <div className="bg-brand-50 dark:bg-brand-900/20 border border-brand-200 dark:border-brand-800 rounded-lg p-4">
                <HStack spacing={3} align="start">
                  <Info className="w-5 h-5 text-brand-600 dark:text-brand-400 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-brand-900 dark:text-brand-100">
                    <p className="font-medium mb-2">What is a HuggingFace Access Token?</p>
                    <p className="text-brand-700 dark:text-brand-300 mb-2">
                      An access token allows you to download gated models (like Llama 2, Mistral) and access your private repositories.
                    </p>
                    <a
                      href="https://huggingface.co/settings/tokens"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-brand-600 dark:text-brand-400 hover:underline font-medium"
                    >
                      Get your token from HuggingFace
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </HStack>
              </div>

              {/* Current Status */}
              {tokenStatus?.is_authenticated && (
                <Card className="border border-success-200 dark:border-success-800 bg-success-50 dark:bg-success-900/20">
                  <CardContent className="pt-4">
                    <VStack spacing={3}>
                      <HStack justify="between">
                        <div>
                          <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                            Connected Account
                          </p>
                          <p className="text-lg font-semibold text-success-700 dark:text-success-400">
                            {tokenStatus.username || 'Authenticated User'}
                          </p>
                        </div>
                        <div className="p-3 bg-success-100 dark:bg-success-900/40 rounded-lg">
                          <Shield className="w-6 h-6 text-success-600 dark:text-success-400" />
                        </div>
                      </HStack>
                      <HStack justify="between">
                        <div>
                          <p className="text-sm text-neutral-600 dark:text-neutral-400">
                            Token Preview
                          </p>
                          <p className="text-sm font-mono text-neutral-700 dark:text-neutral-300">
                            {tokenStatus.token_preview || 'hf_••••••••••••'}
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleRemoveToken}
                          disabled={loading}
                          icon={<Trash2 className="w-4 h-4" />}
                          className="text-danger-600 hover:text-danger-700 hover:bg-danger-50 dark:hover:bg-danger-900/20"
                        >
                          Remove Token
                        </Button>
                      </HStack>
                    </VStack>
                  </CardContent>
                </Card>
              )}

              {/* Token Input Form */}
              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                  Access Token
                </label>
                <div className="relative">
                  <Input
                    type={showToken ? 'text' : 'password'}
                    value={hfToken}
                    onChange={(e) => setHfToken(e.target.value)}
                    placeholder="hf_..."
                    disabled={loading || verifying}
                    icon={<Key className="w-4 h-4" />}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowToken(!showToken)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300"
                  >
                    {showToken ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                  Your token is stored securely and encrypted on your local machine
                </p>
              </div>

              {/* Action Buttons */}
              <HStack spacing={3}>
                <Button
                  variant="primary"
                  onClick={handleSaveToken}
                  disabled={loading || !hfToken.trim()}
                  icon={
                    verifying ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Check className="w-4 h-4" />
                    )
                  }
                >
                  {verifying ? 'Verifying...' : tokenStatus?.is_authenticated ? 'Update Token' : 'Save Token'}
                </Button>
                {hfToken && (
                  <Button
                    variant="ghost"
                    onClick={() => setHfToken('')}
                    disabled={loading}
                  >
                    Cancel
                  </Button>
                )}
              </HStack>

              {/* Security Note */}
              <div className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg p-4">
                <HStack spacing={3} align="start">
                  <Shield className="w-5 h-5 text-neutral-600 dark:text-neutral-400 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-neutral-700 dark:text-neutral-300">
                    <p className="font-medium mb-1">Security & Privacy</p>
                    <ul className="list-disc list-inside space-y-1 text-neutral-600 dark:text-neutral-400">
                      <li>Your token is encrypted and stored locally</li>
                      <li>Token is never sent to external servers (except HuggingFace)</li>
                      <li>You can revoke access anytime from HuggingFace settings</li>
                      <li>Read-only tokens are recommended for downloading models</li>
                    </ul>
                  </div>
                </HStack>
              </div>
            </VStack>
          </CardContent>
        </Card>

        {/* Token Permissions Info */}
        <Card>
          <CardHeader>
            <CardTitle>Token Permissions</CardTitle>
            <CardDescription>Recommended permissions for your HuggingFace token</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex items-start gap-3 p-3 bg-success-50 dark:bg-success-900/20 rounded-lg border border-success-200 dark:border-success-800">
                <Check className="w-5 h-5 text-success-600 dark:text-success-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-neutral-900 dark:text-neutral-100">Read Access</p>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">
                    Required for downloading public and gated models
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-3 bg-neutral-50 dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700">
                <Info className="w-5 h-5 text-neutral-600 dark:text-neutral-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-neutral-900 dark:text-neutral-100">Write Access</p>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">
                    Optional: Only needed for uploading models
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </VStack>
    </Container>
  );
};

export default Settings;

