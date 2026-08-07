import { emitCacheEvent } from './events';
import { DEFAULT_LIMITS } from './types';
import type { CacheLimits } from './types';

const LIMITS_KEY = 'audioCacheLimits';
const SAVING_KEY = 'audioCacheSavingEnabled';
const STREAMING_KEY = 'audioStreamingEnabled';

export const getLimits = (): CacheLimits => {
    try {
        const raw = localStorage.getItem(LIMITS_KEY);
        if (raw) return { ...DEFAULT_LIMITS, ...JSON.parse(raw) };
    } catch { /* fall through to defaults */ }
    return { ...DEFAULT_LIMITS };
};

export const setLimits = (limits: Partial<CacheLimits>): CacheLimits => {
    const merged = { ...getLimits(), ...limits };
    try { localStorage.setItem(LIMITS_KEY, JSON.stringify(merged)); } catch { /* non-fatal */ }
    return merged;
};

/** Whether generated audio is kept between plays. */
export const isSavingEnabled = (): boolean => {
    try { return localStorage.getItem(SAVING_KEY) !== 'false'; } catch { return true; }
};

export const setSavingEnabled = (enabled: boolean): boolean => {
    try { localStorage.setItem(SAVING_KEY, enabled ? 'true' : 'false'); } catch { /* non-fatal */ }
    emitCacheEvent({ type: 'changed' });
    return enabled;
};

/** Whether playback may begin before a passage has finished generating. */
export const isStreamingEnabled = (): boolean => {
    try { return localStorage.getItem(STREAMING_KEY) === 'true'; } catch { return false; }
};

export const setStreamingEnabled = (enabled: boolean): boolean => {
    try { localStorage.setItem(STREAMING_KEY, enabled ? 'true' : 'false'); } catch { /* non-fatal */ }
    emitCacheEvent({ type: 'changed' });
    return enabled;
};
