import type { CacheEvent } from './types';

/**
 * One listener set for every cache caller. Keeping it here prevents storage and
 * preference modules from accidentally creating separate notification buses.
 */
const listeners = new Set<(event: CacheEvent) => void>();

export const subscribe = (fn: (event: CacheEvent) => void): (() => void) => {
    listeners.add(fn);
    return () => { listeners.delete(fn); };
};

/** Internal write-side bridge shared by the cache modules. */
export const emitCacheEvent = (event: CacheEvent): void => {
    for (const fn of [...listeners]) {
        try { fn(event); } catch { /* a bad listener must not break a write */ }
    }
};

/** Called by the audio engine as it works through sentences. */
export const noteActivity = (
    index: number, text: string, state: 'generating' | 'hit' | 'saved' | 'idle',
): void => emitCacheEvent({ type: 'activity', index, text, state });
