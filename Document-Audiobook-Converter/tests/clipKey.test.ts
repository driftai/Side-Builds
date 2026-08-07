import { describe, it, expect } from 'vitest';
import { makeClipKey, makeLegacyClipKey, makeDocumentId } from '../src/utils/audioCache';
import {
    isClipNarrationIdentityCompatible,
    NARRATION_CACHE_NORMALIZATION_VERSION,
} from '../src/utils/audioCache/identity';
import { NARRATION_POLICY_VERSION } from '../src/config/narrationPolicy';

/**
 * Clips are found by the words they narrate, not by where those words sit.
 *
 * Position was the obvious key and it cost real money: this document is edited
 * while it is being read, and inserting one line renumbers every passage below
 * it, so each of them missed its clip and was generated again.
 */
describe('makeClipKey', () => {
    const voice = 'Aoede';
    const model = 'gemini-2.5-flash-native-audio-preview-09-2025';
    const text = 'The lighthouse blinked twice across the bay.';

    it('gives a passage the same key wherever it has moved to', async () => {
        const documentId = await makeDocumentId('book.txt');
        // The same passage, before and after a line was inserted above it.
        const before = await makeClipKey({ documentId, text, voice, model });
        const after = await makeClipKey({ documentId, text, voice, model });
        expect(after).toBe(before);
    });

    it('gives edited words a different key, so old audio is not played as current', async () => {
        const documentId = await makeDocumentId('book.txt');
        const original = await makeClipKey({ documentId, text, voice, model });
        const edited = await makeClipKey({
            documentId, text: 'The lighthouse blinked once across the bay.', voice, model,
        });
        expect(edited).not.toBe(original);
    });

    it('ignores re-wrapping and indentation, which change nothing spoken', async () => {
        const documentId = await makeDocumentId('book.txt');
        const plain = await makeClipKey({ documentId, text, voice, model });
        const rewrapped = await makeClipKey({
            documentId, text: '  The lighthouse blinked\n  twice across the bay.  ', voice, model,
        });
        expect(rewrapped).toBe(plain);
    });

    it('separates voices and models, which sound different', async () => {
        const documentId = await makeDocumentId('book.txt');
        const base = await makeClipKey({ documentId, text, voice, model });
        expect(await makeClipKey({ documentId, text, voice: 'Puck', model })).not.toBe(base);
        expect(await makeClipKey({ documentId, text, voice, model: 'other-model' })).not.toBe(base);
    });

    it('separates delivery styles and policy versions', async () => {
        const documentId = await makeDocumentId('book.txt');
        const base = await makeClipKey({ documentId, text, voice, model });
        const styled = await makeClipKey({
            documentId, text, voice, model, styleInstructions: 'Read slowly.',
        });
        const anotherPolicy = await makeClipKey({
            documentId, text, voice, model, policyVersion: 'strict-verbatim-v3',
        });
        expect(styled).not.toBe(base);
        expect(anotherPolicy).not.toBe(base);
    });

    it('normalizes style whitespace before deriving identity', async () => {
        const documentId = await makeDocumentId('book.txt');
        const plain = await makeClipKey({
            documentId, text, voice, model, styleInstructions: 'slow and steady',
        });
        const spaced = await makeClipKey({
            documentId, text, voice, model, styleInstructions: '  slow\n and   steady ',
        });
        expect(spaced).toBe(plain);
    });

    it('separates documents that happen to share a line', async () => {
        const one = await makeClipKey({ documentId: await makeDocumentId('one.txt'), text, voice, model });
        const two = await makeClipKey({ documentId: await makeDocumentId('two.txt'), text, voice, model });
        expect(one).not.toBe(two);
    });

    it('still derives the old positional key, so existing clips can be adopted', async () => {
        const documentId = await makeDocumentId('book.txt');
        const legacy = await makeLegacyClipKey({ documentId, index: 4, voice, model });
        expect(legacy).toHaveLength(64);
        expect(legacy).not.toBe(await makeClipKey({ documentId, text, voice, model }));
        // Position still distinguishes them under the old scheme.
        expect(await makeLegacyClipKey({ documentId, index: 5, voice, model })).not.toBe(legacy);
    });
});

describe('legacy narration identity', () => {
    const current = {
        styleInstructions: 'Read steadily.',
        narrationPolicyVersion: NARRATION_POLICY_VERSION,
        cacheNormalizationVersion: NARRATION_CACHE_NORMALIZATION_VERSION,
    };

    it('refuses clips that cannot prove their policy and style', () => {
        expect(isClipNarrationIdentityCompatible({})).toBe(false);
        expect(isClipNarrationIdentityCompatible(current, {
            styleInstructions: 'Use a Southern cadence.',
        })).toBe(false);
        expect(isClipNarrationIdentityCompatible({
            ...current,
            narrationPolicyVersion: 'strict-verbatim-v1',
        }, { styleInstructions: current.styleInstructions })).toBe(false);
    });

    it('allows adoption only when every narration identity field matches', () => {
        expect(isClipNarrationIdentityCompatible(current, {
            styleInstructions: '  Read\n steadily. ',
        })).toBe(true);
    });
});

describe('makeDocumentId', () => {
    it('treats a file as the same document however its text changes', async () => {
        // Identity is the file name, which is what lets a document be edited
        // without orphaning everything generated for it.
        expect(await makeDocumentId('book.txt')).toBe(await makeDocumentId('book.txt'));
    });

    it('ignores case and surrounding space in the name', async () => {
        expect(await makeDocumentId(' Book.TXT ')).toBe(await makeDocumentId('book.txt'));
    });
});
