'use client';

import React from 'react';

export function CardSkeleton() {
  return (
    <div className="bg-surfaceElevated border border-border rounded-2xl p-4 flex flex-col space-y-4 animate-pulse">
      {/* 9:16 Video Preview Skeleton */}
      <div className="w-full aspect-[9/16] bg-surface rounded-xl flex items-center justify-center">
        <div className="w-12 h-12 rounded-full bg-borderSubtle"></div>
      </div>
      {/* Title & Badge */}
      <div className="h-5 bg-border rounded-md w-3/4"></div>
      <div className="h-4 bg-borderSubtle rounded-md w-1/2"></div>
      {/* Score bar */}
      <div className="h-8 bg-surface rounded-lg w-full"></div>
    </div>
  );
}

export function StepperSkeleton() {
  return (
    <div className="w-full max-w-3xl mx-auto bg-surface border border-border rounded-2xl p-6 space-y-6 animate-pulse">
      <div className="h-6 bg-surfaceElevated rounded w-1/3"></div>
      <div className="space-y-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-center space-x-4">
            <div className="w-8 h-8 rounded-full bg-surfaceElevated"></div>
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-surfaceElevated rounded w-1/4"></div>
              <div className="h-3 bg-border rounded w-1/2"></div>
            </div>
          </div>
        ))}
      </div>
      <div className="h-3 bg-surfaceElevated rounded-full w-full"></div>
    </div>
  );
}

export function TableRowSkeleton() {
  return (
    <div className="w-full bg-surfaceElevated/50 border border-border rounded-xl p-4 flex items-center justify-between animate-pulse">
      <div className="space-y-2 w-1/3">
        <div className="h-4 bg-surface rounded w-3/4"></div>
        <div className="h-3 bg-border rounded w-1/2"></div>
      </div>
      <div className="h-8 bg-surface rounded-lg w-24"></div>
    </div>
  );
}
