'use client';

import React, { useState } from 'react';
import dynamic from 'next/dynamic';

const Hero3DCanvas = dynamic(() => import('./components/Hero3DCanvas'), { ssr: false });

export default function HomePage() {
  const [url, setUrl] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [clips, setClips] = useState([
    {
      id: 'clip_1',
      title: 'Mindset Shift for Rapid Growth',
      headline: 'WHY 99% FAIL AT CODING',
      duration: '34s',
      viralScore: 95,
      previewUrl: '/sample_short.mp4'
    },
    {
      id: 'clip_2',
      title: 'The Hidden Trap in Modern Startups',
      headline: 'THE BIGGEST STARTUP MISTAKE',
      duration: '42s',
      viralScore: 91,
      previewUrl: '/sample_short_2.mp4'
    }
  ]);

  const handleRunPipeline = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    setIsProcessing(true);
    setTimeout(() => {
      setIsProcessing(false);
    }, 3000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Navigation */}
      <header className="border-b border-slate-800 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <span className="text-2xl font-black bg-gradient-to-r from-amber-400 via-rose-500 to-purple-600 bg-clip-text text-transparent">
            AI CLIPPER PRO
          </span>
          <span className="text-xs uppercase px-2 py-0.5 rounded bg-purple-900/60 text-purple-300 font-semibold border border-purple-700">
            v1.0
          </span>
        </div>
        <nav className="flex items-center space-x-6 text-sm font-medium">
          <a href="/editor" className="hover:text-purple-400 transition">Editor</a>
          <a href="/brand-kit" className="hover:text-purple-400 transition">Brand Kit</a>
          <a href="/pricing" className="hover:text-purple-400 transition">Pricing</a>
          <button className="bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg text-white font-semibold shadow-lg shadow-purple-900/40 transition">
            Sign In
          </button>
        </nav>
      </header>

      {/* Hero Ingestion Section */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-12 flex flex-col items-center">
        <h1 className="text-4xl md:text-6xl font-extrabold text-center tracking-tight mb-4">
          Turn Any Video into{' '}
          <span className="bg-gradient-to-r from-amber-400 via-rose-500 to-purple-500 bg-clip-text text-transparent">
            Viral Shorts
          </span>
        </h1>
        <p className="text-slate-400 text-lg md:text-xl text-center max-w-2xl mb-8">
          Autonomous multi-agent curation, word-by-word karaoke subtitles, face tracking, and 2-speaker split screens in seconds.
        </p>

        {/* Interactive 3D Web Experience */}
        <div className="w-full max-w-3xl mb-10">
          <Hero3DCanvas />
        </div>

        {/* Input Card */}
        <div className="w-full max-w-3xl bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-2xl backdrop-blur-sm mb-12">
          <form onSubmit={handleRunPipeline} className="space-y-4">
            <div className="flex flex-col md:flex-row gap-3">
              <label htmlFor="video-url" className="sr-only">
                YouTube Video or Podcast URL
              </label>
              <input
                id="video-url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Paste YouTube Video / Podcast URL..."
                aria-label="YouTube Video or Podcast URL"
                className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
                required
              />
              <button
                type="submit"
                disabled={isProcessing}
                aria-label="Generate viral vertical shorts"
                className="bg-gradient-to-r from-amber-500 to-purple-600 hover:from-amber-600 hover:to-purple-700 focus-visible:ring-2 focus-visible:ring-purple-400 text-white font-bold px-8 py-3 rounded-xl shadow-lg transition flex items-center justify-center space-x-2 min-h-[48px]"
              >
                {isProcessing ? 'Generating...' : '⚡ Generate Shorts'}
              </button>
            </div>
            <div className="text-xs text-slate-400 text-center">
              SSRF Guard Active · 1080x1920 60FPS NVENC Acceleration · -14 LUFS Audio Normalization
            </div>
          </form>
        </div>

        {/* Live Clips Gallery */}
        <section className="w-full">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold">Curated Viral Shorts</h2>
            <span className="text-sm text-slate-400">Ranked by 4-Factor Virality Rubric</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {clips.map((clip) => (
              <div key={clip.id} className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden hover:border-slate-700 transition">
                <div className="aspect-[9/16] bg-slate-950 flex flex-col items-center justify-center p-4 relative group">
                  <span className="absolute top-4 left-4 bg-red-600/90 text-white text-xs font-black px-2.5 py-1 rounded-full uppercase tracking-wider">
                    🔥 Score: {clip.viralScore}/100
                  </span>
                  <div className="bg-black/75 text-white font-black text-center text-sm px-3 py-1.5 rounded-lg mb-4 border border-white/20">
                    {clip.headline}
                  </div>
                  <button className="bg-white/10 hover:bg-white/20 text-white px-4 py-2 rounded-full text-xs font-semibold backdrop-blur-sm border border-white/20 transition">
                    ▶ Preview Clip
                  </button>
                </div>
                <div className="p-4">
                  <h3 className="font-bold text-base mb-1 truncate">{clip.title}</h3>
                  <p className="text-xs text-slate-400 mb-4">Duration: {clip.duration}</p>
                  <div className="flex space-x-2">
                    <a
                      href="/editor"
                      className="flex-1 text-center bg-slate-800 hover:bg-slate-700 text-xs font-semibold py-2 rounded-lg transition"
                    >
                      ✂️ Edit Text
                    </a>
                    <button className="bg-purple-600 hover:bg-purple-700 text-xs font-semibold px-4 py-2 rounded-lg transition">
                      ⬇ Download
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
