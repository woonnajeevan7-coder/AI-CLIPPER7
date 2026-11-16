'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Link as LinkIcon,
  UploadCloud,
  ChevronDown,
  Sparkles,
  Sliders,
  Check,
  Video,
  Clock,
  Music,
  ZoomIn,
  FolderOpen,
  ArrowRight,
  Play,
  Award,
  Trophy,
  Gamepad2,
} from 'lucide-react';
import ErrorAlert from '@/components/ui/ErrorAlert';
import { useAppStore } from '@/store';
import { getValidAuthToken } from '@/lib/auth';

export default function StudioRootPage() {
  const router = useRouter();
  const setProject = useAppStore((state) => state.setProject);

  // Ingestion Mode: 'url' | 'upload'
  const [ingestMode, setIngestMode] = useState<'url' | 'upload'>('url');
  const [url, setUrl] = useState('');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  // Collapsible Advanced Options
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Form Configuration
  const [title, setTitle] = useState('');
  const [numClips, setNumClips] = useState(3);
  const [durationTarget, setDurationTarget] = useState<'20-45' | '45-60'>('20-45');
  const [framingMode, setFramingMode] = useState<'sports_gaming' | 'single_face' | 'split_screen' | 'auto'>('sports_gaming');
  const [captionPreset, setCaptionPreset] = useState('sports_gaming');
  const [punchInZoom, setPunchInZoom] = useState(true);
  const [musicDucking, setMusicDucking] = useState(true);
  const [silenceTrim, setSilenceTrim] = useState(true);

  // Submission State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Auto-detect Cricket & Gaming content
  const detectedSportsOrGaming = /cricket|ipl|t10|t20|match|wicket|bowler|batsman|yorker|over|six|gaming|gameplay|stream|clutch|esports|valorant|fortnite|gta|fifa|minecraft/i.test(
    `${title} ${url} ${uploadedFile?.name || ''}`
  );
  const isCricketOrGaming = framingMode === 'sports_gaming' || detectedSportsOrGaming;

  // Recent Projects List featuring the verified cricket video format (short_1794842257_2.mp4)
  const recentProjects = [
    {
      id: 'proj_cricket_t10',
      title: 'Abu Dhabi T10: Will Smiths Yorker Disaster',
      duration: '26.7s',
      clipsCount: 2,
      topScore: 98,
      date: 'Just now',
      status: 'Ready',
      formatTag: '🏏 Cricket Action 9:16 + Top Banner',
      headline: 'WILL SMITHS YORKER DISASTER',
    },
    {
      id: 'proj_demo_1',
      title: 'Connecting the Dots in Life',
      duration: '32s',
      clipsCount: 3,
      topScore: 96,
      date: 'Today',
      status: 'Ready',
      formatTag: '🎙️ Face Tracking',
      headline: 'CONNECTING THE DOTS',
    },
    {
      id: 'proj_demo_2',
      title: 'The Hidden Quantum Paradox',
      duration: '44s',
      clipsCount: 3,
      topScore: 92,
      date: 'Yesterday',
      status: 'Ready',
      formatTag: '👥 2-Speaker Split',
      headline: 'THE QUANTUM PARADOX',
    },
  ];

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setUploadedFile(file);
      if (!title) setTitle(file.name.replace(/\.[^/.]+$/, ''));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (ingestMode === 'url' && !url.trim()) {
      setErrorMsg('Please enter a valid YouTube or video URL.');
      return;
    }
    if (ingestMode === 'upload' && !uploadedFile) {
      setErrorMsg('Please select or drag a video file to upload.');
      return;
    }

    setIsSubmitting(true);

    try {
      const projectPayload = {
        title: title.trim() || (ingestMode === 'url' ? 'YouTube Podcast Short' : uploadedFile?.name || 'Uploaded Video'),
        source_type: ingestMode === 'url' ? 'youtube' : 'upload',
        source_url: ingestMode === 'url' ? url.trim() : null,
        num_clips: numClips,
        caption_style: captionPreset,
        framing_mode: isCricketOrGaming ? 'sports_gaming' : framingMode,
      };

      const authToken = await getValidAuthToken();
      // Call FastAPI backend
      const response = await fetch('http://localhost:8000/api/v1/projects/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify(projectPayload),
      });

      if (!response.ok) {
        // Fallback for standalone demo when backend is offline
        const mockJobId = `job_${Date.now()}`;
        const mockProjectId = `proj_${Date.now()}`;
        setProject(mockProjectId, mockJobId, projectPayload.title);
        router.push(`/projects/${mockProjectId}/stepper?job_id=${mockJobId}&title=${encodeURIComponent(projectPayload.title)}`);
        return;
      }

      const data = await response.json();
      setProject(data.project_id, data.job_id, data.title);
      router.push(`/projects/${data.project_id}/stepper?job_id=${data.job_id}&title=${encodeURIComponent(data.title)}`);
    } catch (err: any) {
      const mockJobId = `job_${Date.now()}`;
      const mockProjectId = `proj_${Date.now()}`;
      setProject(mockProjectId, mockJobId, title || 'New Video Project');
      router.push(`/projects/${mockProjectId}/stepper?job_id=${mockJobId}&title=${encodeURIComponent(title || 'New Video Project')}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
      {/* Studio Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-8 border-b border-border mb-10">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-accent mb-1 font-semibold">
            <Sparkles className="w-4 h-4" />
            <span>AI CLIPPER STUDIO</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-foreground tracking-tight">
            Create Viral 9:16 Shorts
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Autonomous multi-agent transcription, dual-mode 9:16 framing, and 4-pillar rubric curation.
          </p>
        </div>

        <Link
          href="/about"
          className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-mono font-semibold bg-surfaceElevated border border-border hover:border-accent/40 text-zinc-300 hover:text-white transition btn-spell"
        >
          <span>View Engine Specs &amp; 3D Demo</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Cricket & Gaming Video Format Detected Alert */}
      {isCricketOrGaming && (
        <div className="mb-8 p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between shadow-card-glow animate-fadeIn">
          <div className="flex items-center space-x-3.5">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 flex-shrink-0">
              <Trophy className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-bold text-amber-300 flex items-center space-x-2">
                <span>Cricket &amp; Gaming Video Format Active</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200">
                  MATCHING short_1794842257_2
                </span>
              </p>
              <p className="text-xs text-zinc-300 mt-0.5">
                Full-screen 9:16 Action Crop (1080x1920) · Bold Top Headline Banner · Bottom Scoreboard &amp; HUD Safe Zone
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setFramingMode('single_face')}
            className="text-xs font-mono text-zinc-400 hover:text-white underline underline-offset-2 ml-4 flex-shrink-0"
          >
            Change
          </button>
        </div>
      )}

      {errorMsg && (
        <div className="mb-6">
          <ErrorAlert message={errorMsg} onRetry={() => setErrorMsg(null)} />
        </div>
      )}

      {/* Main Creation Card */}
      <div className="bg-surface border border-border rounded-3xl p-6 sm:p-8 shadow-card-glow mb-14">
        {/* Ingestion Mode Toggle */}
        <div className="flex rounded-xl bg-surfaceElevated p-1.5 border border-border mb-8 max-w-md mx-auto shadow-inner">
          <button
            type="button"
            onClick={() => setIngestMode('url')}
            className={`flex-1 flex items-center justify-center space-x-2 py-2.5 rounded-lg text-sm font-semibold btn-spell ${
              ingestMode === 'url'
                ? 'bg-accent text-white shadow-accent-glow'
                : 'text-zinc-400 hover:text-foreground hover:bg-surface/50'
            }`}
          >
            <LinkIcon className="w-4 h-4" />
            <span>YouTube URL</span>
          </button>
          <button
            type="button"
            onClick={() => setIngestMode('upload')}
            className={`flex-1 flex items-center justify-center space-x-2 py-2.5 rounded-lg text-sm font-semibold btn-spell ${
              ingestMode === 'upload'
                ? 'bg-accent text-white shadow-accent-glow'
                : 'text-zinc-400 hover:text-foreground hover:bg-surface/50'
            }`}
          >
            <UploadCloud className="w-4 h-4" />
            <span>Upload File</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Project Title Input */}
          <div>
            <label htmlFor="studio-project-title" className="block text-xs font-mono font-semibold uppercase text-zinc-300 tracking-wider mb-2">
              Project Title (Optional)
            </label>
            <input
              id="studio-project-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Lex Fridman Ep #412 Viral Highlights"
              className="w-full bg-surfaceElevated border border-border rounded-xl px-4 py-3 text-foreground placeholder:text-zinc-400 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition font-sans"
            />
          </div>

          {/* Ingestion Input */}
          {ingestMode === 'url' ? (
            <div>
              <label htmlFor="studio-video-url" className="block text-xs font-mono font-semibold uppercase text-zinc-300 tracking-wider mb-2">
                Video Link
              </label>
              <div className="relative">
                <input
                  id="studio-video-url"
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="w-full bg-surfaceElevated border border-border rounded-xl pl-11 pr-4 py-3.5 text-foreground placeholder:text-zinc-400 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition font-sans"
                  required={ingestMode === 'url'}
                />
                <LinkIcon className="w-5 h-5 text-zinc-400 absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
              <p className="text-xs text-zinc-400 mt-2">
                Protected against SSRF. Supports YouTube videos, live replays, and long-form podcasts.
              </p>
            </div>
          ) : (
            <div>
              <span className="block text-xs font-mono font-semibold uppercase text-zinc-300 tracking-wider mb-2">
                Video Media File
              </span>
              <div
                tabIndex={0}
                role="button"
                aria-label="Upload video file - Click to browse or drag and drop file here"
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleFileDrop}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    document.getElementById('studio-file-input')?.click();
                  }
                }}
                className="w-full border-2 border-dashed border-border hover:border-accent/60 rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer bg-surfaceElevated/50 transition group focus-ring"
                onClick={() => document.getElementById('studio-file-input')?.click()}
              >
                <div className="w-12 h-12 rounded-xl bg-accent/15 border border-accent/30 flex items-center justify-center text-accent mb-3 group-hover:scale-110 transition">
                  <UploadCloud className="w-6 h-6" />
                </div>
                {uploadedFile ? (
                  <div className="space-y-1">
                    <p className="text-sm font-bold text-foreground">{uploadedFile.name}</p>
                    <p className="text-xs font-mono text-zinc-400">
                      {(uploadedFile.size / (1024 * 1024)).toFixed(1)} MB
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-foreground">
                      Click to browse or drop video here
                    </p>
                    <p className="text-xs text-zinc-400 font-mono">
                      MP4, MOV, MKV up to 500MB
                    </p>
                  </div>
                )}
                <input
                  id="studio-file-input"
                  type="file"
                  aria-label="Select video file"
                  accept="video/mp4,video/quicktime,video/x-matroska"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setUploadedFile(e.target.files[0]);
                      if (!title) setTitle(e.target.files[0].name.replace(/\.[^/.]+$/, ''));
                    }
                  }}
                />
              </div>
            </div>
          )}

          {/* Collapsible Options Accordion */}
          <div className="border border-border hover:border-accent/30 rounded-2xl overflow-hidden bg-surfaceElevated/30 transition-colors">
            <button
              type="button"
              aria-expanded={showAdvanced}
              aria-controls="studio-advanced-panel"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full px-5 py-4 flex items-center justify-between text-left hover:bg-surfaceElevated/60 transition group btn-spell"
            >
              <div className="flex items-center space-x-2.5">
                <Sliders className="w-4 h-4 text-accent transition-transform duration-300 group-hover:rotate-45" />
                <span className="text-sm font-semibold text-foreground">
                  Curation &amp; Output Preferences
                </span>
                <span className="text-xs font-mono text-zinc-400 px-2 py-0.5 rounded bg-surface border border-border">
                  {numClips} clips · {durationTarget}s · {captionPreset}
                </span>
              </div>
              <ChevronDown className={`w-4 h-4 text-zinc-400 transition-transform duration-300 ${showAdvanced ? 'rotate-180 text-accent' : ''}`} />
            </button>

            {showAdvanced && (
              <div id="studio-advanced-panel" className="p-5 border-t border-border space-y-6">
                {/* 1. Video Genre & Framing Format */}
                <div>
                  <span className="block text-xs font-mono font-semibold uppercase text-zinc-300 tracking-wider mb-2">
                    Video Genre &amp; 9:16 Framing Format
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" role="radiogroup" aria-label="Video genre and framing format">
                    <button
                      type="button"
                      role="radio"
                      aria-checked={framingMode === 'sports_gaming'}
                      onClick={() => {
                        setFramingMode('sports_gaming');
                        setCaptionPreset('sports_gaming');
                      }}
                      className={`p-3.5 rounded-xl border text-left btn-spell flex items-start space-x-3 ${
                        framingMode === 'sports_gaming'
                          ? 'bg-amber-500/15 border-amber-500/50 shadow-sm ring-1 ring-amber-500/50'
                          : 'bg-surfaceElevated border-border text-zinc-400 hover:text-foreground'
                      }`}
                    >
                      <Trophy className={`w-5 h-5 mt-0.5 flex-shrink-0 ${framingMode === 'sports_gaming' ? 'text-amber-400' : 'text-zinc-400'}`} />
                      <div>
                        <p className={`text-xs font-bold ${framingMode === 'sports_gaming' ? 'text-amber-300' : 'text-foreground'}`}>
                          🏏 Cricket &amp; Gaming Format
                        </p>
                        <p className="text-[11px] text-zinc-400 mt-0.5">
                          Action 9:16 crop · Top headline banner · Scoreboard &amp; HUD safe zone (short_1794842257_2)
                        </p>
                      </div>
                    </button>

                    <button
                      type="button"
                      role="radio"
                      aria-checked={framingMode === 'single_face'}
                      onClick={() => setFramingMode('single_face')}
                      className={`p-3.5 rounded-xl border text-left btn-spell flex items-start space-x-3 ${
                        framingMode === 'single_face'
                          ? 'bg-accent/20 border-accent shadow-sm ring-1 ring-accent'
                          : 'bg-surfaceElevated border-border text-zinc-400 hover:text-foreground'
                      }`}
                    >
                      <Video className={`w-5 h-5 mt-0.5 flex-shrink-0 ${framingMode === 'single_face' ? 'text-accent' : 'text-zinc-400'}`} />
                      <div>
                        <p className={`text-xs font-bold ${framingMode === 'single_face' ? 'text-accent-light' : 'text-foreground'}`}>
                          🎙️ Podcasts &amp; Solo Speaker
                        </p>
                        <p className="text-[11px] text-zinc-400 mt-0.5">
                          Active speaker face tracking · Smooth EMA camera centering
                        </p>
                      </div>
                    </button>
                  </div>
                </div>

                {/* 2. Target Duration */}
                <div>
                  <span className="block text-xs font-mono font-semibold uppercase text-zinc-300 tracking-wider mb-2">
                    Clip Duration Window
                  </span>
                  <div className="grid grid-cols-2 gap-3" role="group" aria-label="Target clip duration window">
                    <button
                      type="button"
                      aria-pressed={durationTarget === '20-45'}
                      onClick={() => setDurationTarget('20-45')}
                      className={`py-2.5 px-4 rounded-xl text-sm font-semibold border flex items-center justify-between btn-spell ${
                        durationTarget === '20-45'
                          ? 'bg-accent/20 border-accent text-accent-light shadow-sm'
                          : 'bg-surfaceElevated border-border text-zinc-400 hover:text-foreground'
                      }`}
                    >
                      <span>20 - 45s (Reels / TikTok)</span>
                      {durationTarget === '20-45' && <Check className="w-4 h-4 text-accent" />}
                    </button>
                    <button
                      type="button"
                      aria-pressed={durationTarget === '45-60'}
                      onClick={() => setDurationTarget('45-60')}
                      className={`py-2.5 px-4 rounded-xl text-sm font-semibold border flex items-center justify-between btn-spell ${
                        durationTarget === '45-60'
                          ? 'bg-accent/20 border-accent text-accent-light shadow-sm'
                          : 'bg-surfaceElevated border-border text-zinc-400 hover:text-foreground'
                      }`}
                    >
                      <span>45 - 60s (YouTube Shorts)</span>
                      {durationTarget === '45-60' && <Check className="w-4 h-4 text-accent" />}
                    </button>
                  </div>
                </div>

                {/* 2. Number of Clips */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label htmlFor="studio-num-clips" className="text-xs font-mono font-semibold uppercase text-zinc-300 tracking-wider">
                      Number of Viral Candidates
                    </label>
                    <span className="text-xs font-mono font-bold text-accent-light">
                      {numClips} {numClips === 1 ? 'Clip' : 'Clips'}
                    </span>
                  </div>
                  <input
                    id="studio-num-clips"
                    type="range"
                    min={1}
                    max={5}
                    value={numClips}
                    aria-label="Target number of viral candidate clips"
                    aria-valuemin={1}
                    aria-valuemax={5}
                    aria-valuenow={numClips}
                    aria-valuetext={`${numClips} clips`}
                    onChange={(e) => setNumClips(parseInt(e.target.value))}
                    className="w-full accent-accent bg-border h-2 rounded-lg cursor-pointer focus-ring"
                  />
                  <div className="flex justify-between text-[11px] font-mono text-zinc-400 mt-1">
                    <span>1 Clip (Quickest)</span>
                    <span>3 Clips (Standard)</span>
                    <span>5 Clips (Maximum)</span>
                  </div>
                </div>

                {/* 3. Subtitle Preset */}
                <div>
                  <span className="block text-xs font-mono font-semibold uppercase text-zinc-300 tracking-wider mb-2">
                    Subtitle Typography Preset
                  </span>
                  <div
                    role="radiogroup"
                    aria-label="Subtitle typography presets"
                    className="grid grid-cols-2 sm:grid-cols-4 gap-3"
                  >
                    {[
                      { id: 'sports_gaming', name: 'Sports Gold', desc: 'HUD-Safe / Gold Pop' },
                      { id: 'hormozi', name: 'Hormozi', desc: 'Yellow / Bold' },
                      { id: 'cyber_cyan', name: 'Cyber Cyan', desc: 'Neon Accent' },
                      { id: 'emerald_box', name: 'Emerald Box', desc: 'Green Box' },
                      { id: 'bold_minimal', name: 'Bold Minimal', desc: 'Clean White' },
                    ].map((st) => (
                      <button
                        key={st.id}
                        type="button"
                        role="radio"
                        aria-checked={captionPreset === st.id}
                        aria-label={`${st.name} preset: ${st.desc}`}
                        onClick={() => setCaptionPreset(st.id)}
                        className={`p-3 rounded-xl border text-left btn-spell ${
                          captionPreset === st.id
                            ? 'bg-accent/20 border-accent shadow-sm ring-1 ring-accent'
                            : 'bg-surfaceElevated border-border hover:border-zinc-500'
                        }`}
                      >
                        <p className={`text-sm font-bold ${captionPreset === st.id ? 'text-accent-light' : 'text-foreground'}`}>
                          {st.name}
                        </p>
                        <p className="text-[11px] text-zinc-400">{st.desc}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* 4. Motion & Audio Polish Toggles */}
                <div>
                  <label className="block text-xs font-mono font-semibold uppercase text-zinc-300 tracking-wider mb-3">
                    Production Polish Toggles
                  </label>
                  <div className="space-y-3">
                    <label className="flex items-center justify-between p-3 rounded-xl bg-surfaceElevated border border-border cursor-pointer">
                      <div className="flex items-center space-x-3">
                        <ZoomIn className="w-4 h-4 text-accent" />
                        <div>
                          <p className="text-sm font-semibold text-foreground">Dynamic Punch-In Step Zoom</p>
                          <p className="text-xs text-zinc-400">1.14x emphasis punch-in zoom during vocal spikes</p>
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={punchInZoom}
                        onChange={(e) => setPunchInZoom(e.target.checked)}
                        className="w-4 h-4 accent-accent rounded"
                      />
                    </label>

                    <label className="flex items-center justify-between p-3 rounded-xl bg-surfaceElevated border border-border cursor-pointer">
                      <div className="flex items-center space-x-3">
                        <Music className="w-4 h-4 text-pink-400" />
                        <div>
                          <p className="text-sm font-semibold text-foreground">Real Sidechain BGM Ducking</p>
                          <p className="text-xs text-zinc-400">Attenuates background music when speech begins (-14 LUFS)</p>
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={musicDucking}
                        onChange={(e) => setMusicDucking(e.target.checked)}
                        className="w-4 h-4 accent-accent rounded"
                      />
                    </label>

                    <label className="flex items-center justify-between p-3 rounded-xl bg-surfaceElevated border border-border cursor-pointer">
                      <div className="flex items-center space-x-3">
                        <Clock className="w-4 h-4 text-emerald-400" />
                        <div>
                          <p className="text-sm font-semibold text-foreground">Silence Excision &amp; Sync Lock</p>
                          <p className="text-xs text-zinc-400">Removes dead pauses &gt; 0.5s while preserving subtitle sync</p>
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={silenceTrim}
                        onChange={(e) => setSilenceTrim(e.target.checked)}
                        className="w-4 h-4 accent-accent rounded"
                      />
                    </label>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Submit Action */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-accent hover:bg-accent-hover text-white text-base font-bold py-4 rounded-xl shadow-accent-glow btn-spell flex items-center justify-center space-x-2.5 disabled:opacity-50 group"
            >
              {isSubmitting ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  <span>Initializing Multi-Agent Pipeline...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5 transition-transform duration-300 group-hover:rotate-12" />
                  <span>Start Autonomous Clipping</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Recent Projects Section */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-2">
            <FolderOpen className="w-5 h-5 text-accent" />
            <h2 className="text-xl font-bold text-foreground">Recent Clipping Projects</h2>
          </div>
          <span className="text-xs font-mono text-zinc-400">Last 3 runs available</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {recentProjects.map((p) => (
            <div
              key={p.id}
              className="bg-surface border border-border hover:border-accent/40 rounded-2xl p-5 flex flex-col justify-between card-spell group"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-accent/15 text-accent-light border border-accent/30 font-bold">
                    ★ {p.topScore}/100 Top Virality
                  </span>
                  <span className="text-xs font-mono text-zinc-400">{p.date}</span>
                </div>
                <h3 className="text-sm font-bold text-foreground mb-1 group-hover:text-accent-light transition-colors line-clamp-1">
                  {p.title}
                </h3>
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surfaceElevated border border-border text-zinc-300">
                    {p.formatTag}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mb-4">
                  {p.clipsCount} viral shorts generated · {p.duration} duration
                </p>
              </div>

              <div className="pt-3 border-t border-border flex items-center justify-between">
                <Link
                  href={`/projects/${p.id}`}
                  className="text-xs font-semibold text-accent hover:text-accent-light flex items-center space-x-1"
                >
                  <span>View Results</span>
                  <span>→</span>
                </Link>
                <Link
                  href={`/editor/${p.id.replace('proj_', 'clip-')}`}
                  className="text-xs font-mono text-zinc-400 hover:text-foreground"
                >
                  Open Editor
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
