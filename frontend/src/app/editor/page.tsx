'use client';

import React, { useState } from 'react';

export default function TranscriptEditorPage() {
  const [headline, setHeadline] = useState('WHY 99% FAIL AT CODING');
  const [captionPreset, setCaptionPreset] = useState('hormozi');
  const [words, setWords] = useState([
    { id: 1, text: 'Hey', deleted: false },
    { id: 2, text: 'everyone,', deleted: false },
    { id: 3, text: 'here', deleted: false },
    { id: 4, text: 'is', deleted: false },
    { id: 5, text: 'the', deleted: false },
    { id: 6, text: 'biggest', deleted: false },
    { id: 7, text: 'secret', deleted: false },
    { id: 8, text: 'to', deleted: false },
    { id: 9, text: 'coding', deleted: false },
    { id: 10, text: 'faster', deleted: false },
    { id: 11, text: 'in', deleted: false },
    { id: 12, text: '2026.', deleted: false },
  ]);

  const toggleWord = (id: number) => {
    setWords(words.map((w) => (w.id === id ? { ...w, deleted: !w.deleted } : w)));
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <header className="border-b border-slate-800 px-8 py-4 flex items-center justify-between">
        <a href="/" className="text-xl font-black bg-gradient-to-r from-amber-400 to-purple-600 bg-clip-text text-transparent">
          ← Back to Studio
        </a>
        <span className="text-sm font-semibold text-slate-400">Transcript-Based Video Editor</span>
      </header>

      <main className="flex-1 max-w-6xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {/* Left: Video Preview */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col items-center">
          <div className="w-[300px] h-[533px] bg-black rounded-xl overflow-hidden relative border border-slate-800 shadow-2xl flex flex-col items-center justify-between p-6">
            <div className="bg-black/80 text-white font-extrabold text-sm px-3 py-1.5 rounded-lg border border-white/20 text-center">
              {headline}
            </div>
            <div className="text-center font-black text-xl text-yellow-400 drop-shadow-md">
              BIGGEST SECRET
            </div>
            <div className="text-xs text-slate-500">1080x1920 · 9:16 Preview</div>
          </div>
        </div>

        {/* Right: Word-level Trimming Controls */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
          <div>
            <label htmlFor="headline-input" className="block text-xl font-bold mb-2">
              Headline Banner
            </label>
            <input
              id="headline-input"
              type="text"
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div>
            <label htmlFor="caption-preset-select" className="block text-xl font-bold mb-2">
              Caption Preset
            </label>
            <select
              id="caption-preset-select"
              value={captionPreset}
              onChange={(e) => setCaptionPreset(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="hormozi">Hormozi (High Contrast Yellow/White)</option>
              <option value="cyber_cyan">Cyber Cyan (Neon Accent)</option>
              <option value="emerald_box">Emerald Box (Spring Green)</option>
            </select>
          </div>

          <div>
            <h2 className="text-xl font-bold mb-1">Transcript Word Trimmer</h2>
            <p className="text-xs text-slate-400 mb-3">
              Click any word to delete or restore it. Boundaries re-render instantly without dead air.
            </p>
            <div className="flex flex-wrap gap-2 p-4 bg-slate-950 rounded-xl border border-slate-800" role="group" aria-label="Transcript words to toggle">
              {words.map((w) => (
                <button
                  key={w.id}
                  onClick={() => toggleWord(w.id)}
                  aria-pressed={!w.deleted}
                  aria-label={`${w.text} (${w.deleted ? 'deleted, click to restore' : 'active, click to omit'})`}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-bold transition min-h-[36px] focus-visible:ring-2 focus-visible:ring-purple-400 ${
                    w.deleted
                      ? 'bg-red-950/60 text-red-400 line-through border border-red-800/40'
                      : 'bg-white hover:bg-slate-100 text-black border border-slate-200 shadow-sm'
                  }`}
                >
                  {w.text}
                </button>
              ))}
            </div>
          </div>

          <button className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold py-3.5 rounded-xl shadow-lg transition focus-visible:ring-2 focus-visible:ring-purple-400 min-h-[48px]">
            ⚡ Re-Render Short with New Timestamps
          </button>
        </div>
      </main>
    </div>
  );
}
