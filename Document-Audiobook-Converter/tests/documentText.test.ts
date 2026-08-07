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
});
