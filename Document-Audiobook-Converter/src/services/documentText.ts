import * as pdfjsLib from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { readDocxFile, readTextFile } from './documentReaders';

/**
 * Extensions understood by every document-entry path.
 *
 * Keeping one list prevents the file picker, validation, and live-file refresh
 * from silently drifting apart.
 */
export const SUPPORTED_DOCUMENT_TYPES = ['pdf', 'txt', 'docx'] as const;

export type SupportedDocumentType = (typeof SUPPORTED_DOCUMENT_TYPES)[number];

// Compatibility name historically exported by App.tsx.
export const SUPPORTED_TYPES: string[] = [...SUPPORTED_DOCUMENT_TYPES];

export const getDocumentType = (fileName: string): SupportedDocumentType | null => {
    const extension = fileName.split('.').pop()?.toLowerCase();
    return extension && SUPPORTED_DOCUMENT_TYPES.includes(extension as SupportedDocumentType)
        ? extension as SupportedDocumentType
        : null;
};

// Bundle the worker with the application. The former CDN-backed global failed
// offline and in packaged Electron builds, and leaked workers between uploads.
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

/**
 * Pull text out of a supported document without mutating reader state.
 *
 * Both initial loading and live-file refresh use this service; each caller owns
 * the state transition appropriate to that path.
 */
export const extractDocumentText = async (
    file: File,
    fileType: SupportedDocumentType,
): Promise<string> => {
    if (fileType === 'txt') return readTextFile(file);
    if (fileType === 'docx') return readDocxFile(file);
    if (fileType !== 'pdf') {
        throw new Error(`Unsupported document type: ${String(fileType)}`);
    }

    let fullText = '';
    const arrayBuffer = await file.arrayBuffer();
    const loadingTask = pdfjsLib.getDocument({ data: new Uint8Array(arrayBuffer) });
    const pdf = await loadingTask.promise;

    try {
        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
            const page = await pdf.getPage(pageNumber);
            const content = await page.getTextContent();
            let pageText = '';

            // Honour pdf.js end-of-line markers. Flattening every item with a
            // space welds headings onto the paragraph below and creates enormous
            // pseudo-sentences.
            for (const item of content.items as Array<{ str?: unknown; hasEOL?: boolean }>) {
                if (typeof item.str !== 'string') continue;
                pageText += item.str;
                pageText += item.hasEOL ? '\n' : ' ';
            }

            fullText += `${pageText}\n`;
            page.cleanup();
        }
    } finally {
        await loadingTask.destroy();
    }

    return fullText;
};
