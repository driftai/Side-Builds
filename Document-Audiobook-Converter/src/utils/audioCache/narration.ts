import type { MatchLevel, MatchResult } from './types';

const normaliseWords = (s: string): string[] =>
    s.toLowerCase()
        .replace(/[^\p{L}\p{N}\s']/gu, ' ')
        .split(/\s+/)
        .filter(Boolean);

/** Length of the longest common subsequence of two word arrays. */
const lcsLength = (a: string[], b: string[]): number => {
    if (!a.length || !b.length) return 0;
    let previous = new Array(b.length + 1).fill(0);
    let current = new Array(b.length + 1).fill(0);
    for (let i = 1; i <= a.length; i++) {
        for (let j = 1; j <= b.length; j++) {
            current[j] = a[i - 1] === b[j - 1]
                ? previous[j - 1] + 1
                : Math.max(previous[j], current[j - 1]);
        }
        [previous, current] = [current, previous];
        current.fill(0);
    }
    return previous[b.length];
};

/** Slowest plausible narration, in characters per second. */
const MIN_CHARS_PER_SECOND = 6;
/** Below this duration the character-rate test is not meaningful. */
const MIN_AUDIO_SECONDS_TO_DOUBT = 2.5;
/** How much shorter than the source a transcript must be to look truncated. */
const TRUNCATED_BELOW_FRACTION = 0.6;

/** Compare what the model reported saying with the source it was given. */
export const compareNarration = (
    sourceText: string,
    spokenText: string,
    audioSeconds?: number,
): MatchResult => {
    const source = normaliseWords(sourceText || '');
    const spoken = normaliseWords(spokenText || '');

    if (!spoken.length) {
        return {
            level: 'unknown', ratio: null, wordDelta: -source.length,
            label: source.length ? 'no transcript stored' : 'nothing to compare',
        };
    }

    const spokenChars = (spokenText || '').trim().length;
    const looksTruncated = spoken.length < source.length * TRUNCATED_BELOW_FRACTION;
    if (audioSeconds && audioSeconds >= MIN_AUDIO_SECONDS_TO_DOUBT
        && looksTruncated
        && spokenChars < audioSeconds * MIN_CHARS_PER_SECOND) {
        return {
            level: 'unknown', ratio: null, wordDelta: spoken.length - source.length,
            label: 'transcript incomplete - cannot judge this one',
        };
    }

    const common = lcsLength(source, spoken);
    const ratio = (2 * common) / (source.length + spoken.length);
    const wordDelta = spoken.length - source.length;

    const OVERRUN_FACTOR = 1.75;
    const overran = source.length >= 4 && spoken.length >= source.length * OVERRUN_FACTOR;

    const level: MatchLevel = overran ? 'diverged'
        : ratio >= 0.75 ? 'match'
            : ratio >= 0.5 ? 'drift'
                : 'diverged';

    const pct = Math.round(ratio * 100);
    const times = (spoken.length / Math.max(1, source.length)).toFixed(1);
    const label = overran
        ? `spoke ${times}x the source - diverged`
        : level === 'match' ? (ratio >= 0.995 ? 'read word for word' : `${pct}% match`)
            : level === 'drift' ? `${pct}% match - drifted from the source`
                : `${pct}% match - diverged from the source`;

    return { level, ratio, wordDelta, label };
};
