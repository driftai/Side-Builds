import { useCallback, useEffect, useRef, useState } from 'react';
import type {
    GeminiApiConfig,
    GeminiConnectionState,
    NarrationResult,
} from '../types/gemini';
import { GeminiLaneScheduler } from './gemini/GeminiLaneScheduler';

// Preserve the hook's established result type export.
export type { NarrationResult } from '../types/gemini';

export const useGemini = (geminiConfig: GeminiApiConfig | null) => {
    const [wsState, setWsState] = useState<GeminiConnectionState>('disconnected');
    const [connectionsBlocked, setConnectionsBlocked] = useState(false);
    const audioContextRef = useRef<AudioContext | null>(null);

    const getAudioContext = useCallback(() => {
        if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
            const AudioContextConstructor = window.AudioContext || (window as any).webkitAudioContext;
            audioContextRef.current = new AudioContextConstructor();
        }
        return audioContextRef.current;
    }, []);

    const schedulerRef = useRef<GeminiLaneScheduler | null>(null);
    if (!schedulerRef.current) {
        schedulerRef.current = new GeminiLaneScheduler({
            getAudioContext,
            onStateChange: state => setWsState(state),
            onBlockedChange: blocked => setConnectionsBlocked(blocked),
        });
    }
    const scheduler = schedulerRef.current;

    useEffect(() => { scheduler.setConfig(geminiConfig); }, [geminiConfig, scheduler]);
    useEffect(() => () => {
        audioContextRef.current?.close().catch(() => { });
        audioContextRef.current = null;
    }, []);

    const generateAudioForSentence = useCallback((
        text: string,
        signal?: AbortSignal,
        onChunk?: (pcm: ArrayBuffer) => void,
        priority?: number,
    ): Promise<NarrationResult> => scheduler.generateAudioForSentence(
        text,
        signal,
        onChunk,
        priority,
    ), [scheduler]);

    const disconnect = useCallback(() => scheduler.disconnect(), [scheduler]);
    const allowConnections = useCallback(() => scheduler.allowConnections(), [scheduler]);
    const resetContinuity = useCallback(() => scheduler.resetContinuity(), [scheduler]);

    return {
        wsState,
        generateAudioForSentence,
        disconnect,
        allowConnections,
        connectionsBlocked,
        resetContinuity,
    };
};
