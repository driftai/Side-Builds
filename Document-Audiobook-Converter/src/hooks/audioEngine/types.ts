import type React from 'react';
import type { NarrationResult } from '../../types/gemini';
import { AppState, type SentenceIndexSetter, type VoiceMode } from '../../types/playback';

export const PCM_SAMPLE_RATE = 24000;
export const PREFETCH_DEPTH = 4;

export type GenerateAudioForSentence = (
    text: string,
    signal?: AbortSignal,
    onChunk?: (pcm: ArrayBuffer) => void,
    priority?: number,
) => Promise<NarrationResult>;

export interface StreamRecord {
    chunks: ArrayBuffer[];
    done: boolean;
    listeners: Set<(pcm: ArrayBuffer | null) => void>;
}

export interface PrefetchEntry {
    promise: Promise<AudioBuffer>;
    controller: AbortController;
    text: string;
    settled?: boolean;
    keepToCompletion?: boolean;
    stream?: StreamRecord;
}

export interface AudioState {
    appState: AppState;
    setAppState: (state: AppState) => void;
    currentSentenceIndex: number;
    setCurrentSentenceIndex: SentenceIndexSetter;
    sentencesRef: React.MutableRefObject<string[]>;
    handlePlay: () => void;
    handlePause: () => void;
    handleStop: () => void;
    handleSkipForward: () => void;
    handleSkipBackward: () => void;
    error: string | null;
    setError: (error: string | null) => void;
    smoothPlayback: boolean;
    setSmoothPlayback: (smooth: boolean) => void;
    voiceMode: VoiceMode;
    setVoiceMode: React.Dispatch<React.SetStateAction<VoiceMode>>;
    selectedVoiceURI: string | null;
    setSelectedVoiceURI: (uri: string | null) => void;
    selectedGeminiVoice: string;
    setSelectedGeminiVoice: (voice: string) => void;
    voices: SpeechSynthesisVoice[];
    spokenCharIndex: number | null;
    applySentenceUpdate: (next: string[], oldToNew: (number | null)[]) => void;
}
