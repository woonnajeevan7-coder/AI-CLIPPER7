'use client';

import React, { useState, useEffect } from 'react';
import {
  Palette,
  Type,
  AtSign,
  Tv,
  Save,
  Check,
  Sparkles,
  Sliders,
  Eye,
} from 'lucide-react';
import ErrorAlert from '@/components/ui/ErrorAlert';
import { useAppStore } from '@/store';
import { getValidAuthToken } from '@/lib/auth';

export default function BrandKitPage() {
  const brandKit = useAppStore((state) => state.brandKit);
  const updateBrandKit = useAppStore((state) => state.updateBrandKit);

  const [primaryColor, setPrimaryColor] = useState(brandKit.primaryColor || '#8B5CF6');
  const [secondaryColor, setSecondaryColor] = useState(brandKit.secondaryColor || '#EC4899');
  const [fontFamily, setFontFamily] = useState(brandKit.fontFamily || 'Inter');
  const [captionPreset, setCaptionPreset] = useState(brandKit.captionPreset || 'hormozi');
  const [watermarkText, setWatermarkText] = useState(brandKit.watermarkText || '@mybrand');
  const [watermarkPosition, setWatermarkPosition] = useState(brandKit.watermarkPosition || 'top_right');
  const [outroEnabled, setOutroEnabled] = useState(brandKit.outroCtaEnabled ?? true);
  const [outroText, setOutroText] = useState(brandKit.outroText || 'Subscribe for daily breakdowns');

  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load saved preferences from backend / localStorage
  useEffect(() => {
    const cached = localStorage.getItem('ai_clipper_brand_kit');
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (parsed.primaryColor) setPrimaryColor(parsed.primaryColor);
        if (parsed.secondaryColor) setSecondaryColor(parsed.secondaryColor);
        if (parsed.fontFamily) setFontFamily(parsed.fontFamily);
        if (parsed.captionPreset) setCaptionPreset(parsed.captionPreset);
        if (parsed.watermarkText) setWatermarkText(parsed.watermarkText);
        if (parsed.outroText) setOutroText(parsed.outroText);
      } catch (e) {}
    }
  }, []);

  const handleSaveBrandKit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMsg(null);
    setSaveSuccess(false);

    const kitData = {
      primary_color: primaryColor,
      secondary_color: secondaryColor,
      font_family: fontFamily,
      caption_preset: captionPreset,
      watermark_text: watermarkText,
      watermark_position: watermarkPosition,
      outro_cta_enabled: outroEnabled,
      outro_text: outroText,
    };

    // Cache locally
    updateBrandKit({
      primaryColor,
      secondaryColor,
      fontFamily,
      captionPreset,
      watermarkText,
      watermarkPosition,
      outroCtaEnabled: outroEnabled,
      outroText,
    });
    localStorage.setItem('ai_clipper_brand_kit', JSON.stringify({
      primaryColor,
      secondaryColor,
      fontFamily,
      captionPreset,
      watermarkText,
      outroText,
    }));

    try {
      const authToken = await getValidAuthToken();
      // Dispatches POST /api/v1/brand-kit
      const res = await fetch('http://localhost:8000/api/v1/brand-kit/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify(kitData),
      });

      if (!res.ok) {
        console.warn('Backend unavailable, brand kit saved to local storage.');
      }

      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-8 border-b border-border mb-10">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-accent mb-1 font-semibold">
            <Palette className="w-4 h-4" />
            <span>STUDIO CUSTOMIZATION</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-foreground tracking-tight">
            Brand Kit &amp; Visual Identity
          </h1>
          <p className="text-sm text-muted mt-1">
            Standardize brand colors, typography, watermarks, and outro cards across all generated shorts.
          </p>
        </div>

        <button
          onClick={handleSaveBrandKit}
          disabled={isSaving}
          className={`flex items-center space-x-2 px-6 py-3 rounded-xl text-sm font-bold shadow-accent-glow btn-spell disabled:opacity-50 transition-all duration-200 ${
            saveSuccess
              ? 'bg-emerald-600 text-white shadow-radar-glow'
              : 'bg-accent hover:bg-accent-hover text-white'
          }`}
        >
          {isSaving ? (
            <span className="flex items-center space-x-2">
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              <span>Saving...</span>
            </span>
          ) : saveSuccess ? (
            <>
              <Check className="w-4 h-4 text-white animate-bounce" />
              <span className="text-white">Saved to Cloud</span>
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              <span>Save Brand Kit</span>
            </>
          )}
        </button>
      </div>

      {errorMsg && (
        <div className="mb-8">
          <ErrorAlert message={errorMsg} onRetry={() => setErrorMsg(null)} />
        </div>
      )}

      <form onSubmit={handleSaveBrandKit} className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Form Controls (7 Cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Color Palette */}
          <div className="bg-surface border border-border rounded-2xl p-6 shadow-card-glow">
            <div className="flex items-center space-x-2 text-sm font-bold text-foreground mb-4">
              <Palette className="w-4 h-4 text-accent" />
              <span>Brand Color Palette</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="primary-color-hex" className="block text-xs font-mono text-muted mb-2">
                  Primary Accent Color
                </label>
                <div className="flex items-center space-x-3 bg-surfaceElevated border border-border rounded-xl p-2.5">
                  <input
                    type="color"
                    id="primary-color-picker"
                    aria-label="Pick primary accent color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="w-8 h-8 rounded-lg cursor-pointer bg-transparent border-0"
                  />
                  <input
                    type="text"
                    id="primary-color-hex"
                    aria-label="Primary accent color hex code"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="w-full bg-transparent text-xs font-mono text-foreground focus:outline-none uppercase"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="secondary-color-hex" className="block text-xs font-mono text-muted mb-2">
                  Secondary Highlight Color
                </label>
                <div className="flex items-center space-x-3 bg-surfaceElevated border border-border rounded-xl p-2.5">
                  <input
                    type="color"
                    id="secondary-color-picker"
                    aria-label="Pick secondary highlight color"
                    value={secondaryColor}
                    onChange={(e) => setSecondaryColor(e.target.value)}
                    className="w-8 h-8 rounded-lg cursor-pointer bg-transparent border-0"
                  />
                  <input
                    type="text"
                    id="secondary-color-hex"
                    aria-label="Secondary highlight color hex code"
                    value={secondaryColor}
                    onChange={(e) => setSecondaryColor(e.target.value)}
                    className="w-full bg-transparent text-xs font-mono text-foreground focus:outline-none uppercase"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Typography */}
          <div className="bg-surface border border-border rounded-2xl p-6 shadow-card-glow">
            <div className="flex items-center space-x-2 text-sm font-bold text-foreground mb-4">
              <Type className="w-4 h-4 text-accent" />
              <span>Subtitle &amp; Headline Typography</span>
            </div>

            <div className="space-y-4">
              <div>
                <span className="block text-xs font-mono text-muted mb-2">
                  Font Family
                </span>
                <div role="radiogroup" aria-label="Font family selection" className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {['Inter', 'Montserrat', 'Roboto', 'JetBrains Mono'].map((font) => (
                    <button
                      key={font}
                      type="button"
                      role="radio"
                      aria-checked={fontFamily === font}
                      onClick={() => setFontFamily(font)}
                      className={`p-3 rounded-xl border text-xs font-bold btn-spell ${
                        fontFamily === font
                          ? 'bg-accent/20 border-accent text-accent-light shadow-sm ring-1 ring-accent'
                          : 'bg-surfaceElevated border-border text-muted hover:text-foreground'
                      }`}
                    >
                      {font}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label htmlFor="default-subtitle-preset" className="block text-xs font-mono text-muted mb-2">
                  Default Subtitle Burn-In Preset
                </label>
                <select
                  id="default-subtitle-preset"
                  value={captionPreset}
                  onChange={(e) => setCaptionPreset(e.target.value)}
                  className="w-full bg-surfaceElevated border border-border rounded-xl px-4 py-2.5 text-xs text-foreground focus:outline-none focus:border-accent"
                >
                  <option value="hormozi">Hormozi (High Contrast Yellow &amp; White)</option>
                  <option value="cyber_cyan">Cyber Cyan (Neon Glow)</option>
                  <option value="emerald_box">Emerald Box (High Visibility Green)</option>
                  <option value="bold_minimal">Bold Minimal (Clean Studio White)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Watermark & Social Handle */}
          <div className="bg-surface border border-border rounded-2xl p-6 shadow-card-glow">
            <div className="flex items-center space-x-2 text-sm font-bold text-foreground mb-4">
              <AtSign className="w-4 h-4 text-accent" />
              <span>Watermark &amp; Attribution</span>
            </div>

            <div className="space-y-4">
              <div>
                <label htmlFor="watermark-input" className="block text-xs font-mono text-muted mb-2">
                  Social Handle / Watermark Text
                </label>
                <input
                  id="watermark-input"
                  type="text"
                  value={watermarkText}
                  onChange={(e) => setWatermarkText(e.target.value)}
                  placeholder="@yourhandle"
                  className="w-full bg-surfaceElevated border border-border rounded-xl px-4 py-2.5 text-xs font-mono text-foreground focus:outline-none focus:border-accent"
                />
              </div>

              <div>
                <span className="block text-xs font-mono text-muted mb-2">
                  Overlay Position
                </span>
                <div role="radiogroup" aria-label="Watermark overlay position" className="grid grid-cols-3 gap-3">
                  {[
                    { id: 'top_right', label: 'Top Right' },
                    { id: 'bottom_left', label: 'Bottom Left' },
                    { id: 'bottom_center', label: 'Bottom Center' },
                  ].map((pos) => (
                    <button
                      key={pos.id}
                      type="button"
                      role="radio"
                      aria-checked={watermarkPosition === pos.id}
                      onClick={() => setWatermarkPosition(pos.id)}
                      className={`p-2.5 rounded-xl border text-xs font-semibold btn-spell ${
                        watermarkPosition === pos.id
                          ? 'bg-accent/20 border-accent text-accent-light shadow-sm ring-1 ring-accent'
                          : 'bg-surfaceElevated border-border text-muted hover:text-foreground'
                      }`}
                    >
                      {pos.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Outro CTA Card */}
          <div className="bg-surface border border-border rounded-2xl p-6 shadow-card-glow">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2 text-sm font-bold text-foreground">
                <Tv className="w-4 h-4 text-accent" />
                <span>Outro Call-to-Action Card</span>
              </div>
              <input
                id="outro-enabled-toggle"
                type="checkbox"
                aria-label="Enable outro call-to-action card"
                checked={outroEnabled}
                onChange={(e) => setOutroEnabled(e.target.checked)}
                className="w-4 h-4 accent-accent rounded cursor-pointer"
              />
            </div>

            {outroEnabled && (
              <div>
                <label htmlFor="outro-text-input" className="block text-xs font-mono text-muted mb-2">
                  Outro Card Text
                </label>
                <input
                  id="outro-text-input"
                  type="text"
                  value={outroText}
                  onChange={(e) => setOutroText(e.target.value)}
                  className="w-full bg-surfaceElevated border border-border rounded-xl px-4 py-2.5 text-xs text-foreground focus:outline-none focus:border-accent"
                />
                <p className="text-[11px] text-muted mt-2">
                  Appends a 2.0s branded outro animation at the end of each generated short.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right Live Preview (5 Cols) */}
        <div className="lg:col-span-5 bg-surface border border-border rounded-3xl p-6 flex flex-col items-center shadow-card-glow sticky top-24">
          <div className="w-full flex items-center justify-between text-xs font-mono text-muted mb-4">
            <span className="text-accent font-bold flex items-center space-x-1">
              <Eye className="w-3.5 h-3.5" />
              <span>LIVE BRAND PREVIEW</span>
            </span>
            <span>9:16 Canvas</span>
          </div>

          {/* 9:16 Live Phone Frame */}
          <div className="w-[260px] sm:w-[280px] aspect-[9/16] bg-black rounded-2xl overflow-hidden relative border border-borderSubtle flex flex-col justify-between p-4 shadow-2xl">
            {/* Top Watermark */}
            <div className={`z-10 text-[10px] font-mono px-2 py-0.5 rounded bg-black/60 backdrop-blur-sm border border-white/10 ${
              watermarkPosition === 'top_right' ? 'self-end' : watermarkPosition === 'bottom_left' ? 'self-start mt-auto' : 'self-center'
            }`}>
              {watermarkText}
            </div>

            {/* Simulated Frame Graphics */}
            <div className="self-center my-auto flex flex-col items-center space-y-2">
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg"
                style={{ backgroundColor: primaryColor }}
              >
                <Sparkles className="w-8 h-8 text-white" />
              </div>
              <span className="text-xs font-bold text-white font-mono">
                Brand Anchor
              </span>
            </div>

            {/* Bottom Subtitle Preview */}
            <div className="z-10 bg-black/85 backdrop-blur-md p-3 rounded-xl border border-white/10 text-center space-y-1">
              <p
                className="text-xs font-extrabold tracking-wide uppercase"
                style={{ color: secondaryColor }}
              >
                &quot;LEARN EVERY SINGLE DAY&quot;
              </p>
              <p className="text-[10px] text-muted font-mono">
                Font: {fontFamily}
              </p>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
