/**
 * Stack Component
 * Flex-based layout component for vertical/horizontal stacking
 */

import React from 'react';

export interface StackProps {
  children: React.ReactNode;
  direction?: 'vertical' | 'horizontal';
  spacing?: 0 | 1 | 2 | 3 | 4 | 5 | 6 | 8 | 10 | 12;
  align?: 'start' | 'center' | 'end' | 'stretch';
  justify?: 'start' | 'center' | 'end' | 'between' | 'around';
  wrap?: boolean;
  className?: string;
}

const spacingMap = {
  0: 'gap-0',
  1: 'gap-1',
  2: 'gap-2',
  3: 'gap-3',
  4: 'gap-4',
  5: 'gap-5',
  6: 'gap-6',
  8: 'gap-8',
  10: 'gap-10',
  12: 'gap-12',
};

const alignMap = {
  start: 'items-start',
  center: 'items-center',
  end: 'items-end',
  stretch: 'items-stretch',
};

const justifyMap = {
  start: 'justify-start',
  center: 'justify-center',
  end: 'justify-end',
  between: 'justify-between',
  around: 'justify-around',
};

export const Stack: React.FC<StackProps> = ({
  children,
  direction = 'vertical',
  spacing = 4,
  align = 'stretch',
  justify = 'start',
  wrap = false,
  className = '',
}) => {
  const directionStyles = direction === 'vertical' ? 'flex-col' : 'flex-row';
  const wrapStyles = wrap ? 'flex-wrap' : '';
  
  const combinedClassName = `
    flex ${directionStyles} ${spacingMap[spacing]} ${alignMap[align]} ${justifyMap[justify]} ${wrapStyles} ${className}
  `.trim();

  return <div className={combinedClassName}>{children}</div>;
};

export const HStack: React.FC<Omit<StackProps, 'direction'>> = (props) => {
  return <Stack direction="horizontal" {...props} />;
};

export const VStack: React.FC<Omit<StackProps, 'direction'>> = (props) => {
  return <Stack direction="vertical" {...props} />;
};

