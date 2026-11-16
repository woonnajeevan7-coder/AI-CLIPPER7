'use client';

import React, { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  Cpu,
  HardDrive,
  Key,
  ShieldCheck,
  Save,
  Check,
  Eye,
  EyeOff,
  Activity,
} from 'lucide-react';
import ErrorAlert from '@/components/ui/ErrorAlert';

export default function SettingsPage() {
  // Never pre-fill API keys from environment or defaults
  const [groqKey, setGroqKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [useNvenc, setUseNvenc] = useState(true);
  const [storageType, setStorageType] = useState('local');
  const [resolution, setResolution] = useState('1080x1920');

  const [capabilities, setCapabilities] = useState<{
    ffmpeg: boolean;
    ffprobe: boolean;
    gpu_nvenc: boolean;
    face_tracking: boolean;
    database: boolean;
    storage?: string;
  }>({
    ffmpeg: true,
    ffprobe: true,
    gpu_nvenc: false,
    face_tracking: true,
    database: true,
  });

  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Probe live system capabilities from backend /health
  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then((res) => res.json())
      .then((data) => {
        if (data.capabilities) {
          setCapabilities(data.capabilities);
          setUseNvenc(!!data.capabilities.gpu_nvenc);
          setStorageType(data.capabilities.storage || 'local');
        }
      })
      .catch(() => {
        // Fallback to local default capability flags
      });

    // Check if user previously saved a custom key in their browser localStorage
    const savedUserKey = localStorage.getItem('user_groq_api_key');
    if (savedUserKey && typeof savedUserKey === 'string') {
      setGroqKey(savedUserKey);
    }
  }, []);

  const handleSaveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMsg(null);
    setSavedSuccess(false);

    try {
      if (groqKey.trim()) {
        localStorage.setItem('user_groq_api_key', groqKey.trim());
      } else {
        localStorage.removeItem('user_groq_api_key');
      }

      localStorage.setItem('user_use_nvenc', JSON.stringify(useNvenc));
      localStorage.setItem('user_storage_type', storageType);
      localStorage.setItem('user_resolution', resolution);

      setTimeout(() => {
        setIsSaving(false);
        setSavedSuccess(true);
        setTimeout(() => setSavedSuccess(false), 2500);
      }, 350);
    } catch (err: any) {
      setErrorMsg('Failed to save settings to local storage.');
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-4xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-8 border-b border-border mb-10">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-accent mb-1 font-semibold">
            <SettingsIcon className="w-4 h-4" />
            <span>SYSTEM CONFIGURATION</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-foreground tracking-tight">
            Settings &amp; Infrastructure
          </h1>
          <p className="text-sm text-muted mt-1">
            Hardware acceleration, API credentials, and output storage preferences.
          </p>
        </div>

        <button
          onClick={handleSaveSettings}
          disabled={isSaving}
          className={`flex items-center space-x-2 px-6 py-3 rounded-xl text-sm font-bold shadow-accent-glow btn-spell disabled:opacity-50 transition-all duration-200 ${
            savedSuccess
              ? 'bg-emerald-600 text-white shadow-radar-glow'
              : 'bg-accent hover:bg-accent-hover text-white'
          }`}
        >
          {isSaving ? (
            <span className="flex items-center space-x-2">
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              <span>Saving...</span>
            </span>
          ) : savedSuccess ? (
            <>
              <Check className="w-4 h-4 text-white animate-bounce" />
              <span className="text-white">Settings Saved</span>
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              <span>Save Settings</span>
            </>
          )}
        </button>
      </div>

      {errorMsg && (
        <div className="mb-8">
          <ErrorAlert message={errorMsg} onRetry={() => setErrorMsg(null)} />
        </div>
      )}

      <form onSubmit={handleSaveSettings} className="space-y-8">
        {/* Backend Probed Capabilities Box */}
        <div className="bg-surface border border-border rounded-2xl p-6 shadow-card-glow">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2 text-sm font-bold text-foreground">
              <Activity className="w-4 h-4 text-emerald-400" />
              <span>Probed System Capabilities (/health)</span>
            </div>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold">
              OPERATIONAL
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-3 rounded-xl bg-surfaceElevated border border-border flex items-center justify-between">
              <span className="text-muted">FFmpeg:</span>
              <span className={capabilities.ffmpeg ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
                {capabilities.ffmpeg ? 'READY' : 'UNAVAILABLE'}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-surfaceElevated border border-border flex items-center justify-between">
              <span className="text-muted">FFprobe:</span>
              <span className={capabilities.ffprobe ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
                {capabilities.ffprobe ? 'READY' : 'UNAVAILABLE'}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-surfaceElevated border border-border flex items-center justify-between">
              <span className="text-muted">NVENC GPU:</span>
              <span className={capabilities.gpu_nvenc ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
                {capabilities.gpu_nvenc ? 'DETECTED' : 'CPU FALLBACK'}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-surfaceElevated border border-border flex items-center justify-between">
              <span className="text-muted">Face Tracking:</span>
              <span className={capabilities.face_tracking ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
                {capabilities.face_tracking ? 'ACTIVE' : 'UNAVAILABLE'}
              </span>
            </div>
          </div>
        </div>

        {/* API Credentials */}
        <div className="bg-surface border border-border rounded-2xl p-6 shadow-card-glow space-y-4">
          <div className="flex items-center space-x-2 text-sm font-bold text-foreground">
            <Key className="w-4 h-4 text-accent" />
            <span>LLM &amp; Whisper API Configuration</span>
          </div>

          <div>
            <label className="block text-xs font-mono text-muted mb-2">
              Groq API Key (Optional Client Override)
            </label>
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={groqKey}
                onChange={(e) => setGroqKey(e.target.value)}
                placeholder="Enter Groq API Key..."
                autoComplete="off"
                className="w-full bg-surfaceElevated border border-border rounded-xl px-4 py-2.5 text-xs font-mono text-foreground focus:outline-none focus:border-accent"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                aria-label={showKey ? 'Hide API key' : 'Show API key'}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-foreground"
              >
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-[11px] text-muted mt-2">
              Keys are stored in your local browser session only and never exposed in logs or URLs.
            </p>
          </div>
        </div>

        {/* Render Engine & Acceleration */}
        <div className="bg-surface border border-border rounded-2xl p-6 shadow-card-glow space-y-6">
          <div className="flex items-center space-x-2 text-sm font-bold text-foreground">
            <Cpu className="w-4 h-4 text-accent" />
            <span>Encoding Parameters</span>
          </div>

          <div className="space-y-4">
            <label className="flex items-center justify-between p-4 rounded-xl bg-surfaceElevated border border-border cursor-pointer">
              <div>
                <p className="text-sm font-semibold text-foreground">
                  NVIDIA NVENC Hardware Encoding
                </p>
                <p className="text-xs text-muted">
                  Uses h264_nvenc encoder when supported GPU hardware is detected.
                </p>
              </div>
              <input
                type="checkbox"
                checked={useNvenc}
                onChange={(e) => setUseNvenc(e.target.checked)}
                className="w-4 h-4 accent-accent rounded"
              />
            </label>

            <div>
              <label className="block text-xs font-mono text-muted mb-2">
                Output Canvas Resolution
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setResolution('1080x1920')}
                  className={`py-2.5 px-4 rounded-xl text-xs font-semibold border transition ${
                    resolution === '1080x1920'
                      ? 'bg-accent/15 border-accent text-accent'
                      : 'bg-surfaceElevated border-border text-muted hover:text-foreground'
                  }`}
                >
                  1080 x 1920 (9:16 Full HD)
                </button>
                <button
                  type="button"
                  onClick={() => setResolution('720x1280')}
                  className={`py-2.5 px-4 rounded-xl text-xs font-semibold border transition ${
                    resolution === '720x1280'
                      ? 'bg-accent/15 border-accent text-accent'
                      : 'bg-surfaceElevated border-border text-muted hover:text-foreground'
                  }`}
                >
                  720 x 1280 (9:16 HD Draft)
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Media Storage Backend */}
        <div className="bg-surface border border-border rounded-2xl p-6 shadow-card-glow space-y-4">
          <div className="flex items-center space-x-2 text-sm font-bold text-foreground">
            <HardDrive className="w-4 h-4 text-accent" />
            <span>Clip Storage Backend</span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setStorageType('local')}
              className={`p-3 rounded-xl border text-left transition ${
                storageType === 'local'
                  ? 'bg-accent/15 border-accent text-accent'
                  : 'bg-surfaceElevated border-border text-muted'
              }`}
            >
              <p className="text-xs font-bold text-foreground">Local Filesystem</p>
              <p className="text-[11px] text-muted">temp_media &amp; output_clips folders</p>
            </button>

            <button
              type="button"
              onClick={() => setStorageType('r2')}
              className={`p-3 rounded-xl border text-left transition ${
                storageType === 'r2'
                  ? 'bg-accent/15 border-accent text-accent'
                  : 'bg-surfaceElevated border-border text-muted'
              }`}
            >
              <p className="text-xs font-bold text-foreground">Cloudflare R2 Bucket</p>
              <p className="text-[11px] text-muted">S3-compatible object storage</p>
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
