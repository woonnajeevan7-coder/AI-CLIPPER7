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
  Award,
  Play,
} from 'lucide-react';

const Hero3DCanvas = dynamic(() => import('./components/Hero3DCanvas'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-surface text-muted text-xs font-mono">
      Initializing 3D WebGL Canvas...
    </div>
  ),
});

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
      {/* 3D Hero Section (Lazy-Loaded Three.js Isolated Here) */}
      <section className="relative w-full overflow-hidden pt-12 pb-20 border-b border-border">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-accent/15 blur-[120px] rounded-full pointer-events-none"></div>

        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col items-center text-center relative z-10">
          <div className="inline-flex items-center space-x-2 px-4 py-1.5 rounded-full bg-surfaceElevated border border-accent/40 text-accent-light text-xs font-semibold mb-6 shadow-accent-glow animate-float">
            <Sparkles className="w-3.5 h-3.5 text-accent animate-spin-slow" />
            <span className="tracking-wide">AI CLIPPER PRO · Autonomous Multi-Agent Repurposing Engine</span>
          </div>

          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-foreground max-w-4xl leading-[1.1] mb-6">
            Transform Long-Form Videos into{' '}
            <span className="bg-gradient-to-r from-purple-400 via-accent to-pink-500 bg-clip-text text-transparent">
              Curated Viral Shorts
            </span>
          </h1>

          <p className="text-muted text-base sm:text-xl max-w-2xl mb-10 leading-relaxed font-sans">
            Acoustic Whisper transcription, dual-mode 9:16 smart framing, sidechain audio ducking, and 4-pillar rubric scoring.
          </p>

          <div className="flex flex-col sm:flex-row items-center gap-4 mb-12">
            <Link
              href="/projects/new"
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2.5 bg-accent hover:bg-accent-hover text-white text-base font-bold px-8 py-4 rounded-xl shadow-accent-glow btn-spell group"
            >
              <span>Open Studio &amp; Clip Video</span>
              <ArrowRight className="w-5 h-5 transition-transform duration-200 group-hover:translate-x-1" />
            </Link>

            <Link
              href="/billing"
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 bg-surfaceElevated hover:bg-surface border border-border hover:border-accent/30 text-foreground text-base font-semibold px-6 py-4 rounded-xl btn-spell shadow-sm"
            >
              <span>View Plan Quotas</span>
            </Link>
          </div>

          {/* 3D WebGL Canvas (Exclusive to Landing Page Hero) */}
          <div className="w-full max-w-4xl aspect-[16/9] max-h-[360px] rounded-2xl bg-surface/60 border border-border shadow-2xl overflow-hidden relative backdrop-blur-sm card-spell">
            <Hero3DCanvas />
          </div>
        </div>
      </section>

      {/* Bento Grid: Architecture & Technical Pipeline */}
      <section className="w-full py-20 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-foreground mb-4">
            Pipeline Architecture &amp; Specifications
          </h2>
          <p className="text-muted max-w-xl mx-auto text-base">
            Every clip is produced with acoustic alignment, broadcast loudness compliance, and rubric evaluation.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-surface border border-border rounded-2xl p-6 flex flex-col justify-between card-spell group">
            <div>
              <div className="w-12 h-12 rounded-xl bg-accent/15 border border-accent/30 flex items-center justify-center text-accent mb-4 transition-transform duration-300 group-hover:scale-110">
                <Zap className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2 group-hover:text-accent-light transition-colors">
                Acoustic Whisper Sync
              </h3>
              <p className="text-sm text-muted leading-relaxed">
                Word-level acoustic timestamps align subtitles to audio frames without drift. Centisecond quantization lock.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-borderSubtle text-xs font-mono text-accent flex items-center space-x-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
              </span>
              <span>0.0 ms measured drift</span>
            </div>
          </div>

          <div className="bg-surface border border-border rounded-2xl p-6 flex flex-col justify-between card-spell group">
            <div>
              <div className="w-12 h-12 rounded-xl bg-purple-900/30 border border-purple-700/40 flex items-center justify-center text-purple-400 mb-4 transition-transform duration-300 group-hover:scale-110">
                <ScanFace className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2 group-hover:text-purple-300 transition-colors">
                Dual-Mode Framing
              </h3>
              <p className="text-sm text-muted leading-relaxed">
                Stationary median crop avoids micro-jitter noise; PySceneDetect triggers instantaneous scene cut resets.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-borderSubtle text-xs font-mono text-purple-400 flex items-center space-x-2">
              <span className="w-2 h-2 rounded-sm bg-purple-400"></span>
              <span>Stationary median lock</span>
            </div>
          </div>

          <div className="bg-surface border border-border rounded-2xl p-6 flex flex-col justify-between card-spell group">
            <div>
              <div className="w-12 h-12 rounded-xl bg-pink-900/30 border border-pink-700/40 flex items-center justify-center text-pink-400 mb-4 transition-transform duration-300 group-hover:scale-110">
                <Volume2 className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2 group-hover:text-pink-300 transition-colors">
                Sidechain Ducking
              </h3>
              <p className="text-sm text-muted leading-relaxed">
                Sidechain compression filter attenuates background audio during speech to meet EBU R128 (-14 LUFS) standards.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-borderSubtle text-xs font-mono text-pink-400 flex items-center justify-between">
              <span>-14.0 LUFS Target</span>
              <div className="flex items-end space-x-1 h-3.5" title="Live sidechain audio metering">
                <span className="w-1 bg-pink-400 rounded-full animate-wave1"></span>
                <span className="w-1 bg-pink-400 rounded-full animate-wave2"></span>
                <span className="w-1 bg-pink-400 rounded-full animate-wave3"></span>
                <span className="w-1 bg-pink-400 rounded-full animate-wave4"></span>
              </div>
            </div>
          </div>

          <div className="bg-surface border border-border rounded-2xl p-6 flex flex-col justify-between card-spell group">
            <div>
              <div className="w-12 h-12 rounded-xl bg-amber-900/30 border border-amber-700/40 flex items-center justify-center text-amber-400 mb-4 transition-transform duration-300 group-hover:scale-110">
                <Award className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2 group-hover:text-amber-300 transition-colors">
                4-Pillar Rubric Judge
              </h3>
              <p className="text-sm text-muted leading-relaxed">
                Evaluates candidate clips on hook strength, self-containment, payoff delivery, and context independence.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-borderSubtle text-xs font-mono text-amber-400 flex items-center space-x-1.5">
              <span>★</span>
              <span>100-pt Rubric Criteria</span>
            </div>
          </div>
        </div>
      </section>

      {/* Gallery Section */}
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
              <span>Create New Project</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {sampleClips.map((clip) => (
              <div
                key={clip.id}
                className="bg-surfaceElevated border border-border rounded-3xl p-5 flex flex-col card-spell group"
              >
                <div className="w-full aspect-[9/16] bg-background rounded-2xl overflow-hidden relative border border-borderSubtle flex flex-col justify-between p-4 mb-5 group-hover:border-accent/40 transition-all duration-300">
                  <div className="flex items-center justify-between z-10">
                    <span className="px-2.5 py-1 rounded-md bg-black/80 backdrop-blur-md text-xs font-mono text-white border border-white/10 shadow-sm">
                      {clip.duration}
                    </span>
                    <span className="px-2.5 py-1 rounded-md bg-accent/25 backdrop-blur-md text-xs font-mono font-bold text-accent-light border border-accent/50 shadow-accent-glow-sm">
                      ★ {clip.viralScore}/100
                    </span>
                  </div>

                  <div className="self-center w-14 h-14 rounded-full bg-accent/90 hover:bg-accent text-white flex items-center justify-center shadow-lg transition-all duration-200 group-hover:scale-110 active:scale-95 cursor-pointer">
                    <Play className="w-6 h-6 fill-white ml-0.5" />
                  </div>

                  <div className="z-10 bg-black/90 backdrop-blur-md p-3.5 rounded-xl border border-white/10 shadow-md">
                    <p className="text-xs font-bold text-yellow-400 font-mono tracking-wide uppercase mb-1">
                      {clip.captionStyle} Style
                    </p>
                    <p className="text-xs text-foreground line-clamp-2 leading-relaxed">
                      &quot;{clip.hook}&quot;
                    </p>
                  </div>
                </div>

                <h3 className="text-base font-bold text-foreground mb-1 group-hover:text-accent-light transition-colors">
                  {clip.title}
                </h3>
                <p className="text-xs text-muted mb-4">{clip.layout}</p>

                <div className="mt-auto pt-4 border-t border-border flex items-center justify-between">
                  <Link
                    href={`/editor/${clip.id}`}
                    className="text-xs font-semibold text-accent hover:text-accent-light flex items-center space-x-1 group/btn btn-spell"
                  >
                    <span>Open in Editor</span>
                    <span className="transition-transform duration-200 group-hover/btn:translate-x-1">→</span>
                  </Link>
                  <span className="text-xs font-mono text-muted">Ready for export</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom Action Section */}
      <section className="w-full py-20 max-w-5xl mx-auto px-4 text-center">
        <div className="bg-gradient-to-b from-surfaceElevated to-surface border border-accent/40 rounded-3xl p-10 sm:p-14 relative overflow-hidden shadow-card-glow card-spell">
          <div className="absolute top-0 right-0 w-64 h-64 bg-accent/20 blur-3xl rounded-full pointer-events-none animate-pulse-subtle"></div>
          <h2 className="text-3xl sm:text-5xl font-black text-foreground mb-4 tracking-tight">
            Convert Video Files into Structured 9:16 Shorts
          </h2>
          <p className="text-muted text-base sm:text-lg max-w-xl mx-auto mb-8 leading-relaxed">
            Provide a YouTube URL or media file to run autonomous transcription, scene detection, face tracking, and vertical video rendering.
          </p>
          <Link
            href="/projects/new"
            className="inline-flex items-center space-x-2.5 bg-accent hover:bg-accent-hover text-white text-base font-bold px-8 py-4 rounded-xl shadow-accent-glow btn-spell group"
          >
            <span>Start Clipping Project</span>
            <ArrowRight className="w-5 h-5 transition-transform duration-200 group-hover:translate-x-1" />
          </Link>
        </div>
      </section>
    </div>
  );
}
