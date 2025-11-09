/**
 * Spinner/Loader Component
 * Loading indicator with different sizes
 */

import React from 'react';
import { Loader2 } from 'lucide-react';

export interface SpinnerProps {
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  label?: string;
}

const sizeMap = {
  xs: 'h-3 w-3',
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
  xl: 'h-12 w-12',
};

export const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className = '', label }) => {
  return (
    <div className="flex items-center justify-center gap-2">
      <Loader2 className={`animate-spin text-brand-500 ${sizeMap[size]} ${className}`} />
      {label && <span className="text-sm text-neutral-600 dark:text-neutral-400">{label}</span>}
    </div>
  );
};

export const FullPageSpinner: React.FC<{ label?: string }> = ({ label = 'Loading...' }) => {
  return (
    <div className="flex h-screen w-full items-center justify-center">
      <Spinner size="xl" label={label} />
    </div>
  );
};

