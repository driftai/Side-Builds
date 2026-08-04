import type React from 'react';
import { useState, useRef, useCallback, useEffect } from 'react';
import { GeminiApiConfig } from '../components/GeminiConfig';

export enum AppState {
    IDLE,
    PROCESSING,
    READY,
    PLAYING,
    PAUSED,
    ERROR,
}

interface AudioState {
    appState: AppState;
    setAppState: (state: AppState) => void;
    currentSentenceIndex: number;
    setCurrentSentenceIndex: React.Dispatch<React.SetStateAction<number>>;
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
    voiceMode: 'browser' | 'gemini';
    setVoiceMode: React.Dispatch<React.SetStateAction<'browser' | 'gemini'>>;
    selectedVoiceURI: string | null;
    setSelectedVoiceURI: (uri: string | null) => void;
    selectedGeminiVoice: string;
    setSelectedGeminiVoice: (voice: string) => void;
    voices: SpeechSynthesisVoice[];
}

export const useAudioEngine = (
    geminiConfig: GeminiApiConfig | null,
    generateAudioForSentence: (text: string, signal?: AbortSignal) => Promise<AudioBuffer>
): AudioState => {
    const [appState, setAppState] = useState<AppState>(AppState.IDLE);
    const [currentSentenceIndex, setCurrentSentenceIndex] = useState<number>(-1);
    const [error, setError] = useState<string | null>(null);
    const [smoothPlayback, setSmoothPlayback] = useState<boolean>(true);
    const [voiceMode, setVoiceMode] = useState<'browser' | 'gemini'>('browser');
    const [selectedVoiceURI, setSelectedVoiceURI] = useState<string | null>(null);
    const [selectedGeminiVoice, setSelectedGeminiVoice] = useState<string>('Aoede');
    const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

    const audioContextRef = useRef<AudioContext | null>(null);
    const currentAudioSourceRef = useRef<AudioBufferSourceNode | null>(null);
    const sentencesRef = useRef<string[]>([]);
    const appStateRef = useRef<AppState>(appState);

    // Look-ahead queue of sentences already being generated, keyed by index.
    //
    // This replaces a single prefetch slot that was abandoned and re-created on
    // every advance: only one sentence could ever be in flight, so if a sentence
    // took longer to generate than the previous one took to play, playback sat
    // silent for the difference. Holding several in flight lets generation run
    // ahead of playback and absorb the slow ones.
    //
    // Requests are serialised on the shared socket (see useGemini), so a depth of
    // N queues N turns back-to-back rather than firing them concurrently - the
    // pipeline simply stays fed.
    const PREFETCH_DEPTH = 3;
    const prefetchQueueRef = useRef<Map<number, { promise: Promise<AudioBuffer>; controller: AbortController }>>(new Map());

    const consoleLogger = useRef({
        logAudio: (action: string, details: string) => console.log(`[Audio] ${action}: ${details}`),
    });

    useEffect(() => { appStateRef.current = appState; }, [appState]);

    const getAudioContext = useCallback(() => {
        if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
            audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }
        return audioContextRef.current;
    }, []);

    const resetPlaybackState = useCallback(() => {
        consoleLogger.current.logAudio('Reset', 'Playback state cleared');
        window.speechSynthesis.cancel();
        if (currentAudioSourceRef.current) {
            currentAudioSourceRef.current.onended = null;
            try { currentAudioSourceRef.current.stop(); } catch (e) { }
            currentAudioSourceRef.current = null;
        }
        for (const { promise, controller } of prefetchQueueRef.current.values()) {
            controller.abort();
            promise.catch(() => { });  // queued rejections are expected once aborted
        }
        prefetchQueueRef.current.clear();
    }, []);

    // Voice list population
    useEffect(() => {
        const populateVoiceList = () => {
            const newVoices = window.speechSynthesis.getVoices();
            if (newVoices.length > 0) {
                setVoices(newVoices);
                if (!selectedVoiceURI) {
                    const defaultVoice = newVoices.find(v => v.lang.startsWith('en') && v.default) || newVoices[0];
                    setSelectedVoiceURI(defaultVoice.voiceURI);
                }
            }
        };
        populateVoiceList();
        speechSynthesis.onvoiceschanged = populateVoiceList;
        return () => {
            speechSynthesis.onvoiceschanged = null;
            resetPlaybackState();
        };
    }, [resetPlaybackState, selectedVoiceURI]);

    /** Drop queued sentences we have already moved past, aborting their work. */
    const prunePrefetchQueue = useCallback((beforeIndex: number) => {
        for (const [i, entry] of [...prefetchQueueRef.current.entries()]) {
            if (i < beforeIndex) {
                entry.controller.abort();
                entry.promise.catch(() => { });
                prefetchQueueRef.current.delete(i);
            }
        }
    }, []);

    /** Queue one sentence if it isn't queued already. Returns its promise. */
    const enqueuePrefetch = useCallback((index: number): Promise<AudioBuffer> | null => {
        if (index < 0 || index >= sentencesRef.current.length) return null;

        const existing = prefetchQueueRef.current.get(index);
        if (existing) return existing.promise;

        const text = sentencesRef.current[index];
        if (!text) return null;

        const controller = new AbortController();
        consoleLogger.current.logAudio('Prefetching', `Sentence ${index}`);
        const promise = generateAudioForSentence(text, controller.signal);

        // Attach handlers that never reject, so an unclaimed queue entry can't
        // surface as an unhandled rejection while it waits to be played.
        promise.then(
            () => {
                if (!controller.signal.aborted) {
                    consoleLogger.current.logAudio('Prefetched', `Sentence ${index} ready`);
                }
            },
            (error) => {
                if (error?.name !== 'AbortError') {
                    console.warn(`Prefetch of sentence ${index} failed, will retry on demand:`, error?.message ?? error);
                }
                // Drop it so playSentence regenerates rather than replaying the failure.
                if (prefetchQueueRef.current.get(index)?.controller === controller) {
                    prefetchQueueRef.current.delete(index);
                }
            }
        );

        prefetchQueueRef.current.set(index, { promise, controller });
        return promise;
    }, [generateAudioForSentence]);

    /** Keep the next PREFETCH_DEPTH sentences after `fromIndex` in flight. */
    const fillPrefetchQueue = useCallback((fromIndex: number) => {
        if (!smoothPlayback) return;
        for (let i = fromIndex; i < fromIndex + PREFETCH_DEPTH; i++) {
            enqueuePrefetch(i);
        }
    }, [smoothPlayback, enqueuePrefetch]);

    const playSentence = useCallback(async (index: number) => {
        if (currentAudioSourceRef.current) {
            currentAudioSourceRef.current.onended = null;
            try { currentAudioSourceRef.current.stop(); } catch (e) { }
        }

        // Anything before this sentence is history; stop paying for it.
        prunePrefetchQueue(index);

        // Claim THIS sentence before queueing any look-ahead. Turns are
        // serialised in the order they are requested, so filling the look-ahead
        // first would put the sentence the listener is waiting on at the back of
        // the queue - silence until three other sentences had been generated.
        let audioBuffer: AudioBuffer | null = null;
        const queued = prefetchQueueRef.current.get(index)?.promise ?? enqueuePrefetch(index);

        // Now extend the look-ahead behind it.
        fillPrefetchQueue(index + 1);

        if (!queued) {
            console.error(`No text found for sentence ${index}`);
            setError('Failed to generate audio for the selected sentence.');
            setAppState(AppState.PAUSED);
            return;
        }

        try {
            audioBuffer = await queued;
            consoleLogger.current.logAudio('Playing', `Sentence ${index}`);
        } catch (error: any) {
            if (error?.name === 'AbortError') return;  // superseded by a seek or stop

            // One retry on demand. A prefetch can fail for reasons that have
            // nothing to do with this sentence (a dropped socket, a transient
            // 1011 from Google), and pausing the whole book on it - which is
            // what used to happen - is far worse than spending one more call.
            console.warn(`Sentence ${index} failed from queue, regenerating:`, error?.message ?? error);
            prefetchQueueRef.current.delete(index);
            try {
                const text = sentencesRef.current[index];
                if (!text) throw new Error(`No text found for sentence ${index}`);
                audioBuffer = await generateAudioForSentence(text);
            } catch (retryError: any) {
                if (retryError?.name === 'AbortError') return;
                console.error(`Error generating audio for sentence ${index}:`, retryError);
                setError('Failed to generate audio for the selected sentence.');
                setAppState(AppState.PAUSED);
                return;
            }
        }

        prefetchQueueRef.current.delete(index);

        if (audioBuffer) {
            const audioContext = getAudioContext();

            // Ensure audio context is running (fixes cutoff at beginning)
            // MUST await this to prevent audio from starting before context is ready
            if (audioContext.state === 'suspended') {
                consoleLogger.current.logAudio('Audio Context', 'Resuming from suspended state...');
                await audioContext.resume();
                consoleLogger.current.logAudio('Audio Context', 'Resumed successfully');
            }

            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);
            currentAudioSourceRef.current = source;
            source.onended = () => {
                if (appStateRef.current === AppState.PLAYING) {
                    setCurrentSentenceIndex(prevIndex => prevIndex + 1);
                }
            };

            // Top the queue up again: this sentence's duration is now known, so
            // the look-ahead has exactly that long to get the next ones ready.
            fillPrefetchQueue(index + 1);

            source.start();
        }
    }, [generateAudioForSentence, getAudioContext, prunePrefetchQueue, fillPrefetchQueue, enqueuePrefetch]);

    const speakWithPersistentVoice = useCallback((text: string, voiceURI: string | null, onEnd?: () => void) => {
        const utterance = new SpeechSynthesisUtterance(text);
        const selectedVoice = voices.find(v => v.voiceURI === voiceURI);

        if (selectedVoice) {
            utterance.voice = selectedVoice;
            const currentVoices = window.speechSynthesis.getVoices();
            const voiceIndex = currentVoices.findIndex(v => v.voiceURI === selectedVoice.voiceURI);
            if (voiceIndex >= 0) {
                utterance.voice = currentVoices[voiceIndex];
            }
            utterance.lang = selectedVoice.lang;
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;
        }

        if (onEnd) {
            utterance.onend = onEnd;
        }

        utterance.onerror = (event) => {
            console.warn('TTS utterance error:', event.error);
            // These were 'voice-unavailable' / 'voice-cancelled', neither of which
            // is a SpeechSynthesisErrorCode - the retry-with-default-voice fallback
            // could never fire. These are the real codes for "this voice won't work".
            if (event.error === 'language-unavailable' || event.error === 'synthesis-unavailable') {
                const fallbackUtterance = new SpeechSynthesisUtterance(text);
                fallbackUtterance.onend = onEnd;
                window.speechSynthesis.speak(fallbackUtterance);
            } else if (onEnd) {
                onEnd();
            }
        };

        window.speechSynthesis.speak(utterance);
    }, [voices]);

    // Playback effect
    useEffect(() => {
        const sentences = sentencesRef.current;
        if (appState === AppState.PLAYING && currentSentenceIndex >= 0 && currentSentenceIndex < sentences.length) {
            document.getElementById(`sentence-${currentSentenceIndex}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            if (voiceMode === 'browser') {
                if (!window.speechSynthesis.speaking) {
                    window.speechSynthesis.cancel();
                }

                speakWithPersistentVoice(
                    sentences[currentSentenceIndex],
                    selectedVoiceURI,
                    () => setCurrentSentenceIndex(prev => prev + 1)
                );
            } else {
                playSentence(currentSentenceIndex);
            }
        } else if (appState === AppState.PLAYING && currentSentenceIndex >= sentences.length) {
            handleStop();
        }
    }, [currentSentenceIndex, appState, speakWithPersistentVoice, selectedVoiceURI, playSentence, voiceMode]);

    const handleStop = useCallback(() => {
        resetPlaybackState();
        setAppState(AppState.READY);
        setCurrentSentenceIndex(-1);
    }, [resetPlaybackState]);

    const handlePlay = useCallback(() => {
        if (appState === AppState.READY || appState === AppState.IDLE) {
            setAppState(AppState.PLAYING);
            setCurrentSentenceIndex(0);
        } else if (appState === AppState.PAUSED) {
            setAppState(AppState.PLAYING);
        }
    }, [appState]);

    const handlePause = useCallback(() => {
        if (appState === AppState.PLAYING) {
            resetPlaybackState();
            setAppState(AppState.PAUSED);
        }
    }, [appState, resetPlaybackState]);

    const handleSkipBackward = useCallback(() => {
        if (currentSentenceIndex > 0) {
            setCurrentSentenceIndex(prev => prev - 1);
        }
    }, [currentSentenceIndex]);

    const handleSkipForward = useCallback(() => {
        if (currentSentenceIndex < sentencesRef.current.length - 1) {
            setCurrentSentenceIndex(prev => prev + 1);
        }
    }, [currentSentenceIndex]);

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
        voices
    };
};
