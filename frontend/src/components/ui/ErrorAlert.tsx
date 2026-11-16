'use client';

import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorAlertProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export default function ErrorAlert({
  title = 'Something went wrong',
  message,
  onRetry,
}: ErrorAlertProps) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className="w-full bg-red-950/40 border border-red-800/60 rounded-2xl p-4 sm:p-5 flex items-start space-x-3.5 text-red-200"
    >
      <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <h4 className="text-sm font-semibold text-red-100 mb-1">{title}</h4>
        <p className="text-xs text-red-300 leading-relaxed font-mono">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-red-900/60 hover:bg-red-800/80 border border-red-700/50 text-xs font-semibold text-white transition flex-shrink-0"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}
