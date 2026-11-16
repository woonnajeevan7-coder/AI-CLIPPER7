'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import {
  Sparkles,
  ArrowRight,
  Zap,
  Volume2,
  ScanFace,
  Flame,
  CheckCircle2,
  Play,
  Share2,
} from 'lucide-react';

const Hero3DCanvas = dynamic(() => import('./components/Hero3DCanvas'), { ssr: false });

export default function LandingPage() {
  const sampleClips = [
    {
      id: 'clip-1',
      title: 'Connecting the Dots in Life',
      hook: 'You cannot connect the dots looking forward; you can only connect them looking backwards.',
      duration: '32s',
      viralScore: 96,
      layout: 'Single Face (Median Crop)',
      captionStyle: 'Hormozi',
    },
    {
      id: 'clip-2',
      title: 'The Hidden Quantum Paradox',
      hook: 'What if reality is only rendered when someone is looking?',
      duration: '44s',
      viralScore: 92,
      layout: 'Split-Screen (2-Speaker)',
      captionStyle: 'Cyber Cyan',
    },
    {
      id: 'clip-3',
      title: 'Why 99% Fail at Product-Market Fit',
      hook: 'They build what they think users want instead of observing what users actually do.',
      duration: '28s',
      viralScore: 89,
      layout: 'Single Face (Punch-In Zoom)',
      captionStyle: 'Emerald Box',
    },
  ];

  return (
    <div className="flex flex-col items-center">
      {/* 3D Hero Section */}
      <section className="relative w-full overflow-hidden pt-12 pb-20 border-b border-border">
        {/* Ambient Radial Accent Glow */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-accent/15 blur-[120px] rounded-full pointer-events-none"></div>

        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col items-center text-center relative z-10">
          {/* Badge */}
          <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-surfaceElevated border border-accent/30 text-accent text-xs font-semibold mb-6 shadow-accent-glow">
            <Sparkles className="w-3.5 h-3.5 text-accent" />
            <span>AI CLIPPER PRO · Autonomous Multi-Agent Repurposing Engine</span>
          </div>

          {/* Headline */}
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-foreground max-w-4xl leading-[1.1] mb-6">
            Turn 60-Minute Videos into{' '}
            <span className="bg-gradient-to-r from-purple-400 via-accent to-pink-500 bg-clip-text text-transparent">
              Viral 9:16 Shorts
            </span>
          </h1>

          <p className="text-muted text-base sm:text-xl max-w-2xl mb-10 leading-relaxed font-sans">
            Acoustic Whisper timestamps, smart 9:16 face-tracking, dynamic background music ducking, and 4-pillar LLM virality scoring—completely autonomous.
          </p>

          {/* Primary Action Buttons */}
          <div className="flex flex-col sm:flex-row items-center gap-4 mb-12">
            <Link
              href="/projects/new"
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2.5 bg-accent hover:bg-accent-hover text-white text-base font-bold px-8 py-4 rounded-xl shadow-accent-glow transition transform hover:-translate-y-0.5"
            >
              <span>Launch Studio & Clip Video</span>
              <ArrowRight className="w-5 h-5" />
            </Link>

            <Link
              href="/billing"
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 bg-surfaceElevated hover:bg-surface border border-border text-foreground text-base font-semibold px-6 py-4 rounded-xl transition"
            >
              <span>View Free & Pro Plans</span>
            </Link>
          </div>

          {/* 3D WebGL Canvas (Exclusive to Landing Page) */}
          <div className="w-full max-w-4xl aspect-[16/9] max-h-[360px] rounded-2xl bg-surface/60 border border-border shadow-2xl overflow-hidden relative backdrop-blur-sm">
            <Hero3DCanvas />
          </div>
        </div>
      </section>

      {/* Bento Grid Features */}
      <section className="w-full py-20 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-foreground mb-4">
            Engineered for Flawless Short-Form Quality
          </h2>
          <p className="text-muted max-w-xl mx-auto text-base">
            Every clip is produced with mathematical acoustic precision, zero caption drift, and broadcast loudness compliance.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Feature 1 */}
          <div className="bg-surface border border-border rounded-2xl p-6 flex flex-col justify-between hover:border-accent/40 transition">
            <div>
              <div className="w-12 h-12 rounded-xl bg-accent/15 border border-accent/30 flex items-center justify-center text-accent mb-4">
                <Zap className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2">Acoustic Whisper Sync</h3>
              <p className="text-sm text-muted leading-relaxed">
                Word-level acoustic timestamps eliminate subtitle drift, quantizing subtitles to exact speech frames with zero latency.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-borderSubtle text-xs font-mono text-accent">
              &lt; 5ms measured drift
            </div>
          </div>

          {/* Feature 2 */}
          <div className="bg-surface border border-border rounded-2xl p-6 flex flex-col justify-between hover:border-accent/40 transition">
            <div>
              <div className="w-12 h-12 rounded-xl bg-purple-900/30 border border-purple-700/40 flex items-center justify-center text-purple-400 mb-4">
                <ScanFace className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2">Dual-Mode Framing</h3>
              <p className="text-sm text-muted leading-relaxed">
                Stationary median crop eliminates micro-jitter; PySceneDetect triggers instantaneous scene cut resets without dizzy panning.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-borderSubtle text-xs font-mono text-purple-400">
              0.0 px camera shake
            </div>
          </div>

          {/* Feature 3 */}
          <div className="bg-surface border border-border rounded-2xl p-6 flex flex-col justify-between hover:border-accent/40 transition">
            <div>
              <div className="w-12 h-12 rounded-xl bg-pink-900/30 border border-pink-700/40 flex items-center justify-center text-pink-400 mb-4">
                <Volume2 className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2">Sidechain Ducking</h3>
              <p className="text-sm text-muted leading-relaxed">
                Real sidechain compression automatically ducks background music beneath speech, calibrated to exact EBU R128 (-14 LUFS) standards.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-borderSubtle text-xs font-mono text-pink-400">
              -14.0 LUFS Broadcast standard
            </div>
          </div>

          {/* Feature 4 */}
          <div className="bg-surface border border-border rounded-2xl p-6 flex flex-col justify-between hover:border-accent/40 transition">
            <div>
              <div className="w-12 h-12 rounded-xl bg-amber-900/30 border border-amber-700/40 flex items-center justify-center text-amber-400 mb-4">
                <Flame className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2">4-Pillar Virality Judge</h3>
              <p className="text-sm text-muted leading-relaxed">
                Independent AI judge rigorously scores Hook, Self-Contained Context, Payoff, and Zero Context before selecting candidates.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-borderSubtle text-xs font-mono text-amber-400">
              100-pt Rubric verification
            </div>
          </div>
        </div>
      </section>

      {/* Demo Clips Showcase (9:16 Vertical Cards) */}
      <section className="w-full py-16 bg-surface/40 border-t border-border">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-start sm:items-end justify-between mb-12">
            <div>
              <span className="text-xs uppercase font-mono font-semibold text-accent tracking-wider">
                Live Output Gallery
              </span>
              <h2 className="text-3xl font-extrabold text-foreground mt-1">
                Curated Viral Shorts Generated Autonomous
              </h2>
            </div>
            <Link
              href="/projects/new"
              className="mt-4 sm:mt-0 text-sm font-semibold text-accent hover:text-accent-light flex items-center space-x-1"
            >
              <span>Create Your Own</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {sampleClips.map((clip) => (
              <div
                key={clip.id}
                className="bg-surfaceElevated border border-border rounded-3xl p-5 flex flex-col shadow-card-glow hover:border-accent/50 transition group"
              >
                {/* 9:16 Video Mockup Container */}
                <div className="w-full aspect-[9/16] bg-background rounded-2xl overflow-hidden relative border border-borderSubtle flex flex-col justify-between p-4 mb-5 group-hover:shadow-accent-glow transition">
                  <div className="flex items-center justify-between z-10">
                    <span className="px-2.5 py-1 rounded-md bg-black/75 backdrop-blur-md text-xs font-mono text-white border border-white/10">
                      {clip.duration}
                    </span>
                    <span className="px-2.5 py-1 rounded-md bg-accent/20 backdrop-blur-md text-xs font-mono font-bold text-accent border border-accent/40">
                      ★ {clip.viralScore}/100
                    </span>
                  </div>

                  {/* Play Button Overlay */}
                  <div className="self-center w-14 h-14 rounded-full bg-accent/90 hover:bg-accent text-white flex items-center justify-center shadow-lg transition transform group-hover:scale-110 cursor-pointer">
                    <Play className="w-6 h-6 fill-white ml-0.5" />
                  </div>

                  <div className="z-10 bg-black/85 backdrop-blur-md p-3 rounded-xl border border-white/10">
                    <p className="text-xs font-bold text-yellow-400 font-mono tracking-wide uppercase mb-1">
                      {clip.captionStyle} Style
                    </p>
                    <p className="text-xs text-foreground line-clamp-2">
                      &quot;{clip.hook}&quot;
                    </p>
                  </div>
                </div>

                {/* Card Content */}
                <h3 className="text-base font-bold text-foreground mb-1 group-hover:text-accent transition">
                  {clip.title}
                </h3>
                <p className="text-xs text-muted mb-4">{clip.layout}</p>

                <div className="mt-auto pt-4 border-t border-border flex items-center justify-between">
                  <Link
                    href={`/editor/${clip.id}`}
                    className="text-xs font-semibold text-accent hover:underline"
                  >
                    Open in Editor →
                  </Link>
                  <span className="text-xs font-mono text-muted">Ready to publish</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section className="w-full py-20 max-w-5xl mx-auto px-4 text-center">
        <div className="bg-gradient-to-b from-surfaceElevated to-surface border border-accent/30 rounded-3xl p-10 sm:p-14 relative overflow-hidden shadow-2xl">
          <div className="absolute top-0 right-0 w-64 h-64 bg-accent/20 blur-3xl rounded-full pointer-events-none"></div>
          <h2 className="text-3xl sm:text-5xl font-black text-foreground mb-4 tracking-tight">
            Ready to Multiply Your Video Reach?
          </h2>
          <p className="text-muted text-base sm:text-lg max-w-xl mx-auto mb-8">
            Paste any YouTube URL or upload a file. The multi-agent pipeline takes care of everything from transcription to vertical rendering.
          </p>
          <Link
            href="/projects/new"
            className="inline-flex items-center space-x-2 bg-accent hover:bg-accent-hover text-white text-base font-bold px-8 py-4 rounded-xl shadow-accent-glow transition transform hover:-translate-y-0.5"
          >
            <span>Start Clipping for Free</span>
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>
    </div>
  );
}
