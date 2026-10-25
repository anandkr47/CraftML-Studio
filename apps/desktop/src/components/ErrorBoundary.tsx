/**
 * Catches render errors anywhere below it, so one broken component shows a recoverable
 * message instead of a blank window.
 */

import React from 'react';

interface State {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('Unhandled UI error:', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="max-w-lg text-center space-y-4">
          <h2 className="text-xl font-semibold text-neutral-900 dark:text-neutral-100">Something went wrong on this page</h2>
          <p className="text-sm text-neutral-600 dark:text-neutral-400 break-words">{this.state.error.message}</p>
          <div className="flex gap-3 justify-center">
            <button
              className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
              onClick={() => this.setState({ error: null })}
            >
              Try again
            </button>
            <button
              className="rounded-lg border border-neutral-300 dark:border-neutral-700 px-4 py-2 text-sm"
              onClick={() => window.location.assign('/')}
            >
              Go to Chat
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
