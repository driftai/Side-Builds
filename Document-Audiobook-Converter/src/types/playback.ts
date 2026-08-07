import type React from 'react';

/**
 * Reader lifecycle shared by the engine and its controls.
 *
 * This lives outside the engine hook so presentational components do not need
 * to depend on the hook's implementation module just to describe UI state.
 */
export enum AppState {
    IDLE,
    PROCESSING,
    READY,
    PLAYING,
    PAUSED,
    ERROR,
}

export type VoiceMode = 'browser' | 'gemini';

export interface PlaybackControlHandlers {
    onPlay: () => void;
    onPause: () => void;
    onStop: () => void;
    onSkipForward: () => void;
    onSkipBackward: () => void;
}

export interface PlaybackPosition {
    appState: AppState;
    currentSentenceIndex: number;
    totalSentences: number;
}

export type SentenceIndexSetter = React.Dispatch<React.SetStateAction<number>>;
