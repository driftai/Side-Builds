import { describe, it, expect } from 'vitest';
import { alignSentences, remapIndex } from '../src/utils/documentDiff';

/**
 * Editing a document while it is being read must not throw away where the
 * listener is or what has already been generated. These cover the shapes that
 * broke it before: an edit in place, an insertion above the reader, a deletion,
 * and a document large enough that a naive comparison would crawl.
 */
describe('alignSentences', () => {
    const doc = ['one.', 'two.', 'three.', 'four.'];

    it('reports an unchanged document as identical', () => {
        const r = alignSentences(doc, doc);
        expect(r.identical).toBe(true);
        expect(r.changedCount).toBe(0);
        expect(r.oldToNew).toEqual([0, 1, 2, 3]);
    });

    it('marks only the edited sentence as changed', () => {
        const r = alignSentences(doc, ['one.', 'TWO CHANGED.', 'three.', 'four.']);
        expect(r.identical).toBe(false);
        expect(r.changedCount).toBe(1);
        expect(r.oldToNew[0]).toBe(0);
        expect(r.oldToNew[1]).toBeNull();          // rewritten, so unmatched
        expect(r.oldToNew.slice(2)).toEqual([2, 3]);
    });

    it('carries later sentences across an insertion instead of losing them', () => {
        const r = alignSentences(doc, ['zero.', ...doc]);
        expect(r.oldToNew).toEqual([1, 2, 3, 4]);
        expect(r.changedCount).toBe(1);
    });

    it('closes the gap left by a deletion', () => {
        const r = alignSentences(doc, ['one.', 'three.', 'four.']);
        expect(r.oldToNew[1]).toBeNull();
        expect(r.oldToNew.slice(2)).toEqual([1, 2]);
        expect(r.changedCount).toBe(0);            // nothing new, only removal
    });

    it('handles the document being emptied, and the first load', () => {
        expect(alignSentences(doc, []).oldToNew.every(v => v === null)).toBe(true);
        expect(alignSentences([], doc).oldToNew).toHaveLength(0);
    });

    it('stays exact and fast on a large document', () => {
        const big = Array.from({ length: 5000 }, (_, i) => `Sentence number ${i}.`);
        const edited = big.slice();
        edited[2500] = 'Sentence number 2500 but rewritten.';

        const started = Date.now();
        const r = alignSentences(big, edited);
        const took = Date.now() - started;

        expect(r.oldToNew.filter(v => v === null)).toHaveLength(1);
        expect(r.oldToNew[2500]).toBeNull();
        expect(r.oldToNew[4999]).toBe(4999);
        expect(took).toBeLessThan(500);
    });

    it('shifts a large document by one without losing anything', () => {
        const big = Array.from({ length: 5000 }, (_, i) => `Sentence number ${i}.`);
        const edited = [...big.slice(0, 100), 'Brand new line.', ...big.slice(100)];

        const started = Date.now();
        const r = alignSentences(big, edited);
        const took = Date.now() - started;

        expect(r.oldToNew.every(v => v !== null)).toBe(true);
        expect(r.oldToNew[100]).toBe(101);
        expect(r.oldToNew[4999]).toBe(5000);
        expect(took).toBeLessThan(500);
    });
});

describe('remapIndex', () => {
    const doc = ['one.', 'two.', 'three.', 'four.'];

    it('follows the reader across an insertion above it', () => {
        const { oldToNew } = alignSentences(doc, ['zero.', ...doc]);
        expect(remapIndex(2, oldToNew, 5)).toBe(3);
    });

    it('keeps the position of a rewritten passage, so it is not stepped over', () => {
        // The passage being read is edited: playback must resume *at* its
        // replacement, which is what the skip-after-edit fix turned on.
        const { oldToNew } = alignSentences(doc, ['one.', 'TWO REWRITTEN.', 'three.', 'four.']);
        expect(remapIndex(1, oldToNew, 4)).toBe(1);
    });

    it('moves onto the survivor when its passage was deleted', () => {
        const { oldToNew } = alignSentences(doc, ['one.', 'three.', 'four.']);
        expect(remapIndex(1, oldToNew, 3)).toBe(1);
    });

    it('clamps past the end of a shortened document', () => {
        const { oldToNew } = alignSentences(doc, ['one.']);
        expect(remapIndex(3, oldToNew, 1)).toBe(0);
    });

    it('leaves "nothing playing" alone', () => {
        expect(remapIndex(-1, [null], 3)).toBe(-1);
    });
});
