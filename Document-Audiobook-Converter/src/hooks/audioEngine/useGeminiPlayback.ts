import type React from 'react';
import { useCallback, useEffect, useRef } from 'react';
import type { GeminiApiConfig } from '../../types/gemini';
import { AppState } from '../../types/playback';
import { isStreamingEnabled, subscribe } from '../../utils/audioCache';
import { isNarratable } from '../../utils/textProcessing';
import { PcmStreamPlayer } from '../../utils/streamingPlayer';
import { requestNarrationAudio } from './cacheNarration';
import {
    clearPrefetchQueue,
    closeStreamRecord,
    collectStreamChunk,
    createStreamRecord,
    prunePrefetchQueue,
    remapPrefetchQueue,
} from './prefetchQueue';
import {
    PCM_SAMPLE_RATE,
    PREFETCH_DEPTH,
    type GenerateAudioForSentence,
    type PrefetchEntry,
    type StreamRecord,
} from './types';

interface GeminiPlaybackOptions {
    geminiConfig: GeminiApiConfig | null;
    generateAudioForSentence: GenerateAudioForSentence;
    documentId: string | null;
    documentName: string;
    smoothPlayback: boolean;
    sentencesRef: React.MutableRefObject<string[]>;
    appStateRef: React.MutableRefObject<AppState>;
    currentIndexRef: React.MutableRefObject<number>;
    setAppState: React.Dispatch<React.SetStateAction<AppState>>;
    setError: React.Dispatch<React.SetStateAction<string | null>>;
    setSpokenCharIndex: React.Dispatch<React.SetStateAction<number | null>>;
    advanceAfterPassage: () => void;
}

