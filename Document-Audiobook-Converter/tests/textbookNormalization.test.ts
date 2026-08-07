import { describe, expect, it } from 'vitest';
import { splitIntoSentences } from '../src/utils/textProcessing';
import { normalizeTextbookText } from '../src/utils/textbookNormalization';

describe('textbook normalization', () => {
    it('repairs the extraction artifacts recorded in the textbook notes', () => {
        const extracted = [
            'The concept was not necessarily so to our scientific fore- bears.',
            'Explanations first posit the phenomenon in ques- tion to be regular.',
            'F R O M A P E T O A L E X A N D E R',
            'Aristo- tle used a man- ual while Coperni-cus studied the sky.',
        ].join('\n');

        const normalized = normalizeTextbookText(extracted);
        expect(normalized).toContain('scientific forebears.');
        expect(normalized).toContain('question to be regular.');
        expect(normalized).toContain('FROM APE TO ALEXANDER');
        expect(normalized).toContain('Aristotle used a manual while Copernicus');
    });

    it('repairs soft and line-break hyphenation without changing real compounds', () => {
        const extracted = 'tra-\ndition co\u00adoperate well-known mother-in-law state-of-the-art well- known';
        expect(normalizeTextbookText(extracted)).toBe(
            'tradition cooperate well-known mother-in-law state-of-the-art well- known',
        );
    });

    it('unwraps line-wrapped compounds without deleting their meaningful hyphens', () => {
        const extracted = 'A cost-\neffective policy supports decision-\nmaking and tra-\ndition.';
        expect(normalizeTextbookText(extracted)).toBe(
            'A cost-effective policy supports decision-making and tradition.',
        );
    });

    it('removes known service metadata and can replace it with one marker', () => {
        const metadata = [
            'Opening paragraph.',
            '( EBSCOhost: eBook Collection (EBSCOhost) printed on 9/5/2025 5:16:20 PM UTC via SUNY POLYTECHNIC INSTITUTE. All use subject to https://www. ebsco. com/terms-of-use. )',
            'https://www. ebsco. com/terms-of-use.',
            '(Source: Vitas/Fotolia)',
            'Closing paragraph.',
        ].join('\n');

        const removed = normalizeTextbookText(metadata);
        expect(removed).toBe('Opening paragraph.\nClosing paragraph.');
        const replaced = normalizeTextbookText(metadata, { metadataReplacement: 'Filler' });
        expect(replaced).toBe('Opening paragraph.\nFiller\nFiller\nFiller\nClosing paragraph.');
    });

    it('preserves isolated content, list numbering, equations, and ambiguous letter runs', () => {
        const content = [
            'E',
            '110',
            '7. Calculate I_c, the moment of inertia. 8.',
            '∫y(dA) = L_c*A',
            'A B C D',
        ].join('\n');
        expect(normalizeTextbookText(content)).toBe(content);
    });

    it('keeps every long passage at 600 characters or less without losing words', () => {
        const phrase = 'This preserved textbook passage includes number 7 and equation x + y = z in one continuous thought';
        const longPassage = Array.from({ length: 20 }, () => phrase).join(' ');
        const passages = splitIntoSentences(normalizeTextbookText(longPassage));

        expect(passages.length).toBeGreaterThan(1);
        expect(passages.every(passage => passage.length <= 600)).toBe(true);
        expect(passages.join(' ')).toBe(longPassage);
    });
});
