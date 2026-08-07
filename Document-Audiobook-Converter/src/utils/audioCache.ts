/**
 * Compatibility facade for the persistent narration-audio cache.
 *
 * Existing callers intentionally keep importing this path. Implementation is
 * split by responsibility under audioCache/ while this file preserves the
 * complete public surface.
 */

export { DEFAULT_LIMITS } from './audioCache/types';
export type {
    CacheEvent,
    CacheLimits,
    ClipMeta,
    DocumentSummary,
    MatchLevel,
    MatchResult,
} from './audioCache/types';

export { noteActivity, subscribe } from './audioCache/events';
export {
    getLimits,
    isSavingEnabled,
    isStreamingEnabled,
    setLimits,
    setSavingEnabled,
    setStreamingEnabled,
} from './audioCache/preferences';
export { makeClipKey, makeDocumentId, makeLegacyClipKey } from './audioCache/identity';
export { compareNarration } from './audioCache/narration';
export { audioBufferToPcm16, pcm16ToAudioBuffer } from './audioCache/pcm';
export {
    adoptLegacyClip,
    clearAll,
    deleteClip,
    deleteDocument,
    enforceLimits,
    getClip,
    getStats,
    listClips,
    listDocuments,
    putClip,
    setLiveOnly,
    updateClipPosition,
} from './audioCache/store';
export { formatBytes, formatDuration } from './audioCache/formatters';
