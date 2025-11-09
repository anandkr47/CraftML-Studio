/**
 * Container Component
 * Layout container with max-width and padding
 */

import React from 'react';

export interface ContainerProps {
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full';
  padding?: boolean;
  className?: string;
}

const maxWidthStyles = {
  sm: 'max-w-3xl',
  md: 'max-w-5xl',
  lg: 'max-w-7xl',
  xl: 'max-w-[1400px]',
  '2xl': 'max-w-[1600px]',
  full: 'max-w-full',
};

export const Container: React.FC<ContainerProps> = ({
  children,
  maxWidth = 'xl',
  padding = true,
  className = '',
}) => {
  const paddingStyles = padding ? 'px-4 sm:px-6 lg:px-8' : '';
  const combinedClassName = `mx-auto w-full ${maxWidthStyles[maxWidth]} ${paddingStyles} ${className}`;

  return <div className={combinedClassName}>{children}</div>;
};

