/**
 * Toast Notification Component
 * Displays toast notifications with animations
 */

import React, { useEffect } from 'react';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { useNotificationStore, Notification } from '../../store/notificationStore';

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const variantStyles = {
  success: 'bg-success-50 border-success-200 dark:bg-success-900/20 dark:border-success-800',
  error: 'bg-error-50 border-error-200 dark:bg-error-900/20 dark:border-error-800',
  warning: 'bg-warning-50 border-warning-200 dark:bg-warning-900/20 dark:border-warning-800',
  info: 'bg-info-50 border-info-200 dark:bg-info-900/20 dark:border-info-800',
};

const iconColorMap = {
  success: 'text-success-600 dark:text-success-400',
  error: 'text-error-600 dark:text-error-400',
  warning: 'text-warning-600 dark:text-warning-400',
  info: 'text-info-600 dark:text-info-400',
};

interface ToastItemProps {
  notification: Notification;
}

const ToastItem: React.FC<ToastItemProps> = ({ notification }) => {
  const { removeNotification } = useNotificationStore();
  const Icon = iconMap[notification.type];

  useEffect(() => {
    if (notification.duration && notification.duration > 0) {
      const timer = setTimeout(() => {
        removeNotification(notification.id);
      }, notification.duration);

      return () => clearTimeout(timer);
    }
  }, [notification.id, notification.duration, removeNotification]);

  return (
    <div
      className={`
        pointer-events-auto w-full max-w-sm overflow-hidden rounded-lg border shadow-lg
        animate-slideIn transition-all duration-200
        ${variantStyles[notification.type]}
      `}
      role="alert"
      aria-live="polite"
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className={`flex-shrink-0 ${iconColorMap[notification.type]}`}>
            <Icon className="h-5 w-5" />
          </div>
          
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              {notification.title}
            </p>
            {notification.message && (
              <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
                {notification.message}
              </p>
            )}
            {notification.action && (
              <button
                onClick={notification.action.onClick}
                className="mt-2 text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
              >
                {notification.action.label}
              </button>
            )}
          </div>
          
          <button
            onClick={() => removeNotification(notification.id)}
            className="flex-shrink-0 rounded-md text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export const ToastContainer: React.FC = () => {
  const { notifications } = useNotificationStore();

  return (
    <div
      aria-live="assertive"
      className="pointer-events-none fixed inset-0 z-[1080] flex flex-col items-end justify-start gap-4 p-6"
    >
      {notifications.map((notification) => (
        <ToastItem key={notification.id} notification={notification} />
      ))}
    </div>
  );
};

