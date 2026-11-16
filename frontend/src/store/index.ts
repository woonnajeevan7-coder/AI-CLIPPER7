/**
 * AI Clipper Pro - Global Application Store
 * Implemented using Zustand with TypeScript and subscribeWithSelector middleware.
 */

import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

export interface RubricDetails {
  hook_strength: number;
  self_contained: number;
  payoff: number;
  zero_context_needed: number;
  critique: string;
}

export interface ClipData {
  id: string;
  project_id?: string;
  title: string;
  headline: string;
  start_seconds: number;
  end_seconds: number;
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

export interface BrandKitState {
  primaryColor: string;
  secondaryColor: string;
  fontFamily: string;
  captionPreset: string;
  watermarkText: string;
  watermarkPosition: string;
  outroCtaEnabled: boolean;
  outroText: string;
}

export interface AppState {
  activeProjectId: string | null;
  activeJobId: string | null;
  projectTitle: string;
  clips: ClipData[];
  selectedClipId: string | null;
  brandKit: BrandKitState;
  pipelineProgress: number;
  pipelineLogs: string[];
  isPipelineRunning: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface AppActions {
  setProject: (projectId: string, jobId: string, title?: string) => void;
  setClips: (clips: ClipData[]) => void;
  selectClip: (clipId: string | null) => void;
  updateClipTrim: (clipId: string, newStart: number, newEnd: number) => void;
  updateBrandKit: (kit: Partial<BrandKitState>) => void;
  updatePipelineProgress: (progress: number, log?: string) => void;
  setPipelineRunning: (running: boolean) => void;
  setError: (error: string | null) => void;
  resetProject: () => void;
}

export type AppStore = AppState & AppActions;

const initialBrandKit: BrandKitState = {
  primaryColor: '#8B5CF6',
  secondaryColor: '#EC4899',
  fontFamily: 'Inter',
  captionPreset: 'hormozi',
  watermarkText: '@channel',
  watermarkPosition: 'top_right',
  outroCtaEnabled: true,
  outroText: 'Subscribe for daily breakdowns',
};

export const useAppStore = create<AppStore>()(
  subscribeWithSelector((set, get) => ({
    // State
    activeProjectId: null,
    activeJobId: null,
    projectTitle: '',
    clips: [],
    selectedClipId: null,
    brandKit: initialBrandKit,
    pipelineProgress: 0,
    pipelineLogs: [],
    isPipelineRunning: false,
    isLoading: false,
    error: null,

    // Actions
    setProject: (projectId, jobId, title = 'New Project') =>
      set({
        activeProjectId: projectId,
        activeJobId: jobId,
        projectTitle: title,
        pipelineProgress: 0,
        pipelineLogs: [],
        error: null,
      }),

    setClips: (clips) =>
      set({
        clips,
        selectedClipId: clips.length > 0 ? clips[0].id : null,
      }),

    selectClip: (clipId) =>
      set({ selectedClipId: clipId }),

    updateClipTrim: (clipId, newStart, newEnd) =>
      set((state) => ({
        clips: state.clips.map((c) =>
          c.id === clipId
            ? {
                ...c,
                start_seconds: Number(newStart.toFixed(2)),
                end_seconds: Number(newEnd.toFixed(2)),
                duration: Number((newEnd - newStart).toFixed(2)),
              }
            : c
        ),
      })),

    updateBrandKit: (kitUpdate) =>
      set((state) => ({
        brandKit: { ...state.brandKit, ...kitUpdate },
      })),

    updatePipelineProgress: (progress, log) =>
      set((state) => ({
        pipelineProgress: progress,
        pipelineLogs: log
          ? [...state.pipelineLogs.slice(-40), log]
          : state.pipelineLogs,
      })),

    setPipelineRunning: (running) =>
      set({ isPipelineRunning: running }),

    setError: (error) =>
      set({ error }),

    resetProject: () =>
      set({
        activeProjectId: null,
        activeJobId: null,
        projectTitle: '',
        clips: [],
        selectedClipId: null,
        pipelineProgress: 0,
        pipelineLogs: [],
        isPipelineRunning: false,
        error: null,
      }),
  }))
);
