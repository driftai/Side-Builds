import type { GeminiApiConfig, NarrationResult } from '../../types/gemini';

export type LaneConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface LaneJob {
    text: string;
    priority: number;
    signal?: AbortSignal;
    onChunk?: (pcm: ArrayBuffer) => void;
    resolve: (result: NarrationResult) => void;
    reject: (error: unknown) => void;
}

export interface GeminiLaneDependencies {
    getConfig: () => GeminiApiConfig | null;
    isBlocked: () => boolean;
    getAudioContext: () => AudioContext;
    onStateChange: () => void;
}

export interface GeminiSchedulerDependencies {
    getAudioContext: () => AudioContext;
    onStateChange: (state: LaneConnectionState) => void;
    onBlockedChange: (blocked: boolean) => void;
}
