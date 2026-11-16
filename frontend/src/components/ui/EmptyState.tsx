'use client';

import React from 'react';
import Link from 'next/link';
import { LucideIcon, Film, PlusCircle } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
}

export default function EmptyState({
  icon: Icon = Film,
  title,
  description,
  actionHref,
  actionLabel,
}: EmptyStateProps) {
  return (
    <div className="w-full max-w-lg mx-auto bg-surface border border-border border-dashed rounded-3xl p-10 flex flex-col items-center text-center">
      <div className="w-16 h-16 rounded-2xl bg-surfaceElevated border border-border flex items-center justify-center mb-5 text-accent shadow-card-glow">
        <Icon className="w-8 h-8" />
      </div>
      <h3 className="text-xl font-bold text-foreground mb-2">{title}</h3>
      <p className="text-sm text-muted mb-6 max-w-sm">{description}</p>
      {actionHref && actionLabel && (
        <Link
          href={actionHref}
          className="inline-flex items-center space-x-2 bg-accent hover:bg-accent-hover text-white text-sm font-semibold px-5 py-2.5 rounded-xl shadow-accent-glow transition"
        >
          <PlusCircle className="w-4 h-4" />
          <span>{actionLabel}</span>
        </Link>
      )}
    </div>
  );
}
