/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { create } from 'zustand';
import {
  DEFAULT_LIVE_API_MODEL,
  DEFAULT_IMAGE_MODEL,
  PLACEHOLDER_DOC,
  normalizeLiveApiModel,
  normalizeImageModel,
} from '../constants';
import { themes } from '../themes';

export type MainTab =
  | 'document'
  | 'workspace'
  | 'transcript'
  | 'unidex-log'
  | 'minutes'
  | 'audio-log';
export type ScribeMode =
  | 'general'
  | 'research'
  | 'meeting'
  | 'creative'
  | 'legal'
  | 'academic'
  | 'news'
  | 'technical'
  | 'personal';
export type ScribeExportProfile =
  | 'note'
  | 'report'
  | 'memo'
  | 'script'
  | 'study-guide'
  | 'brief';

const _resolveInitialApiKey = (): string => {
  try {
    const stored = localStorage.getItem('scribe_api_key');
    if (stored) return stored;
  } catch { /* localStorage unavailable */ }
  if (typeof process !== 'undefined' && process.env) {
    return (process.env.API_KEY || process.env.GEMINI_API_KEY || '') as string;
  }
  return '';
};

const _resolveInitialImageModel = (): string => {
  try {
    const stored = localStorage.getItem('scribe_image_model');
    if (stored) return normalizeImageModel(stored);
  } catch { /* localStorage unavailable */ }
  return DEFAULT_IMAGE_MODEL;
};

const _resolveInitialImageGenerationEnabled = (): boolean => {
  try {
    return localStorage.getItem('scribe_image_generation_enabled') === 'true';
  } catch { /* localStorage unavailable */ }
  return false;
};

const _resolveInitialLiveApiModel = (): string => {
  try {
    const stored = localStorage.getItem('scribe_live_api_model');
    if (stored) return normalizeLiveApiModel(stored);
  } catch { /* localStorage unavailable */ }
  return DEFAULT_LIVE_API_MODEL;
};

const _resolveInitialAgentVolume = (): number => {
  try {
    const stored = localStorage.getItem('scribe_agent_volume');
    if (stored) {
      const parsed = Number(stored);
      if (Number.isFinite(parsed)) return Math.max(0, Math.min(100, parsed));
    }
  } catch { /* localStorage unavailable */ }
  return 65;
};

const _resolveInitialMicMuted = (): boolean => {
  try {
    return localStorage.getItem('scribe_mic_muted') === 'true';
  } catch { /* localStorage unavailable */ }
  return false;
};

const _resolveInitialScribeMode = (): ScribeMode => {
  try {
    const stored = localStorage.getItem('scribe_mode') as ScribeMode | null;
    if (
      stored &&
      ['general', 'research', 'meeting', 'creative', 'legal', 'academic', 'news', 'technical', 'personal'].includes(stored)
    ) {
      return stored;
    }
  } catch { /* localStorage unavailable */ }
  return 'general';
};

const _resolveInitialExportProfile = (): ScribeExportProfile => {
  try {
    const stored = localStorage.getItem('scribe_export_profile') as ScribeExportProfile | null;
    if (stored && ['note', 'report', 'memo', 'script', 'study-guide', 'brief'].includes(stored)) {
      return stored;
    }
  } catch { /* localStorage unavailable */ }
  return 'note';
};

const _resolveInitialDocumentGoal = (): string => {
  try {
    return localStorage.getItem('scribe_document_goal') || '';
  } catch { /* localStorage unavailable */ }
  return '';
};

const _resolveInitialWorkspaceInstruction = (): string => {
  try {
    return localStorage.getItem('scribe_workspace_instruction') || '';
  } catch { /* localStorage unavailable */ }
  return '';
};

const _resolveInitialTheme = (): string => {
  try {
    const stored = localStorage.getItem('scribe_theme');
    if (stored && themes.some(t => t.name === stored)) return stored;
  } catch { /* localStorage unavailable */ }
  return themes[0].name;
};

