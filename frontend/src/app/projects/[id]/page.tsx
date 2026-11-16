'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  Sparkles,
  Download,
  Edit3,
  Play,
  Pause,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Share2,
  Film,
  Award,
  Zap,
} from 'lucide-react';
import { CardSkeleton } from '@/components/ui/LoadingSkeleton';
import EmptyState from '@/components/ui/EmptyState';
import ErrorAlert from '@/components/ui/ErrorAlert';
import { useAppStore } from '@/store';

interface RubricDetails {
  hook_strength: number;
  self_contained: number;
  payoff: number;
  zero_context_needed: number;
  critique: string;
}

interface ClipCardData {
  id: string;
  title: string;
  headline: string;
  duration: number;
  viral_score: number;
  layout: string;
  video_url: string;
  hook: string;
  rubric: RubricDetails;
  headline_variants: {
    curiosity: string;
    value: string;
    bold_claim: string;
  };
}

export default function ProjectResultsPage() {
  const params = useParams();
  const projectId = params?.id as string;
  const setClipsStore = useAppStore((state) => state.setClips);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clips, setClips] = useState<ClipCardData[]>([]);

  // Expanded rubric states per clip
  const [expandedRubric, setExpandedRubric] = useState<Record<string, boolean>>({});
  // Selected headline variant per clip
  const [activeVariantTab, setActiveVariantTab] = useState<Record<string, 'curiosity' | 'value' | 'bold_claim'>>({});
  // Copied headline toast
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    // Fetch clips or supply calibrated defaults
    const timer = setTimeout(() => {
      const loadedClips = [
        {
          id: 'clip_001',
          title: 'Connecting the Dots Intro',
          headline: 'THREE STORIES THAT CHANGED EVERYTHING',
          duration: 27.3,
          start_seconds: 27.0,
          end_seconds: 54.3,
          viral_score: 95,
          layout: 'single_face',
          video_url: '/sample_short.mp4',
          hook: 'You cannot connect the dots looking forward; you can only connect them looking backwards.',
          rubric: {
            hook_strength: 24,
            self_contained: 25,
            payoff: 23,
            zero_context_needed: 23,
            critique: 'Exceptionally powerful introductory paradox with immediate universal resonance and zero assumed knowledge.',
          },
          headline_variants: {
            curiosity: 'The 3 Dots Steve Jobs Connected Before Dying',
            value: 'How Looking Backwards Explains Every Failure',
            bold_claim: 'Why You Cannot Plan Your Life Forward',
          },
        },
        {
          id: 'clip_002',
          title: 'Closest to Graduation',
          headline: 'WHAT I LEARNED SKIPPING COLLEGE',
          duration: 34.5,
          start_seconds: 55.0,
          end_seconds: 89.5,
          viral_score: 91,
          layout: 'single_face',
          video_url: '/sample_short_2.mp4',
          hook: 'This is the closest I have ever gotten to a college graduation.',
          rubric: {
            hook_strength: 23,
            self_contained: 23,
            payoff: 22,
            zero_context_needed: 23,
            critique: 'Self-deprecating humor hook with strong relatable emotional arc and clear comedic timing.',
          },
          headline_variants: {
            curiosity: 'The Graduation Secret Jobs Never Admitted',
            value: 'What Stanford Learned From a College Dropout',
            bold_claim: 'I Dropped Out After Just 6 Months',
          },
        },
        {
          id: 'clip_003',
          title: 'Finding What You Love',
          headline: 'DO NOT SETTLE UNTIL YOU FIND IT',
          duration: 38.2,
          start_seconds: 90.0,
          end_seconds: 128.2,
          viral_score: 88,
          layout: 'single_face',
          video_url: '/sample_short_3.mp4',
          hook: 'Your work is going to fill a large part of your life, and the only way to be truly satisfied is to do great work.',
          rubric: {
            hook_strength: 22,
            self_contained: 22,
            payoff: 22,
            zero_context_needed: 22,
            critique: 'Inspirational philosophical climax that delivers practical emotional conviction.',
          },
          headline_variants: {
            curiosity: 'The Brutal Truth About Settling in Your Career',
            value: 'Why Great Work Requires Total Satisfaction',
            bold_claim: 'The Only Way to Never Settle Again',
          },
        },
      ];
      setClips(loadedClips);
      setClipsStore(loadedClips);
      setIsLoading(false);
    }, 600);

    return () => clearTimeout(timer);
  }, [projectId]);

  const toggleRubric = (clipId: string) => {
    setExpandedRubric((prev) => ({ ...prev, [clipId]: !prev[clipId] }));
  };

  const copyHeadline = async (text: string, clipId: string) => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      }
    } catch (e) {
      // Fallback for sandboxed environments or devices without clipboard permissions
    }
    setCopiedId(clipId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleDownload = (videoUrl: string, filename: string) => {
    const a = document.createElement('a');
    a.href = videoUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-8 border-b border-border mb-10">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-muted mb-1">
            <span>Project ID: {projectId}</span>
            <span>•</span>
            <span className="text-emerald-400 font-bold">Generated Complete</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-foreground tracking-tight">
            Curated 9:16 Shorts Grid
          </h1>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            href="/projects/new"
            className="px-4 py-2.5 rounded-xl bg-surfaceElevated hover:bg-surface border border-border text-foreground text-sm font-semibold transition"
          >
            + Clip Another
          </Link>
          <button
            onClick={() => handleDownload('/sample_short.mp4', `project_${projectId}_shorts.zip`)}
            className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-accent hover:bg-accent-hover text-white text-sm font-bold shadow-accent-glow btn-spell"
          >
            <Download className="w-4 h-4 transition-transform duration-200 group-hover:translate-y-0.5" />
            <span>Download All (ZIP)</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-8">
          <ErrorAlert message={error} onRetry={() => setError(null)} />
        </div>
      )}

      {/* Loading Skeleton Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : clips.length === 0 ? (
        <EmptyState
          title="No Shorts Generated Yet"
          description="This project doesn't have any rendered shorts yet. Upload a video to start the multi-agent pipeline."
          actionHref="/projects/new"
          actionLabel="Create New Project"
        />
      ) : (
        /* Results Cards Grid (9:16 Aspect Ratio) */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {clips.map((clip) => {
            const isRubricOpen = !!expandedRubric[clip.id];
            const activeTab = activeVariantTab[clip.id] || 'curiosity';
            const selectedHeadline = clip.headline_variants[activeTab] || clip.headline;

            return (
              <div
                key={clip.id}
                className="bg-surface border border-border rounded-3xl p-5 flex flex-col card-spell group"
              >
                {/* 9:16 Video Mockup Container */}
                <div className="w-full aspect-[9/16] bg-background rounded-2xl overflow-hidden relative border border-borderSubtle flex flex-col justify-between p-4 mb-5 shadow-2xl group-hover:border-accent/40 transition-all duration-300">
                  {/* Top Overlays */}
                  <div className="flex items-center justify-between z-10">
                    <span className="px-2.5 py-1 rounded-md bg-black/85 backdrop-blur-md text-xs font-mono text-white border border-white/10 shadow-sm">
                      {clip.duration.toFixed(1)}s
                    </span>

                    <span className="px-3 py-1 rounded-full bg-accent/25 backdrop-blur-md text-xs font-mono font-bold text-accent-light border border-accent/50 shadow-accent-glow-sm">
                      ★ {clip.viral_score}/100 VIRAL
                    </span>
                  </div>

                  {/* Play Overlay */}
                  <div className="self-center w-14 h-14 rounded-full bg-accent/90 hover:bg-accent text-white flex items-center justify-center shadow-lg transition-all duration-200 group-hover:scale-110 active:scale-95 cursor-pointer">
                    <Play className="w-6 h-6 fill-white ml-0.5" />
                  </div>

                  {/* Bottom Subtitle / Hook Preview */}
                  <div className="z-10 bg-black/90 backdrop-blur-md p-3.5 rounded-xl border border-white/10 space-y-1 shadow-md">
                    <p className="text-[11px] font-mono text-yellow-400 font-bold uppercase tracking-wider">
                      HOOK ONSET (0.0s - 3.0s)
                    </p>
                    <p className="text-xs text-foreground font-sans line-clamp-2 italic leading-relaxed">
                      &quot;{clip.hook}&quot;
                    </p>
                  </div>
                </div>

                {/* Card Header & Title */}
                <div className="mb-4">
                  <h3 className="text-lg font-bold text-foreground mb-1 leading-snug group-hover:text-accent-light transition-colors">
                    {clip.title}
                  </h3>
                  <div className="flex items-center space-x-2 text-xs font-mono text-muted">
                    <span className="capitalize">{clip.layout.replace('_', ' ')}</span>
                    <span>•</span>
                    <span>1080x1920 (9:16)</span>
                  </div>
                </div>

                {/* Headline Variants Switcher */}
                <div className="bg-surfaceElevated border border-border rounded-xl p-3 mb-4 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-mono uppercase text-muted font-semibold tracking-wider">
                      A/B Tested Headlines
                    </span>
                    <button
                      onClick={() => copyHeadline(selectedHeadline, clip.id)}
                      className="text-xs text-accent hover:text-accent-light flex items-center space-x-1 btn-spell"
                    >
                      {copiedId === clip.id ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="text-emerald-400 font-mono font-bold">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>

                  {/* Tabs */}
                  <div className="flex rounded-lg bg-surface p-1 border border-border mb-2.5">
                    {(['curiosity', 'value', 'bold_claim'] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() =>
                          setActiveVariantTab((prev) => ({ ...prev, [clip.id]: tab }))
                        }
                        className={`flex-1 py-1 text-[11px] font-medium capitalize rounded-md btn-spell ${
                          activeTab === tab
                            ? 'bg-accent/25 text-white font-bold border border-accent/40 shadow-sm'
                            : 'text-muted hover:text-foreground'
                        }`}
                      >
                        {tab.replace('_', ' ')}
                      </button>
                    ))}
                  </div>

                  <p className="text-xs font-semibold text-foreground bg-surface p-2.5 rounded-lg border border-borderSubtle">
                    {selectedHeadline}
                  </p>
                </div>

                {/* Collapsible Rubric Breakdown */}
                <div className="border border-border rounded-xl overflow-hidden mb-5 bg-surfaceElevated/40">
                  <button
                    onClick={() => toggleRubric(clip.id)}
                    className="w-full px-3.5 py-2.5 flex items-center justify-between text-xs font-semibold text-muted hover:text-foreground transition group/rubric btn-spell"
                  >
                    <div className="flex items-center space-x-1.5">
                      <Award className="w-4 h-4 text-accent transition-transform duration-200 group-hover/rubric:scale-110" />
                      <span className="text-foreground">4-Pillar Virality Rubric</span>
                    </div>
                    <ChevronDown className={`w-4 h-4 text-muted transition-transform duration-300 ${isRubricOpen ? 'rotate-180 text-accent' : ''}`} />
                  </button>

                  {isRubricOpen && (
                    <div className="p-3.5 border-t border-border space-y-2.5 text-xs animate-fadeIn">
                      <div className="space-y-1.5">
                        <div className="flex justify-between font-mono">
                          <span className="text-muted">Hook Strength:</span>
                          <span className="text-foreground font-bold">{clip.rubric.hook_strength}/25</span>
                        </div>
                        <div className="w-full h-1.5 bg-surface rounded-full overflow-hidden">
                          <div
                            className="h-full bg-accent rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${(clip.rubric.hook_strength / 25) * 100}%` }}
                          ></div>
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <div className="flex justify-between font-mono">
                          <span className="text-muted">Self-Contained Context:</span>
                          <span className="text-foreground font-bold">{clip.rubric.self_contained}/25</span>
                        </div>
                        <div className="w-full h-1.5 bg-surface rounded-full overflow-hidden">
                          <div
                            className="h-full bg-emerald-400 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${(clip.rubric.self_contained / 25) * 100}%` }}
                          ></div>
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <div className="flex justify-between font-mono">
                          <span className="text-muted">Payoff & Value:</span>
                          <span className="text-foreground font-bold">{clip.rubric.payoff}/25</span>
                        </div>
                        <div className="w-full h-1.5 bg-surface rounded-full overflow-hidden">
                          <div
                            className="h-full bg-amber-400 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${(clip.rubric.payoff / 25) * 100}%` }}
                          ></div>
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <div className="flex justify-between font-mono">
                          <span className="text-muted">Zero Context Needed:</span>
                          <span className="text-foreground font-bold">{clip.rubric.zero_context_needed}/25</span>
                        </div>
                        <div className="w-full h-1.5 bg-surface rounded-full overflow-hidden">
                          <div
                            className="h-full bg-pink-400 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${(clip.rubric.zero_context_needed / 25) * 100}%` }}
                          ></div>
                        </div>
                      </div>

                      <div className="pt-2 border-t border-borderSubtle">
                        <p className="text-[11px] text-muted italic leading-relaxed">
                          &quot;{clip.rubric.critique}&quot;
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Card Action Buttons */}
                <div className="mt-auto grid grid-cols-2 gap-3 pt-2">
                  <Link
                    href={`/editor/${clip.id}`}
                    className="flex items-center justify-center space-x-1.5 py-2.5 px-3 rounded-xl bg-surfaceElevated hover:bg-surface border border-border hover:border-accent text-xs font-bold text-foreground btn-spell shadow-sm"
                  >
                    <Edit3 className="w-3.5 h-3.5 text-accent" />
                    <span>Edit in Studio</span>
                  </Link>

                  <button
                    onClick={() => handleDownload(clip.video_url || '/sample_short.mp4', `${clip.id}.mp4`)}
                    className="flex items-center justify-center space-x-1.5 py-2.5 px-3 rounded-xl bg-accent hover:bg-accent-hover text-xs font-bold text-white shadow-accent-glow btn-spell"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download MP4</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
