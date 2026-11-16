'use client';

import React, { useState } from 'react';
import {
  CreditCard,
  CheckCircle2,
  Sparkles,
  Zap,
  Shield,
  HelpCircle,
  X,
} from 'lucide-react';

export default function BillingPage() {
  const [showComingSoonModal, setShowComingSoonModal] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState('');

  const plans = [
    {
      id: 'free',
      name: 'Free Creator',
      price: '$0',
      period: 'forever',
      description: 'Ideal for experimenting with AI short-form curation.',
      isCurrent: true,
      features: [
        '5 viral clips / month',
        'Standard queue processing',
        'Word-level acoustic subtitles',
        '1080x1920 9:16 export',
        'Basic virality scoring',
      ],
      buttonLabel: 'Current Plan',
      buttonDisabled: true,
    },
    {
      id: 'pro',
      name: 'Pro Studio',
      price: '$29',
      period: 'per month',
      description: 'For content creators, YouTubers, and podcast editors.',
      isCurrent: false,
      isPopular: true,
      features: [
        '60 viral clips / month',
        'Priority GPU NVENC queue (6x faster)',
        'Custom Brand Kit & Watermark removal',
        'Full 4-Pillar Virality Rubric breakdown',
        'A/B tested headline generator',
        'Direct MP4 export & transcription trim',
      ],
      buttonLabel: 'Upgrade to Pro',
      comingSoon: true,
    },
    {
      id: 'agency',
      name: 'Agency Scale',
      price: '$99',
      period: 'per month',
      description: 'For media teams and agencies managing multiple channels.',
      isCurrent: false,
      features: [
        '250 viral clips / month',
        'Unlimited Brand Kits',
        'REST API & Webhook access',
        'Multi-speaker podcast split-screen',
        'Autonomous multi-channel publishing',
        'Dedicated 24/7 Slack support',
      ],
      buttonLabel: 'Upgrade to Agency',
      comingSoon: true,
    },
  ];

  const handleUpgradeClick = (planName: string) => {
    setSelectedPlan(planName);
    setShowComingSoonModal(true);
  };

  return (
    <div className="max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
      {/* Header */}
      <div className="text-center mb-12">
        <span className="text-xs font-mono font-semibold uppercase text-accent tracking-widest px-3 py-1 rounded-full bg-accent/10 border border-accent/20">
          PLANS &amp; SUBSCRIPTION
        </span>
        <h1 className="text-3xl sm:text-5xl font-black text-foreground mt-3 mb-3 tracking-tight">
          Transparent, Usage-Based Pricing
        </h1>
        <p className="text-sm sm:text-base text-muted max-w-xl mx-auto">
          Start for free, scale when your audience explodes. All plans include full multi-agent transcription and rendering.
        </p>
      </div>

      {/* Current Quota Usage Card */}
      <div className="bg-surface border border-border rounded-2xl p-6 sm:p-7 shadow-card-glow mb-12 max-w-3xl mx-auto">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-accent/15 text-accent border border-accent/30 font-bold uppercase">
                Active Tier: Free Creator
              </span>
              <span className="text-xs text-muted font-mono">Current Billing Cycle</span>
            </div>
            <h3 className="text-lg font-bold text-foreground mt-1">
              Monthly Clip Allowance
            </h3>
          </div>
          <span className="text-xs font-mono font-bold text-accent">
            2 of 5 Clips Used (40%)
          </span>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-3 bg-surfaceElevated rounded-full overflow-hidden border border-border mb-3">
          <div className="h-full bg-accent rounded-full" style={{ width: '40%' }}></div>
        </div>

        <div className="flex justify-between items-center text-xs font-mono text-muted">
          <span>3 clips remaining</span>
          <span>Resets on the 1st of next month</span>
        </div>
      </div>

      {/* Pricing Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-stretch">
        {plans.map((plan) => (
          <div
            key={plan.id}
            className={`bg-surface rounded-3xl p-7 flex flex-col justify-between border transition relative ${
              plan.isPopular
                ? 'border-accent shadow-accent-glow bg-gradient-to-b from-surfaceElevated to-surface'
                : 'border-border shadow-card-glow'
            }`}
          >
            {plan.isPopular && (
              <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-accent text-white text-[11px] font-bold tracking-wide uppercase shadow-lg">
                Most Popular
              </span>
            )}

            <div>
              {/* Plan Title & Price */}
              <div className="mb-6">
                <h3 className="text-xl font-bold text-foreground mb-1">{plan.name}</h3>
                <p className="text-xs text-muted mb-4">{plan.description}</p>
                <div className="flex items-baseline space-x-1">
                  <span className="text-4xl font-extrabold text-foreground font-mono">
                    {plan.price}
                  </span>
                  <span className="text-xs font-mono text-muted">/{plan.period}</span>
                </div>
              </div>

              {/* Features List */}
              <ul className="space-y-3 mb-8 text-xs">
                {plan.features.map((feat, i) => (
                  <li key={i} className="flex items-start space-x-2.5">
                    <CheckCircle2 className="w-4 h-4 text-accent flex-shrink-0 mt-0.5" />
                    <span className="text-foreground/90">{feat}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Action Button */}
            <div>
              {plan.isCurrent ? (
                <button
                  disabled
                  className="w-full py-3.5 rounded-xl bg-surfaceElevated border border-border text-xs font-bold text-muted cursor-default"
                >
                  {plan.buttonLabel}
                </button>
              ) : (
                <div className="space-y-2">
                  <button
                    onClick={() => handleUpgradeClick(plan.name)}
                    className="w-full py-3.5 rounded-xl bg-accent hover:bg-accent-hover text-white text-xs font-bold shadow-accent-glow transition flex items-center justify-center space-x-1.5"
                  >
                    <span>{plan.buttonLabel}</span>
                    <span className="px-1.5 py-0.5 rounded bg-white/20 text-[10px] font-mono tracking-wider uppercase ml-1">
                      Coming Soon
                    </span>
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* "Coming Soon" Modal */}
      {showComingSoonModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface border border-border rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-2xl relative text-center">
            <button
              onClick={() => setShowComingSoonModal(false)}
              className="absolute top-4 right-4 p-2 rounded-xl text-muted hover:text-foreground hover:bg-surfaceElevated transition"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="w-14 h-14 rounded-2xl bg-accent/15 border border-accent/30 flex items-center justify-center text-accent mx-auto mb-4 shadow-accent-glow">
              <Sparkles className="w-7 h-7" />
            </div>

            <h3 className="text-xl font-extrabold text-foreground mb-2">
              {selectedPlan} Upgrade Coming Soon!
            </h3>
            <p className="text-xs text-muted leading-relaxed mb-6">
              Our automated Stripe &amp; LemonSqueezy payment gateway integration is currently in staging. You are currently grandfathered into our generous Free tier with full multi-agent feature access.
            </p>

            <button
              onClick={() => setShowComingSoonModal(false)}
              className="w-full py-3 rounded-xl bg-accent hover:bg-accent-hover text-white text-xs font-bold shadow-accent-glow transition"
            >
              Got it, continue with Free tier
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
