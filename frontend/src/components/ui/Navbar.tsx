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
        <Link href="/" className="flex items-center space-x-3 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-accent to-purple-400 flex items-center justify-center shadow-accent-glow transition group-hover:scale-105">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div className="flex items-baseline space-x-1.5">
            <span className="text-lg font-bold tracking-tight text-foreground">
              AI CLIPPER
            </span>
            <span className="text-xs font-mono font-semibold px-1.5 py-0.5 rounded bg-accent/15 text-accent border border-accent/30">
              PRO
            </span>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="hidden md:flex items-center space-x-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? 'bg-surfaceElevated text-accent border border-accent/20'
                    : 'text-muted hover:text-foreground hover:bg-surfaceElevated/60'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-accent' : 'text-muted'}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right CTA / Quota */}
        <div className="flex items-center space-x-3">
          <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-surfaceElevated border border-border text-xs font-mono text-muted">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>2 / 5 Clips Free</span>
          </div>

          <Link
            href="/projects/new"
            className="flex items-center space-x-1.5 bg-accent hover:bg-accent-hover text-white text-sm font-semibold px-4 py-2 rounded-lg shadow-accent-glow transition"
          >
            <PlusCircle className="w-4 h-4" />
            <span className="hidden sm:inline">Clip Video</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
