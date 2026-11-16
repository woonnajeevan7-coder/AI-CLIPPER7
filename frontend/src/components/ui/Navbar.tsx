'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Sparkles, Video, Palette, Settings, CreditCard, PlusCircle } from 'lucide-react';

export default function Navbar() {
  const pathname = usePathname();

  const navItems = [
    { label: 'Studio', href: '/', icon: Sparkles },
    { label: 'New Project', href: '/projects/new', icon: PlusCircle },
    { label: 'Brand Kit', href: '/brand-kit', icon: Palette },
    { label: 'Billing', href: '/billing', icon: CreditCard },
    { label: 'Settings', href: '/settings', icon: Settings },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-surface/85 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center space-x-3 group btn-spell">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-accent to-purple-400 flex items-center justify-center shadow-accent-glow transition-all duration-300 ease-out group-hover:scale-110 group-hover:rotate-6">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div className="flex items-baseline space-x-1.5">
            <span className="text-lg font-bold tracking-tight text-foreground group-hover:text-white transition-colors">
              AI CLIPPER
            </span>
            <span className="text-xs font-mono font-semibold px-1.5 py-0.5 rounded bg-accent/20 text-accent-light border border-accent/40 shadow-sm">
              PRO
            </span>
          </div>
        </Link>

        {/* Navigation Links (Desktop) */}
        <nav aria-label="Main Navigation" className="hidden md:flex items-center space-x-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-200 btn-spell ${
                  isActive
                    ? 'bg-surfaceElevated text-foreground border border-accent/40 shadow-sm'
                    : 'text-zinc-300 hover:text-foreground hover:bg-surfaceElevated/70'
                }`}
              >
                <Icon className={`w-4 h-4 transition-transform duration-200 ${isActive ? 'text-accent scale-110' : 'text-zinc-400'}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right CTA / Quota */}
        <div className="flex items-center space-x-3">
          <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-surfaceElevated border border-border text-xs font-mono text-zinc-300 shadow-sm">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
            </span>
            <span className="text-foreground font-medium">2 / 5</span>
            <span className="text-zinc-400">Clips Free</span>
          </div>

          <Link
            href="/projects/new"
            aria-label="Create new clipping project"
            className="flex items-center space-x-1.5 bg-accent hover:bg-accent-hover text-white text-sm font-semibold px-4 py-2 rounded-lg shadow-accent-glow btn-spell focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
          >
            <PlusCircle className="w-4 h-4 transition-transform duration-200 group-hover:rotate-90" />
            <span className="hidden sm:inline">Clip Video</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
