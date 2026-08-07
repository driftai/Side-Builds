import { describe, expect, it } from 'vitest';
import type { GeminiApiConfig } from '../src/types/gemini';
import {
    createDisconnectMessage,
    createInitMessage,
    createTurnMessage,
    isSessionReadyMessage,
    isTurnBoundaryMessage,
    parseServerMessage,
} from '../src/services/gemini/liveProtocol';

const config: GeminiApiConfig = {
    apiKey: 'test-key',
    model: 'test-model',
    allowModelOverride: false,
    temperature: 0.5,
    maxTokens: 100,
    timeout: 1000,
    websocketUrl: 'ws://localhost:9084',
    voice: 'Aoede',
    instructions: 'Narrate clearly.',
};

describe('Gemini Live protocol', () => {
    it('builds the narration init payload with its continuation hint', () => {
        expect(createInitMessage(config, {
            allowModelOverride: true,
            instructions: config.instructions,
            continuationHint: 'Previous passage',
        })).toEqual({
            type: 'init',
            voice: 'Aoede',
            model: 'test-model',
            allowModelOverride: true,
            apiKey: 'test-key',
            instructions: 'Narrate clearly.',
            continuationHint: 'Previous passage',
            sequentialAudioPlay: false,
        });
    });

    it('keeps test-session payloads free of narration-only continuity', () => {
        const message = createInitMessage(config, {
            allowModelOverride: false,
            instructions: 'Test connection',
        });
        expect(message).not.toHaveProperty('continuationHint');
        expect(message.allowModelOverride).toBe(false);
    });

    it('preserves turn text exactly and marks the turn complete', () => {
        expect(createTurnMessage('  keep spacing  ')).toEqual({
            realtime_input: {
                media_chunks: [{ mime_type: 'text/plain', data: '  keep spacing  ' }],
                turn_complete: true,
            },
        });
        expect(createDisconnectMessage()).toEqual({ type: 'disconnect' });
    });

    it('recognizes session readiness and both accepted turn boundaries', () => {
        const ready = parseServerMessage(JSON.stringify({
            text: 'Connected to Gemini API successfully',
            is_system_message: true,
        }));
        expect(isSessionReadyMessage(ready)).toBe(true);
        expect(isTurnBoundaryMessage({ is_transcription: true })).toBe(true);
        expect(isTurnBoundaryMessage({ turn_complete: true })).toBe(true);
        expect(isTurnBoundaryMessage({ audio: 'AAAA' })).toBe(false);
    });
});
