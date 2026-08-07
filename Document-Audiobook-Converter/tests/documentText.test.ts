import { describe, expect, it, vi } from 'vitest';

// The facade configures browser-only PDF/DOCX readers at module load. These
// tests exercise its type routing, so keep Node out of the rendering runtimes.
vi.mock('pdfjs-dist', () => ({
    GlobalWorkerOptions: { workerSrc: '' },
    getDocument: vi.fn(),
}));
vi.mock('pdfjs-dist/build/pdf.worker.min.mjs?url', () => ({
    default: 'pdf-worker.mjs',
}));
vi.mock('mammoth/mammoth.browser', () => ({
    default: { extractRawText: vi.fn() },
}));
import * as pdfjsLib from 'pdfjs-dist';
import {
    extractDocumentText,
    getDocumentType,
    SUPPORTED_TYPES,
} from '../src/services/documentText';

describe('document text facade', () => {
    it('keeps validation and the compatibility list aligned', () => {
        expect(SUPPORTED_TYPES).toEqual(['pdf', 'txt', 'docx']);
        expect(getDocumentType('book.PDF')).toBe('pdf');
        expect(getDocumentType('notes.txt')).toBe('txt');
        expect(getDocumentType('draft.final.docx')).toBe('docx');
        expect(getDocumentType('archive.zip')).toBeNull();
        expect(getDocumentType('no-extension')).toBeNull();
    });

    it('rejects an invalid runtime type before treating it as a PDF', async () => {
        await expect(extractDocumentText(
            {} as File,
            'epub' as never,
        )).rejects.toThrow('Unsupported document type: epub');
    });

    it('filters marked-content sentinels and normalizes the extracted PDF text', async () => {
        const cleanup = vi.fn();
        const destroy = vi.fn().mockResolvedValue(undefined);
        vi.mocked(pdfjsLib.getDocument).mockReturnValue({
            promise: Promise.resolve({
                numPages: 1,
                getPage: vi.fn().mockResolvedValue({
                    getTextContent: vi.fn().mockResolvedValue({
                        items: [
                            { type: 'beginMarkedContent', id: 'chapter' },
                            {
                                str: 'dition began.', dir: 'ltr', transform: [12, 0, 0, 12, 40, 680],
                                width: 90, height: 12, fontName: 'Body', hasEOL: true,
                            },
                            {
                                str: 'tra-', dir: 'ltr', transform: [12, 0, 0, 12, 40, 700],
                                width: 25, height: 12, fontName: 'Body', hasEOL: true,
                            },
                        ],
                    }),
                    cleanup,
                }),
            }),
            destroy,
        } as never);

        const file = { arrayBuffer: vi.fn().mockResolvedValue(new ArrayBuffer(8)) } as unknown as File;
        await expect(extractDocumentText(file, 'pdf')).resolves.toBe('tradition began.');
        expect(cleanup).toHaveBeenCalledOnce();
        expect(destroy).toHaveBeenCalledOnce();
    });
});
