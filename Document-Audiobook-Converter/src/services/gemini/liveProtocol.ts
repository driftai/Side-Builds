import type { GeminiApiConfig } from '../../types/gemini';

export interface GeminiServerMessage {
    audio?: string;
    text?: string;
    is_system_message?: boolean;
    is_transcription?: boolean;
    turn_complete?: boolean;
}

interface InitMessageOptions {
    allowModelOverride: boolean;
    instructions: string;
    continuationHint?: string;
}

export const createInitMessage = (
    config: GeminiApiConfig,
    options: InitMessageOptions,
): Record<string, unknown> => ({
    type: 'init',
    voice: config.voice,
    model: config.model,
    allowModelOverride: options.allowModelOverride,
    apiKey: config.apiKey,
    instructions: options.instructions,
    ...(options.continuationHint === undefined
        ? {}
        : { continuationHint: options.continuationHint }),
    sequentialAudioPlay: false,
});

export const createTurnMessage = (text: string): Record<string, unknown> => ({
    realtime_input: {
        media_chunks: [{ mime_type: 'text/plain', data: text }],
        turn_complete: true,
    },
});

export const createDisconnectMessage = (): Record<string, string> => ({
    type: 'disconnect',
});

export const parseServerMessage = (raw: string): GeminiServerMessage => JSON.parse(raw);

export const isSessionReadyMessage = (message: GeminiServerMessage): boolean => Boolean(
    message.text?.includes('Connected to Gemini API') && message.is_system_message,
);

export const isTurnBoundaryMessage = (message: GeminiServerMessage): boolean => Boolean(
    message.is_transcription || message.turn_complete,
);
