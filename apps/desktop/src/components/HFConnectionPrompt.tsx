/**
 * HuggingFace Connection Prompt Component
 * Shows connection status and prompts user to connect if not authenticated
 */

import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, Check, ExternalLink, Settings as SettingsIcon } from 'lucide-react';
import { Card, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { HStack } from './ui/Stack';

interface HFTokenStatus {
  is_authenticated: boolean;
  username?: string;
}

interface HFConnectionPromptProps {
  showIfConnected?: boolean;
  compact?: boolean;
  className?: string;
}

export const HFConnectionPrompt: React.FC<HFConnectionPromptProps> = ({
  showIfConnected = true,
  compact = false,
  className = '',
}) => {
  const [tokenStatus, setTokenStatus] = useState<HFTokenStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkTokenStatus();
  }, []);

  const checkTokenStatus = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://127.0.0.1:5000/api/settings/hf-token/status');
      if (response.ok) {
        const data = await response.json();
        setTokenStatus(data);
      }
    } catch (error) {
      console.error('Error checking HF token status:', error);
      setTokenStatus({ is_authenticated: false });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return null;
  }

  // Don't show anything if connected and showIfConnected is false
  if (tokenStatus?.is_authenticated && !showIfConnected) {
    return null;
  }

  // Compact connected view
  if (compact && tokenStatus?.is_authenticated) {
    return (
      <div className={`inline-flex items-center gap-2 ${className}`}>
        <Badge variant="success" className="text-xs">
          <Check className="w-3 h-3 mr-1" />
          HF Connected
        </Badge>
        {tokenStatus.username && (
          <span className="text-xs text-neutral-600 dark:text-neutral-400">
            as {tokenStatus.username}
          </span>
        )}
      </div>
    );
  }

  // Connected view
  if (tokenStatus?.is_authenticated) {
    return (
      <Card className={`border-success-200 dark:border-success-800 bg-success-50 dark:bg-success-900/20 ${className}`}>
        <CardContent className="pt-4">
          <HStack justify="between" align="center">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-success-100 dark:bg-success-900/40 rounded-lg">
                <Check className="w-5 h-5 text-success-600 dark:text-success-400" />
              </div>
              <div>
                <p className="font-medium text-success-900 dark:text-success-100">
                  HuggingFace Connected
                </p>
                <p className="text-sm text-success-700 dark:text-success-300">
                  Authenticated as <span className="font-semibold">{tokenStatus.username || 'User'}</span>
                </p>
              </div>
            </div>
            <Link to="/settings">
              <Button variant="ghost" size="sm">
                <SettingsIcon className="w-4 h-4" />
              </Button>
            </Link>
          </HStack>
        </CardContent>
      </Card>
    );
  }

  // Not connected - show prompt
  return (
    <Card className={`border-warning-200 dark:border-warning-800 bg-warning-50 dark:bg-warning-900/20 ${className}`}>
      <CardContent className="pt-4">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-warning-100 dark:bg-warning-900/40 rounded-lg flex-shrink-0">
            <AlertCircle className="w-5 h-5 text-warning-600 dark:text-warning-400" />
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-warning-900 dark:text-warning-100 mb-1">
              HuggingFace Not Connected
            </h4>
            <p className="text-sm text-warning-700 dark:text-warning-300 mb-3">
              To download base models from HuggingFace (including gated models like Llama, Mistral), 
              you need to connect your HuggingFace account.
            </p>
            <HStack spacing={2}>
              <Link to="/settings">
                <Button variant="primary" size="sm">
                  <SettingsIcon className="w-4 h-4 mr-2" />
                  Connect HuggingFace
                </Button>
              </Link>
              <a
                href="https://huggingface.co/settings/tokens"
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button variant="outline" size="sm">
                  Get Token
                  <ExternalLink className="w-3 h-3 ml-2" />
                </Button>
              </a>
            </HStack>
            <p className="text-xs text-warning-600 dark:text-warning-400 mt-2">
              💡 Tip: You can also train from scratch without a base model if you have your own dataset.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default HFConnectionPrompt;