export const useGeminiPlayback = ({
    geminiConfig,
    generateAudioForSentence,
    documentId,
    documentName,
    smoothPlayback,
    sentencesRef,
    appStateRef,
    currentIndexRef,
    setAppState,
    setError,
    setSpokenCharIndex,
    advanceAfterPassage,
}: GeminiPlaybackOptions) => {
    const audioContextRef = useRef<AudioContext | null>(null);
    const currentAudioSourceRef = useRef<AudioBufferSourceNode | null>(null);
    const prefetchQueueRef = useRef<Map<number, PrefetchEntry>>(new Map());
    const activePlayerRef = useRef<PcmStreamPlayer | null>(null);
    const playbackEpochRef = useRef(0);
    const wordTimerRef = useRef<number | null>(null);
    const fillFromRef = useRef<((from: number) => void) | null>(null);
    const logAudio = useCallback((action: string, details: string) => {
        console.log(`[Audio] ${action}: ${details}`);
    }, []);

    const getAudioContext = useCallback(() => {
        if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
            audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }
        return audioContextRef.current;
    }, []);

    const resetPlayback = useCallback(() => {
        if (currentAudioSourceRef.current) {
            currentAudioSourceRef.current.onended = null;
            try { currentAudioSourceRef.current.stop(); } catch { /* already stopped */ }
            currentAudioSourceRef.current = null;
        }
        playbackEpochRef.current += 1;
        activePlayerRef.current?.stop();
        activePlayerRef.current = null;
        clearPrefetchQueue(prefetchQueueRef.current);
        if (wordTimerRef.current !== null) {
            cancelAnimationFrame(wordTimerRef.current);
            wordTimerRef.current = null;
        }
        setSpokenCharIndex(null);
    }, [setSpokenCharIndex]);

    useEffect(() => subscribe(event => {
        if (event.type !== 'removed') return;
        for (const [index, entry] of [...prefetchQueueRef.current.entries()]) {
            if (!entry.settled || index === currentIndexRef.current) continue;
            entry.promise.catch(() => { });
            prefetchQueueRef.current.delete(index);
        }
    }), [currentIndexRef]);

    const requestAudio = useCallback((
        index: number,
        text: string,
        signal?: AbortSignal,
        onChunk?: (pcm: ArrayBuffer) => void,
    ) => requestNarrationAudio({
        index,
        text,
        signal,
        onChunk,
        geminiConfig,
        documentId,
        documentName,
        getAudioContext,
        generateAudioForSentence,
        logAudio,
    }), [geminiConfig, documentId, documentName, generateAudioForSentence, getAudioContext, logAudio]);

    const enqueuePrefetch = useCallback((index: number): Promise<AudioBuffer> | null => {
        if (index < 0 || index >= sentencesRef.current.length) return null;
        const existing = prefetchQueueRef.current.get(index);
        if (existing) return existing.promise;

        const text = sentencesRef.current[index];
        if (!text || !isNarratable(text)) return null;

        const controller = new AbortController();
        logAudio('Prefetching', `Sentence ${index}`);
        const record = isStreamingEnabled() ? createStreamRecord() : null;
        const onChunk = record ? (pcm: ArrayBuffer) => collectStreamChunk(record, pcm) : undefined;
        const promise = requestAudio(index, text, controller.signal, onChunk);

        promise.then(
            () => {
                const entry = prefetchQueueRef.current.get(index);
                if (entry?.controller === controller) entry.settled = true;
                closeStreamRecord(record);
                if (!controller.signal.aborted) {
                    logAudio('Prefetched', `Sentence ${index} ready`);
                    fillFromRef.current?.(currentIndexRef.current + 1);
                }
            },
            error => {
                if (error?.name !== 'AbortError') {
                    console.warn(`Prefetch of sentence ${index} failed, will retry on demand:`, error?.message ?? error);
                }
                closeStreamRecord(record);
                if (prefetchQueueRef.current.get(index)?.controller === controller) {
                    prefetchQueueRef.current.delete(index);
                }
            },
        );

        prefetchQueueRef.current.set(index, {
            promise,
            controller,
            text,
            stream: record ?? undefined,
        });
        return promise;
    }, [currentIndexRef, logAudio, requestAudio, sentencesRef]);

    const fillPrefetchQueue = useCallback((fromIndex: number) => {
        if (!smoothPlayback) return;
        for (let index = fromIndex; index < fromIndex + PREFETCH_DEPTH; index++) {
            enqueuePrefetch(index);
        }
    }, [smoothPlayback, enqueuePrefetch]);

    useEffect(() => { fillFromRef.current = fillPrefetchQueue; }, [fillPrefetchQueue]);

    const applyPrefetchUpdate = useCallback((next: string[], oldToNew: (number | null)[]) => {
        prefetchQueueRef.current = remapPrefetchQueue(prefetchQueueRef.current, next, oldToNew);
    }, []);

    const playStreamed = useCallback(async (index: number, record: StreamRecord): Promise<boolean> => {
        const epoch = playbackEpochRef.current;
        const stillWanted = () => playbackEpochRef.current === epoch;
        const audioContext = getAudioContext();
        if (audioContext.state === 'suspended') {
            try { await audioContext.resume(); } catch { return false; }
        }
        if (!stillWanted() || record.done) return false;

        if (record.chunks.length === 0) {
            const streaming = await new Promise<boolean>(resolve => {
                const probe = (pcm: ArrayBuffer | null) => {
                    record.listeners.delete(probe);
                    resolve(pcm !== null);
                };
                record.listeners.add(probe);
            });
            if (!streaming) return false;
        }
        if (!stillWanted()
            || appStateRef.current !== AppState.PLAYING
            || currentIndexRef.current !== index) return false;

        logAudio('Streaming', `Sentence ${index} while it generates`);
        const entry = prefetchQueueRef.current.get(index);
        if (entry) entry.keepToCompletion = true;

        let listener: (pcm: ArrayBuffer | null) => void;
        const player = new PcmStreamPlayer({
            context: audioContext,
            sampleRate: PCM_SAMPLE_RATE,
            onStarved: () => logAudio('Stream ran dry', `Sentence ${index} - generation fell behind playback`),
            onFinished: () => {
                record.listeners.delete(listener);
                if (activePlayerRef.current !== player) return;
                activePlayerRef.current = null;
                if (appStateRef.current === AppState.PLAYING) advanceAfterPassage();
            },
        });
        listener = pcm => {
            if (activePlayerRef.current !== player) return;
            if (pcm === null) player.end(); else player.push(pcm);
        };

        activePlayerRef.current = player;
        record.listeners.add(listener);
        for (const chunk of record.chunks) player.push(chunk);
        if (record.done) player.end();

        const totalChars = (sentencesRef.current[index] ?? '').length || 1;
        const followStream = () => {
            if (appStateRef.current !== AppState.PLAYING || activePlayerRef.current !== player) {
                wordTimerRef.current = null;
                return;
            }
            const scheduled = player.scheduledSeconds;
            if (scheduled > 0) {
                const progress = Math.min(1, Math.max(0, player.elapsedSeconds / scheduled));
                setSpokenCharIndex(Math.floor(progress * totalChars));
            }
            wordTimerRef.current = requestAnimationFrame(followStream);
        };
        if (wordTimerRef.current !== null) cancelAnimationFrame(wordTimerRef.current);
        wordTimerRef.current = requestAnimationFrame(followStream);
        return true;
    }, [advanceAfterPassage, appStateRef, currentIndexRef, getAudioContext, logAudio, sentencesRef, setSpokenCharIndex]);

    const playSentence = useCallback(async (index: number) => {
        const epoch = playbackEpochRef.current;
        const stillWanted = () => playbackEpochRef.current === epoch;
        if (currentAudioSourceRef.current) {
            currentAudioSourceRef.current.onended = null;
            try { currentAudioSourceRef.current.stop(); } catch { /* already stopped */ }
        }
        prunePrefetchQueue(prefetchQueueRef.current, index);

        if (!isNarratable(sentencesRef.current[index] ?? '')) {
            logAudio('Skipping', `Sentence ${index} has no speakable text`);
            fillPrefetchQueue(index + 1);
            window.setTimeout(() => {
                if (appStateRef.current === AppState.PLAYING
                    && currentIndexRef.current === index) advanceAfterPassage();
            }, 200);
            return;
        }

        let audioBuffer: AudioBuffer | null = null;
        const queued = prefetchQueueRef.current.get(index)?.promise ?? enqueuePrefetch(index);
        fillPrefetchQueue(index + 1);
        if (!queued) {
            console.error(`No text found for sentence ${index}`);
            setError('Failed to generate audio for the selected sentence.');
            setAppState(AppState.PAUSED);
            return;
        }

        const pending = prefetchQueueRef.current.get(index);
        const stream = pending?.stream;
        if (pending && !pending.settled && stream && !stream.done) {
            if (await playStreamed(index, stream)) return;
        }

        try {
            audioBuffer = await queued;
            logAudio('Playing', `Sentence ${index}`);
        } catch (error: any) {
            if (error?.name === 'AbortError') return;
            console.warn(`Sentence ${index} failed from queue, regenerating:`, error?.message ?? error);
            prefetchQueueRef.current.delete(index);
            try {
                const text = sentencesRef.current[index];
                if (!text) throw new Error(`No text found for sentence ${index}`);
                audioBuffer = await requestAudio(index, text);
            } catch (retryError: any) {
                if (retryError?.name === 'AbortError') return;
                console.error(`Error generating audio for sentence ${index}:`, retryError);
                const message = typeof retryError?.message === 'string'
                    && retryError.message.includes('disconnected')
                    ? retryError.message
                    : 'Failed to generate audio for the selected sentence.';
                setError(message);
                setAppState(AppState.PAUSED);
                return;
            }
        }

        prefetchQueueRef.current.delete(index);
        if (!stillWanted() || !audioBuffer) return;
        const audioContext = getAudioContext();
        if (audioContext.state === 'suspended') {
            logAudio('Audio Context', 'Resuming from suspended state...');
            await audioContext.resume();
            logAudio('Audio Context', 'Resumed successfully');
        }
        if (!stillWanted()) return;

        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);
        currentAudioSourceRef.current = source;
        source.onended = () => {
            if (appStateRef.current === AppState.PLAYING) advanceAfterPassage();
        };
        fillPrefetchQueue(index + 1);
        source.start();

        const totalChars = (sentencesRef.current[index] ?? '').length || 1;
        const startedAt = audioContext.currentTime;
        const followAudio = () => {
            if (appStateRef.current !== AppState.PLAYING || currentAudioSourceRef.current !== source) {
                wordTimerRef.current = null;
                return;
            }
            const elapsed = audioContext.currentTime - startedAt;
            const progress = Math.min(1, Math.max(0, elapsed / (audioBuffer!.duration || 1)));
            setSpokenCharIndex(Math.floor(progress * totalChars));
            wordTimerRef.current = requestAnimationFrame(followAudio);
        };
        if (wordTimerRef.current !== null) cancelAnimationFrame(wordTimerRef.current);
        wordTimerRef.current = requestAnimationFrame(followAudio);
    }, [advanceAfterPassage, appStateRef, currentIndexRef, enqueuePrefetch, fillPrefetchQueue,
        getAudioContext, logAudio, playStreamed, requestAudio, sentencesRef, setAppState, setError,
        setSpokenCharIndex]);

    return { resetPlayback, playSentence, applyPrefetchUpdate, fillPrefetchQueue };
};
