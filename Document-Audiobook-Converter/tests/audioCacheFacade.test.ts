import { afterEach, describe, expect, it, vi } from 'vitest';
import * as cache from '../src/utils/audioCache';
import { subscribe as subscribeToCacheEvents } from '../src/utils/audioCache/events';

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('audioCache compatibility facade', () => {
    it('keeps the established runtime export surface', () => {
        expect(Object.keys(cache).sort()).toEqual([
            'DEFAULT_LIMITS',
            'adoptLegacyClip',
            'audioBufferToPcm16',
            'clearAll',
            'compareNarration',
            'deleteClip',
            'deleteDocument',
            'enforceLimits',
            'formatBytes',
            'formatDuration',
            'getClip',
            'getLimits',
            'getStats',
            'isSavingEnabled',
            'isStreamingEnabled',
            'listClips',
            'listDocuments',
            'makeClipKey',
            'makeDocumentId',
            'makeLegacyClipKey',
            'noteActivity',
            'pcm16ToAudioBuffer',
            'putClip',
            'setLimits',
            'setLiveOnly',
            'setSavingEnabled',
            'setStreamingEnabled',
            'subscribe',
            'updateClipPosition',
        ].sort());
    });

    it('re-exports the singleton event bus instead of wrapping it', () => {
        expect(cache.subscribe).toBe(subscribeToCacheEvents);
    });

    it('retains preference keys and writes before announcing changes', () => {
        const values = new Map<string, string>();
        vi.stubGlobal('localStorage', {
            getItem: (key: string) => values.get(key) ?? null,
            setItem: (key: string, value: string) => { values.set(key, value); },
        });

        const snapshots: Array<{ saving: string | null; streaming: string | null }> = [];
        const unsubscribe = cache.subscribe(event => {
            if (event.type === 'changed') {
                snapshots.push({
                    saving: values.get('audioCacheSavingEnabled') ?? null,
                    streaming: values.get('audioStreamingEnabled') ?? null,
                });
            }
        });

        try {
            expect(cache.setSavingEnabled(false)).toBe(false);
            expect(cache.setStreamingEnabled(true)).toBe(true);
            expect(cache.setLimits({ maxBytes: 123 })).toEqual({
                maxBytes: 123,
                maxAgeDays: cache.DEFAULT_LIMITS.maxAgeDays,
            });
        } finally {
            unsubscribe();
        }

        expect(snapshots).toEqual([
            { saving: 'false', streaming: null },
            { saving: 'false', streaming: 'true' },
        ]);
        expect(JSON.parse(values.get('audioCacheLimits') ?? '')).toEqual({
            maxBytes: 123,
            maxAgeDays: cache.DEFAULT_LIMITS.maxAgeDays,
        });
    });
});
