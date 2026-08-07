import { describe, expect, it } from 'vitest';
import {
    combinePdfPages,
    extractPdfPageText,
    type PdfPageText,
    type PdfTextItemLike,
} from '../src/services/pdfTextLayout';

const item = (
    str: string,
    x: number,
    y: number,
    width: number,
    hasEOL = true,
): PdfTextItemLike => ({
    str,
    dir: 'ltr',
    transform: [12, 0, 0, 12, x, y],
    width,
    height: 12,
    fontName: 'TextbookBody',
    hasEOL,
});

describe('positional PDF text layout', () => {
    it('orders a single column by page coordinates instead of internal item order', () => {
        const page = extractPdfPageText([
            item('Second line.', 40, 680, 180),
            item('First line.', 40, 720, 160),
        ]);

        expect(page.usedPositionalLayout).toBe(true);
        expect(page.text).toBe('First line.\nSecond line.');
    });

    it('reads each column top-to-bottom beneath a full-width heading', () => {
        const page = extractPdfPageText([
            item('Right second.', 320, 680, 150),
            item('Left first.', 30, 700, 150),
            item('A HISTORY OF SCIENCE', 20, 760, 460),
            item('Right first.', 320, 700, 150),
            item('Left second.', 30, 680, 150),
            item('Chapter footer', 20, 40, 460),
        ]);

        expect(page.usedPositionalLayout).toBe(true);
        expect(page.lines).toEqual([
            'A HISTORY OF SCIENCE',
            'Left first.',
            'Left second.',
            'Right first.',
            'Right second.',
            'Chapter footer',
        ]);
    });

    it('does not mistake vertically separate, offset blocks for columns', () => {
        const page = extractPdfPageText([
            item('Lower left second.', 30, 280, 150),
            item('Upper right first.', 320, 700, 150),
            item('Lower left first.', 30, 300, 150),
            item('Upper right second.', 320, 680, 150),
        ]);

        expect(page.lines).toEqual([
            'Upper right first.',
            'Upper right second.',
            'Lower left first.',
            'Lower left second.',
        ]);
    });

    it('falls back to pdf.js EOL markers when coordinates are incomplete', () => {
        const page = extractPdfPageText([
            { str: 'First fallback line.', hasEOL: true },
            { str: 'Second fallback line.', hasEOL: false },
        ]);

        expect(page.usedPositionalLayout).toBe(false);
        expect(page.text).toBe('First fallback line.\nSecond fallback line.');
    });

    it('falls back for vertically oriented text instead of guessing its reading order', () => {
        const page = extractPdfPageText([
            { ...item('Vertical first.', 40, 700, 100), dir: 'ttb', transform: [0, 12, -12, 0, 40, 700] },
            { ...item('Vertical second.', 40, 600, 110), dir: 'ttb', transform: [0, 12, -12, 0, 40, 600] },
        ]);

        expect(page.usedPositionalLayout).toBe(false);
        expect(page.text).toBe('Vertical first.\nVertical second.');
    });

    it('removes only repeated outer-margin lines across three or more pages', () => {
        const page = (number: number, body: string): PdfPageText => ({
            text: '',
            lines: ['History of Science', body, String(number)],
            confidence: 1,
            usedPositionalLayout: true,
        });
        const combined = combinePdfPages([
            page(58, 'Thales lived in Miletus.'),
            page(59, 'Anaximander followed him.'),
            page(60, 'The account continues here.'),
        ]);

        expect(combined).toBe([
            'Thales lived in Miletus.',
            'Anaximander followed him.',
            'The account continues here.',
        ].join('\n\n'));
    });

    it('preserves distinct numbered headings while removing pure page numbers', () => {
        const page = (chapter: number, body: string, pageNumber: number): PdfPageText => ({
            text: '',
            lines: [`Chapter ${chapter}`, body, String(pageNumber)],
            confidence: 1,
            usedPositionalLayout: true,
        });
        const combined = combinePdfPages([
            page(1, 'Origins of astronomy.', 11),
            page(2, 'Classical mechanics.', 29),
            page(3, 'Modern cosmology.', 47),
        ]);

        expect(combined).toBe([
            'Chapter 1\nOrigins of astronomy.',
            'Chapter 2\nClassical mechanics.',
            'Chapter 3\nModern cosmology.',
        ].join('\n\n'));
    });

    it('does not remove an isolated numeric content line from an outer position', () => {
        const page = (lines: string[]): PdfPageText => ({
            text: '',
            lines,
            confidence: 1,
            usedPositionalLayout: true,
        });
        const combined = combinePdfPages([
            page(['1', 'A numbered section begins here.', 'First footer']),
            page(['Chapter Two', 'Its body continues.', 'Second footer']),
            page(['Chapter Three', 'The final body.', 'Third footer']),
        ]);

        expect(combined).toContain('1\nA numbered section begins here.');
    });

    it('still removes exact repeated footer text', () => {
        const page = (heading: string, body: string): PdfPageText => ({
            text: '',
            lines: [heading, body, 'History of Science'],
            confidence: 1,
            usedPositionalLayout: true,
        });
        const combined = combinePdfPages([
            page('Chapter 1', 'Origins of astronomy.'),
            page('Chapter 2', 'Classical mechanics.'),
            page('Chapter 3', 'Modern cosmology.'),
        ]);

        expect(combined).toBe([
            'Chapter 1\nOrigins of astronomy.',
            'Chapter 2\nClassical mechanics.',
            'Chapter 3\nModern cosmology.',
        ].join('\n\n'));
    });
});