export const useUI = create<{
  apiKey: string;
  setApiKey: (key: string) => void;
  imageModel: string;
  setImageModel: (model: string) => void;
  imageGenerationEnabled: boolean;
  setImageGenerationEnabled: (enabled: boolean) => void;
  showWelcomeScreen: boolean;
  setShowWelcomeScreen: (show: boolean) => void;
  showUserConfig: boolean;
  setShowUserConfig: (show: boolean) => void;
  showAgentEdit: boolean;
  setShowAgentEdit: (show: boolean) => void;
  showDebugModal: boolean;
  setShowDebugModal: (show: boolean) => void;
  showHelpModal: boolean;
  setShowHelpModal: (show: boolean) => void;
  showStorageModal: boolean;
  setShowStorageModal: (show: boolean) => void;
  showExportPackageModal: boolean;
  setShowExportPackageModal: (show: boolean) => void;
  theme: string;
  setTheme: (themeName: string) => void;
  font: string;
  setFont: (fontName: string) => void;
  suppressRedundantLogs: boolean;
  setSuppressRedundantLogs: (suppress: boolean) => void;
  suppressStaleAgentResponses: boolean;
  setSuppressStaleAgentResponses: (suppress: boolean) => void;
  suppressPostFlushAudio: boolean;
  setSuppressPostFlushAudio: (suppress: boolean) => void;
  changeCount: number;
  incrementChangeCount: () => void;
  agentState: string | null;
  setAgentState: (state: string | null) => void;
  mainTab: MainTab;
  setMainTab: (tab: MainTab) => void;
  documentTab: 'editor' | 'rendered';
  setDocumentTab: (tab: 'editor' | 'rendered') => void;
  speechBubbleText: string | null;
  setSpeechBubbleText: (text: string | null) => void;
  documentContent: string;
  setDocumentContent: (content: string | ((prev: string) => string)) => void;
  outputModality: 'audio' | 'text' | 'both';
  setOutputModality: (modality: 'audio' | 'text' | 'both') => void;
  agentVolume: number;
  setAgentVolume: (volume: number) => void;
  micMuted: boolean;
  setMicMuted: (muted: boolean) => void;
  useSearch: boolean;
  setUseSearch: (useSearch: boolean) => void;
  liveApiModel: string;
  setLiveApiModel: (model: string) => void;
  scribeMode: ScribeMode;
  setScribeMode: (mode: ScribeMode) => void;
  exportProfile: ScribeExportProfile;
  setExportProfile: (profile: ScribeExportProfile) => void;
  documentGoal: string;
  setDocumentGoal: (goal: string) => void;
  workspaceInstruction: string;
  setWorkspaceInstruction: (instruction: string) => void;
  pendingSourceFocus: string | null;
  setPendingSourceFocus: (id: string | null) => void;
}>(set => ({
  apiKey: _resolveInitialApiKey(),
  setApiKey: (key: string) => {
    try { localStorage.setItem('scribe_api_key', key); } catch { /* noop */ }
    set({ apiKey: key });
  },
  imageModel: _resolveInitialImageModel(),
  setImageModel: (model: string) => {
    const normalizedModel = normalizeImageModel(model);
    try { localStorage.setItem('scribe_image_model', normalizedModel); } catch { /* noop */ }
    set({ imageModel: normalizedModel });
  },
  imageGenerationEnabled: _resolveInitialImageGenerationEnabled(),
  setImageGenerationEnabled: (enabled: boolean) => {
    try { localStorage.setItem('scribe_image_generation_enabled', String(enabled)); } catch { /* noop */ }
    set({ imageGenerationEnabled: enabled });
  },
  showWelcomeScreen: true,
  setShowWelcomeScreen: (show: boolean) => set({ showWelcomeScreen: show }),
  showUserConfig: false,
  setShowUserConfig: (show: boolean) => set({ showUserConfig: show }),
  showAgentEdit: false,
  setShowAgentEdit: (show: boolean) => set({ showAgentEdit: show }),
  showDebugModal: false,
  setShowDebugModal: (show: boolean) => set({ showDebugModal: show }),
  showHelpModal: false,
  setShowHelpModal: (show: boolean) => set({ showHelpModal: show }),
  showStorageModal: false,
  setShowStorageModal: (show: boolean) => set({ showStorageModal: show }),
  showExportPackageModal: false,
  setShowExportPackageModal: (show: boolean) => set({ showExportPackageModal: show }),
  theme: _resolveInitialTheme(),
  setTheme: (themeName: string) => {
    try { localStorage.setItem('scribe_theme', themeName); } catch { /* noop */ }
    set({ theme: themeName });
  },
  font: 'Arial',
  setFont: (fontName: string) => set({ font: fontName }),
  suppressRedundantLogs: false,
  setSuppressRedundantLogs: (suppress: boolean) =>
    set({ suppressRedundantLogs: suppress }),
  suppressStaleAgentResponses: false,
  setSuppressStaleAgentResponses: (suppress: boolean) =>
    set({ suppressStaleAgentResponses: suppress }),
  suppressPostFlushAudio: true,
  setSuppressPostFlushAudio: (suppress: boolean) =>
    set({ suppressPostFlushAudio: suppress }),
  changeCount: 0,
  incrementChangeCount: () =>
    set(state => ({ changeCount: state.changeCount + 1 })),
  agentState: null,
  setAgentState: (state: string | null) => set({ agentState: state }),
  mainTab: 'document',
  setMainTab: (tab: MainTab) => set({ mainTab: tab }),
  documentTab: 'rendered',
  setDocumentTab: (tab: 'editor' | 'rendered') => set({ documentTab: tab }),
  speechBubbleText: null,
  setSpeechBubbleText: (text: string | null) => set({ speechBubbleText: text }),
  documentContent: PLACEHOLDER_DOC,
  setDocumentContent: (content: string | ((prev: string) => string)) =>
    set(state => ({
      documentContent:
        typeof content === 'function' ? content(state.documentContent) : content,
    })),
  outputModality: 'audio',
  setOutputModality: (modality: 'audio' | 'text' | 'both') => set({ outputModality: modality }),
  agentVolume: _resolveInitialAgentVolume(),
  setAgentVolume: (volume: number) => {
    const nextVolume = Math.max(0, Math.min(100, volume));
    try { localStorage.setItem('scribe_agent_volume', String(nextVolume)); } catch { /* noop */ }
    set({ agentVolume: nextVolume });
  },
  micMuted: _resolveInitialMicMuted(),
  setMicMuted: (muted: boolean) => {
    try { localStorage.setItem('scribe_mic_muted', String(muted)); } catch { /* noop */ }
    set({ micMuted: muted });
  },
  useSearch: false,
  setUseSearch: (useSearch: boolean) => set({ useSearch }),
  liveApiModel: _resolveInitialLiveApiModel(),
  setLiveApiModel: (model: string) => {
    const normalizedModel = normalizeLiveApiModel(model);
    try { localStorage.setItem('scribe_live_api_model', normalizedModel); } catch { /* noop */ }
    set({ liveApiModel: normalizedModel });
  },
  scribeMode: _resolveInitialScribeMode(),
  setScribeMode: (mode: ScribeMode) => {
    try { localStorage.setItem('scribe_mode', mode); } catch { /* noop */ }
    set({ scribeMode: mode });
  },
  exportProfile: _resolveInitialExportProfile(),
  setExportProfile: (profile: ScribeExportProfile) => {
    try { localStorage.setItem('scribe_export_profile', profile); } catch { /* noop */ }
    set({ exportProfile: profile });
  },
  documentGoal: _resolveInitialDocumentGoal(),
  setDocumentGoal: (goal: string) => {
    try { localStorage.setItem('scribe_document_goal', goal); } catch { /* noop */ }
    set({ documentGoal: goal });
  },
  workspaceInstruction: _resolveInitialWorkspaceInstruction(),
  setWorkspaceInstruction: (instruction: string) => {
    try { localStorage.setItem('scribe_workspace_instruction', instruction); } catch { /* noop */ }
    set({ workspaceInstruction: instruction });
  },
  // Transient — set when a citation chip is clicked, consumed by WorkspaceView
  // which scrolls to and highlights the matching source card, then clears it.
  pendingSourceFocus: null,
  setPendingSourceFocus: (id: string | null) => set({ pendingSourceFocus: id }),
}));
