import { describe, expect, it, vi } from 'vitest';
import { getNarrationIdentity } from '../src/hooks/audioEngine/narrationIdentity';
import { performPlaybackSeek } from '../src/hooks/audioEngine/playbackSeek';
import {
    collectStreamChunk,
    createStreamRecord,
    waitForStreamAvailability,
} from '../src/hooks/audioEngine/prefetchQueue';
import type { GeminiApiConfig } from '../src/types/gemini';
import { AppState } from '../src/types/playback';

const config = (overrides: Partial<GeminiApiConfig> = {}): GeminiApiConfig => ({
    apiKey: 'local-test-key',
    model: 'audio-model',
    allowModelOverride: true,
    temperature: 0.5,
    maxTokens: 100,
    timeout: 10,
    websocketUrl: 'ws://localhost:9083',
    voice: 'Aoede',
    instructions: 'Read verbatim.',
    ...overrides,
});

describe('synchronous playback seeking', () => {
    it('invalidates and stops active output before publishing the new index', () => {
        const events: string[] = [];
        let epoch = 4;
        let active = true;
        let index = 1;
        let state = AppState.PLAYING;
        const abandonedAttempt = epoch;

        const moved = performPlaybackSeek({
            targetIndex: 3,
            sentenceCount: 6,
            mode: 'preserve',
            currentState: state,
            stopPlayback: () => {
                events.push('stop');
                epoch += 1;
                active = false;
            },
            syncIndex: next => {
                expect(epoch).not.toBe(abandonedAttempt);
                events.push(`index:${next}`);
                index = next;
            },
            syncState: next => {
                events.push(`state:${next}`);
                state = next;
            },
            restartPlaybackEffect: () => events.push('restart'),
        });

        expect(moved).toBe(true);
        expect(active).toBe(false);
        expect(index).toBe(3);
        expect(state).toBe(AppState.PLAYING);
        expect(events).toEqual([
            'stop',
            'index:3',
            `state:${AppState.PLAYING}`,
            'restart',
        ]);
    });

    it('does not revive a stream that was waiting for its first fragment', async () => {
        const record = createStreamRecord();
        let epoch = 7;
        const attempt = epoch;
        const pending = waitForStreamAvailability(record, () => epoch === attempt);

        epoch += 1;
        collectStreamChunk(record, new ArrayBuffer(8));

        await expect(pending).resolves.toBe(false);
        expect(record.listeners.size).toBe(0);
    });

    it('rejects out-of-range jumps without touching playback', () => {
        const stopPlayback = vi.fn();
        expect(performPlaybackSeek({
            targetIndex: 4,
            sentenceCount: 4,
            mode: 'play',
            currentState: AppState.PAUSED,
            stopPlayback,
            syncIndex: vi.fn(),
            syncState: vi.fn(),
            restartPlaybackEffect: vi.fn(),
        })).toBe(false);
        expect(stopPlayback).not.toHaveBeenCalled();
    });
});

describe('Gemini narration identity', () => {
    it('changes for model, voice, instructions, or override mode', () => {
        const original = getNarrationIdentity(config());
        expect(getNarrationIdentity(config({ model: 'other-model' }))).not.toBe(original);
        expect(getNarrationIdentity(config({ voice: 'Kore' }))).not.toBe(original);
        expect(getNarrationIdentity(config({ instructions: 'Use a calm style.' }))).not.toBe(original);
        expect(getNarrationIdentity(config({ allowModelOverride: false }))).not.toBe(original);
    });

    it('ignores transport and timeout fields that do not alter narration identity', () => {
        const original = getNarrationIdentity(config());
        expect(getNarrationIdentity(config({
            apiKey: 'rotated-key',
            timeout: 99,
            websocketUrl: 'ws://localhost:9999',
        }))).toBe(original);
    });
});
