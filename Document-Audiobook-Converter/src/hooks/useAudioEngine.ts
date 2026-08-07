import { useCallback, useEffect, useMemo, useRef, useState, type SetStateAction } from 'react';
import type { GeminiApiConfig } from '../types/gemini';
import { AppState, type VoiceMode } from '../types/playback';
import { remapIndex } from '../utils/documentDiff';
import { speakWithPersistentVoice } from './audioEngine/browserSpeech';
import { getNarrationIdentity } from './audioEngine/narrationIdentity';
import { performPlaybackSeek } from './audioEngine/playbackSeek';
import type {
    AudioState,
    GenerateAudioForSentence,
    PlaybackSeekMode,
} from './audioEngine/types';
import { useGeminiPlayback } from './audioEngine/useGeminiPlayback';

// Preserve the hook's original public surface for existing callers.
export { AppState } from '../types/playback';

export const useAudioEngine = (
    geminiConfig: GeminiApiConfig | null,
    generateAudioForSentence: GenerateAudioForSentence,
    documentId: string | null = null,
    documentName: string = '',
): AudioState => {
    const [appState, setAppStateValue] = useState<AppState>(AppState.IDLE);
    const [currentSentenceIndex, setCurrentSentenceIndexValue] = useState(-1);
    const [error, setError] = useState<string | null>(null);
    const [smoothPlayback, setSmoothPlayback] = useState(true);
    const [voiceMode, setVoiceMode] = useState<VoiceMode>('browser');
    const [selectedVoiceURI, setSelectedVoiceURI] = useState<string | null>(() => {
        try { return localStorage.getItem('selectedVoiceURI'); } catch { return null; }
    });
    const [selectedGeminiVoice, setSelectedGeminiVoice] = useState(() => {
        try {
            const saved = localStorage.getItem('geminiAudiobookConfig');
            const voice = saved ? JSON.parse(saved).voice : null;
            return typeof voice === 'string' && voice ? voice : 'Aoede';
        } catch {
            return 'Aoede';
        }
    });
    const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
    const [spokenCharIndex, setSpokenCharIndex] = useState<number | null>(null);
    const [playNonce, setPlayNonce] = useState(0);

    const sentencesRef = useRef<string[]>([]);
    const appStateRef = useRef(appState);
    const currentIndexRef = useRef(-1);
    const voiceModeRef = useRef(voiceMode);
    const playbackEpochRef = useRef(0);
    const startedTokenRef = useRef<string | null>(null);
    const nextIndexOverrideRef = useRef<number | null>(null);

    const setAppState = useCallback((next: SetStateAction<AppState>) => {
        const resolved = typeof next === 'function' ? next(appStateRef.current) : next;
        appStateRef.current = resolved;
        setAppStateValue(resolved);
    }, []);
    const setCurrentSentenceIndex = useCallback((next: SetStateAction<number>) => {
        const resolved = typeof next === 'function' ? next(currentIndexRef.current) : next;
        currentIndexRef.current = resolved;
        setCurrentSentenceIndexValue(resolved);
    }, []);

    useEffect(() => { voiceModeRef.current = voiceMode; }, [voiceMode]);

    /**
     * Finish at the next passage, except when an edit detached the audio being
     * heard from the document. In that case resume at the remapped position so
     * the passage now occupying it is not skipped.
     */
    const advanceAfterPassage = useCallback(() => {
        const override = nextIndexOverrideRef.current;
        nextIndexOverrideRef.current = null;
        if (override === null) {
            setCurrentSentenceIndex(previous => previous + 1);
            return;
        }
        startedTokenRef.current = null;
        setCurrentSentenceIndex(override);
        setPlayNonce(nonce => nonce + 1);
    }, []);

    const geminiPlayback = useGeminiPlayback({
        geminiConfig,
        generateAudioForSentence,
        documentId,
        documentName,
        smoothPlayback,
        sentencesRef,
        appStateRef,
        currentIndexRef,
        playbackEpochRef,
        setAppState,
        setError,
        setSpokenCharIndex,
        advanceAfterPassage,
    });

    const resetPlaybackState = useCallback(() => {
        console.log('[Audio] Reset: Playback state cleared');
        geminiPlayback.resetPlayback();
        window.speechSynthesis.cancel();
        nextIndexOverrideRef.current = null;
        startedTokenRef.current = null;
    }, [geminiPlayback.resetPlayback]);

    useEffect(() => {
        const populateVoiceList = () => {
            const available = window.speechSynthesis.getVoices();
            if (available.length === 0) return;
            setVoices(available);
            setSelectedVoiceURI(current => {
                if (current && available.some(voice => voice.voiceURI === current)) return current;
                const fallback = available.find(voice => voice.lang.startsWith('en') && voice.default)
                    || available[0];
                return fallback.voiceURI;
            });
        };
        populateVoiceList();
        window.speechSynthesis.onvoiceschanged = populateVoiceList;
        return () => {
            window.speechSynthesis.onvoiceschanged = null;
            resetPlaybackState();
        };
    }, [resetPlaybackState]);

    useEffect(() => {
        if (!selectedVoiceURI) return;
        try { localStorage.setItem('selectedVoiceURI', selectedVoiceURI); } catch { /* non-fatal */ }
    }, [selectedVoiceURI]);

    // Keep the file-watcher callback stable while routing work to the current
    // playback callbacks. Rebuilding it on every engine change churns the watcher.
    const applyPrefetchUpdateRef = useRef(geminiPlayback.applyPrefetchUpdate);
    const fillPrefetchQueueRef = useRef(geminiPlayback.fillPrefetchQueue);
    useEffect(() => {
        applyPrefetchUpdateRef.current = geminiPlayback.applyPrefetchUpdate;
        fillPrefetchQueueRef.current = geminiPlayback.fillPrefetchQueue;
    }, [geminiPlayback.applyPrefetchUpdate, geminiPlayback.fillPrefetchQueue]);

    const applySentenceUpdate = useCallback((next: string[], oldToNew: (number | null)[]) => {
        sentencesRef.current = next;
        applyPrefetchUpdateRef.current(next, oldToNew);

        const from = currentIndexRef.current;
        if (from >= 0) {
            const to = remapIndex(from, oldToNew, next.length);
            const survived = from < oldToNew.length && oldToNew[from] !== null;
            currentIndexRef.current = to;
            if (startedTokenRef.current !== null) {
                startedTokenRef.current = `${voiceModeRef.current}:${to}`;
            }
            if (to !== from) setCurrentSentenceIndex(to);
            nextIndexOverrideRef.current = survived ? null : to;
        }

        if (voiceModeRef.current === 'gemini') {
            fillPrefetchQueueRef.current(currentIndexRef.current + 1);
        }
    }, []);

    const speakBrowser = useCallback((text: string, voiceURI: string | null, onEnd?: () => void) => {
        speakWithPersistentVoice({
            text,
            voiceURI,
            voices,
            onEnd,
            onBoundary: setSpokenCharIndex,
        });
    }, [voices]);

    const handleStop = useCallback(() => {
        resetPlaybackState();
        setAppState(AppState.READY);
        setCurrentSentenceIndex(-1);
    }, [resetPlaybackState, setAppState, setCurrentSentenceIndex]);

    const handlePlay = useCallback(() => {
        const state = appStateRef.current;
        if (state === AppState.READY || state === AppState.IDLE) {
            setAppState(AppState.PLAYING);
            setCurrentSentenceIndex(0);
        } else if (state === AppState.PAUSED) {
            setAppState(AppState.PLAYING);
        }
    }, [setAppState, setCurrentSentenceIndex]);

    const handlePause = useCallback(() => {
        if (appStateRef.current !== AppState.PLAYING) return;
        resetPlaybackState();
        setAppState(AppState.PAUSED);
    }, [resetPlaybackState, setAppState]);

    const handleJumpToSentence = useCallback((
        index: number,
        mode: PlaybackSeekMode = 'preserve',
    ) => performPlaybackSeek({
        targetIndex: index,
        sentenceCount: sentencesRef.current.length,
        mode,
        currentState: appStateRef.current,
        stopPlayback: resetPlaybackState,
        syncIndex: setCurrentSentenceIndex,
        syncState: setAppState,
        restartPlaybackEffect: () => setPlayNonce(nonce => nonce + 1),
    }), [resetPlaybackState, setAppState, setCurrentSentenceIndex]);

    const handleSkipBackward = useCallback(() => {
        handleJumpToSentence(currentIndexRef.current - 1);
    }, [handleJumpToSentence]);

    const handleSkipForward = useCallback(() => {
        handleJumpToSentence(currentIndexRef.current + 1);
    }, [handleJumpToSentence]);

    // Stop the outgoing engine before the playback effect starts the same passage
    // on the newly selected engine.
    const previousVoiceModeRef = useRef(voiceMode);
    useEffect(() => {
        if (previousVoiceModeRef.current === voiceMode) return;
        previousVoiceModeRef.current = voiceMode;
        resetPlaybackState();
    }, [voiceMode, resetPlaybackState]);

    const narrationIdentity = useMemo(
        () => getNarrationIdentity(geminiConfig),
        [geminiConfig?.allowModelOverride, geminiConfig?.instructions,
            geminiConfig?.model, geminiConfig?.voice],
    );
    const previousNarrationIdentityRef = useRef(narrationIdentity);
    useEffect(() => {
        if (previousNarrationIdentityRef.current === narrationIdentity) return;
        previousNarrationIdentityRef.current = narrationIdentity;
        if (voiceModeRef.current !== 'gemini') return;
        resetPlaybackState();
        if (appStateRef.current === AppState.PLAYING) {
            setPlayNonce(nonce => nonce + 1);
        }
    }, [narrationIdentity, resetPlaybackState]);

    // The token prevents unrelated callback identity changes from restarting a
    // passage that is already in progress.
    useEffect(() => {
        const sentences = sentencesRef.current;
        const token = `${voiceMode}:${currentSentenceIndex}`;
        if (appState === AppState.PLAYING && startedTokenRef.current === token) return;
        if (appState !== AppState.PLAYING) startedTokenRef.current = null;

        if (appState === AppState.PLAYING
            && currentSentenceIndex >= 0
            && currentSentenceIndex < sentences.length) {
            startedTokenRef.current = token;
            setSpokenCharIndex(null);
            document.getElementById(`sentence-${currentSentenceIndex}`)
                ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            if (voiceMode === 'browser') {
                if (!window.speechSynthesis.speaking) window.speechSynthesis.cancel();
                const epoch = playbackEpochRef.current;
                speakBrowser(sentences[currentSentenceIndex], selectedVoiceURI, () => {
                    if (playbackEpochRef.current === epoch
                        && appStateRef.current === AppState.PLAYING
                        && currentIndexRef.current === currentSentenceIndex) {
                        advanceAfterPassage();
                    }
                });
            } else {
                void geminiPlayback.playSentence(currentSentenceIndex);
            }
        } else if (appState === AppState.PLAYING && currentSentenceIndex >= sentences.length) {
            handleStop();
        }
    }, [advanceAfterPassage, appState, currentSentenceIndex, geminiPlayback.playSentence,
        handleStop, playNonce, selectedVoiceURI, speakBrowser, voiceMode]);

    return {
        appState,
        setAppState,
        currentSentenceIndex,
        setCurrentSentenceIndex,
        sentencesRef,
        handlePlay,
        handlePause,
        handleStop,
        handleSkipForward,
        handleSkipBackward,
        handleJumpToSentence,
        error,
        setError,
        smoothPlayback,
        setSmoothPlayback,
        voiceMode,
        setVoiceMode,
        selectedVoiceURI,
        setSelectedVoiceURI,
        selectedGeminiVoice,
        setSelectedGeminiVoice,
        voices,
        spokenCharIndex,
        applySentenceUpdate,
    };
};
