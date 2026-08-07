import { describe, it, expect } from 'vitest';
import { narratableText, isNarratable, splitIntoSentences } from '../src/utils/textProcessing';

/**
 * Stat blocks and scene breaks carry rules like "-------------". Sent to the
 * model as-is they come back with no audio at all, which used to surface as
 * "No audio data received" and stop the book.
 */
describe('narratable text', () => {
    // As pasted from a real document: the run mixes ASCII hyphens with U+2010.
    const RULE = '---------------------------‐--';

    it('treats a bare rule as having nothing to say', () => {
        expect(isNarratable(RULE)).toBe(false);
        expect(narratableText(RULE)).toBe('');
    });

    it('catches short rules and mixed dash characters', () => {
        expect(isNarratable('-----------')).toBe(false);
        expect(isNarratable('---‐‐---–—--')).toBe(false);
    });

    it('reads a passage that merely opens with a rule', () => {
        const opening = `${RULE} Name: Leon kirumi Race: Human`;
        expect(isNarratable(opening)).toBe(true);
        expect(narratableText(opening)).toBe('Name: Leon kirumi Race: Human');
    });

    it('keeps the content of a stat block while dropping its rules', () => {
        const block = [RULE, 'Name: Leon kirumi', 'Race: Human', '-----------',
            'ATK:200 MD:200 INT:50 AGI:80', '------------------------------'].join('\n');
        const spoken = narratableText(block);
        expect(isNarratable(block)).toBe(true);
        expect(spoken).not.toMatch(/-{3,}/);
        expect(spoken).toContain('Name: Leon kirumi');
        expect(spoken).toContain('ATK:200');
    });

    it('leaves ordinary prose exactly as it is', () => {
        const prose = 'Leon started laughing like it was a joke being played on him.';
        expect(narratableText(prose)).toBe(prose);
    });

    it('keeps hyphenation and a lone dash, which are real punctuation', () => {
        const line = 'The well-known man stopped — then turned back.';
        expect(narratableText(line)).toBe(line);
    });

    it('does not silence a passage for an ellipsis', () => {
        expect(isNarratable('He waited... then spoke.')).toBe(true);
    });
});

describe('splitIntoSentences', () => {
    it('keeps an abbreviation with the name that follows it', () => {
        // "Mr. | Teke" used to be split across two requests.
        const parts = splitIntoSentences('Mr. Teke opened the door. Then he left.');
        expect(parts.some(p => p.includes('Mr. Teke'))).toBe(true);
    });

    it('produces passages that are each either speakable or a pure rule', () => {
        const doc = ['The lighthouse blinked twice across the bay.', '---------------------------',
            'The road down to the water was still wet.'].join('\n\n');
        const parts = splitIntoSentences(doc);
        expect(parts.length).toBeGreaterThan(0);
        expect(parts.every(p => isNarratable(p) || narratableText(p) === '')).toBe(true);
    });
});
