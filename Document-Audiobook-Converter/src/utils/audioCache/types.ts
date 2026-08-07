export interface CacheLimits {
    /** Hard ceiling on total stored audio. */
    maxBytes: number;
    /** Clips untouched for longer than this are swept regardless of size. */
    maxAgeDays: number;
}

export const DEFAULT_LIMITS: CacheLimits = {
    maxBytes: 750 * 1024 * 1024,   // ~4.5 hours of narration
    maxAgeDays: 30,
};

export interface ClipMeta {
    key: string;
    documentId: string;
    documentName: string;
    index: number;
    /** The source text this clip was generated from, as it read at the time. */
    text: string;
    /** What the model reported actually saying. Empty on older clips. */
    spokenText: string;
    voice: string;
    model: string;
    /** Normalized delivery guidance used when this audio was generated. */
    styleInstructions?: string;
    /** Missing on clips made before narration policy became part of identity. */
    narrationPolicyVersion?: string;
    /** Missing on clips made under an older cache-key normalization scheme. */
    cacheNormalizationVersion?: string;
    bytes: number;
    durationSec: number;
    sampleRate: number;
    createdAt: number;
    lastUsedAt: number;
    /** When true, bypass this clip and regenerate it on next play. */
    liveOnly: boolean;
}

export interface DocumentSummary {
    documentId: string;
    documentName: string;
    clips: number;
    bytes: number;
    durationSec: number;
    lastUsedAt: number;
}

export type CacheEvent =
    | { type: 'changed' }
    | { type: 'removed' }
    | {
        type: 'activity';
        index: number;
        text: string;
        state: 'generating' | 'hit' | 'saved' | 'idle';
    };

export type MatchLevel = 'match' | 'drift' | 'diverged' | 'unknown';

export interface MatchResult {
    level: MatchLevel;
    /** 0-1 similarity, or null when there is nothing to compare. */
    ratio: number | null;
    /** Words spoken minus words in the source; positive means the model added. */
    wordDelta: number;
    label: string;
}
