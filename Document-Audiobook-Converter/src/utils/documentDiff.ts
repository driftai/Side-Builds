/**
 * Work out what actually changed between two versions of a document.
 *
 * When the file on disk is edited, re-splitting it produces a whole new array of
 * sentences. Treating that as a new document throws away everything the reader
 * knows - where you were, which passages are already generated, which are still
 * in flight - for what is usually a one-word change.
 *
 * Aligning the two versions instead says which old sentence became which new
 * one, so the session can be updated in place: unchanged passages keep their
 * queued audio even if an insertion above them shifted their position, and only
 * the passages that genuinely changed are regenerated.
 */

export interface SentenceAlignment {
    /**
     * For each index in the old array, where that sentence now lives - or null
     * if it is gone. Sentences that merely moved keep a mapping.
     */
    oldToNew: (number | null)[];
    /** Nothing changed; the caller can skip the update entirely. */
    identical: boolean;
    /** Sentences in the new document that did not come from the old one. */
    changedCount: number;
}

/**
 * Cap on the alignment table. A full comparison is quadratic, and an edit to a
 * very large document would otherwise allocate hundreds of megabytes. Past this
 * the middle section falls back to comparing position by position, which still
 * gets the common cases right and never blocks the app.
 */
const MAX_DIFF_CELLS = 4_000_000;

/** Longest common subsequence over two sentence lists, as index pairs. */
const lcsPairs = (a: string[], b: string[]): Array<[number, number]> => {
    const n = a.length;
    const m = b.length;
    const width = m + 1;
    // Lengths of the best match from each (i, j) onward, filled backwards so the
    // walk below can follow the larger option without re-deriving anything.
    const dp = new Uint32Array((n + 1) * width);

    for (let i = n - 1; i >= 0; i--) {
        for (let j = m - 1; j >= 0; j--) {
            dp[i * width + j] = a[i] === b[j]
                ? dp[(i + 1) * width + (j + 1)] + 1
                : Math.max(dp[(i + 1) * width + j], dp[i * width + (j + 1)]);
        }
    }

    const pairs: Array<[number, number]> = [];
    let i = 0;
    let j = 0;
    while (i < n && j < m) {
        if (a[i] === b[j]) {
            pairs.push([i, j]);
            i++;
            j++;
        } else if (dp[(i + 1) * width + j] >= dp[i * width + (j + 1)]) {
            i++;
        } else {
            j++;
        }
    }
    return pairs;
};

/**
 * Map the old sentences onto the new ones.
 *
 * Identical head and tail are matched off first. That is not just an
 * optimisation: a typical edit touches one paragraph, so stripping the
 * untouched ends usually leaves a handful of sentences to compare properly
 * however large the document is.
 */
export const alignSentences = (before: string[], after: string[]): SentenceAlignment => {
    const oldToNew: (number | null)[] = new Array(before.length).fill(null);

    let prefix = 0;
    while (prefix < before.length && prefix < after.length && before[prefix] === after[prefix]) {
        oldToNew[prefix] = prefix;
        prefix++;
    }

    if (prefix === before.length && prefix === after.length) {
        return { oldToNew, identical: true, changedCount: 0 };
    }

    let suffix = 0;
    while (
        suffix < before.length - prefix &&
        suffix < after.length - prefix &&
        before[before.length - 1 - suffix] === after[after.length - 1 - suffix]
    ) {
        oldToNew[before.length - 1 - suffix] = after.length - 1 - suffix;
        suffix++;
    }

    const oldMid = before.slice(prefix, before.length - suffix);
    const newMid = after.slice(prefix, after.length - suffix);
    let matchedInMiddle = 0;

    if (oldMid.length && newMid.length) {
        if (oldMid.length * newMid.length <= MAX_DIFF_CELLS) {
            for (const [i, j] of lcsPairs(oldMid, newMid)) {
                oldToNew[prefix + i] = prefix + j;
                matchedInMiddle++;
            }
        } else {
            // Too large to align properly - compare position by position, which
            // still recognises an edit that did not move anything.
            const shared = Math.min(oldMid.length, newMid.length);
            for (let k = 0; k < shared; k++) {
                if (oldMid[k] === newMid[k]) {
                    oldToNew[prefix + k] = prefix + k;
                    matchedInMiddle++;
                }
            }
        }
    }

    const changedCount = after.length - (prefix + suffix + matchedInMiddle);
    return { oldToNew, identical: false, changedCount: Math.max(0, changedCount) };
};

/**
 * Where a position in the old document should land in the new one.
 *
 * A surviving sentence keeps its place. One that was deleted hands over to the
 * nearest sentence after it, so the reader moves forward into the edit rather
 * than jumping backwards over text it has already read.
 */
export const remapIndex = (
    index: number,
    oldToNew: (number | null)[],
    newLength: number,
): number => {
    if (index < 0) return index;
    if (index >= oldToNew.length) return Math.min(index, newLength - 1);

    const direct = oldToNew[index];
    if (direct !== null) return direct;

    for (let i = index + 1; i < oldToNew.length; i++) {
        const mapped = oldToNew[i];
        if (mapped !== null) return mapped;
    }
    // Everything after was deleted too: fall back to the last sentence that
    // still exists before this point, then to the end of the document.
    for (let i = index - 1; i >= 0; i--) {
        const mapped = oldToNew[i];
        if (mapped !== null) return Math.min(mapped + 1, newLength - 1);
    }
    return Math.min(index, newLength - 1);
};
