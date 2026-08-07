import { AppState } from '../../types/playback';
import type { PlaybackSeekMode } from './types';

interface PlaybackSeekOptions {
    targetIndex: number;
    sentenceCount: number;
    mode: PlaybackSeekMode;
    currentState: AppState;
    /** Invalidates async work and stops every active output before position changes. */
    stopPlayback: () => void;
    /** These setters update their corresponding refs before scheduling React state. */
    syncIndex: (index: number) => void;
    syncState: (state: AppState) => void;
    restartPlaybackEffect: () => void;
}

/**
 * Atomically move playback to another passage.
 *
 * All jump sources use this ordering so an abandoned async generation cannot
 * observe the new index while still holding an old playback epoch.
 */
export const performPlaybackSeek = ({
    targetIndex,
    sentenceCount,
    mode,
    currentState,
    stopPlayback,
    syncIndex,
    syncState,
    restartPlaybackEffect,
}: PlaybackSeekOptions): boolean => {
    if (targetIndex < 0 || targetIndex >= sentenceCount) return false;

    stopPlayback();
    syncIndex(targetIndex);

    const shouldPlay = mode === 'play' || currentState === AppState.PLAYING;
    if (shouldPlay) {
        syncState(AppState.PLAYING);
        // Also restarts a passage when its already-selected index is clicked.
        restartPlaybackEffect();
    }
    return true;
};
