const sha256 = async (input: string): Promise<string> => {
    const bytes = new TextEncoder().encode(input);
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
};

/** Identity for a document, stable across edits to its contents. */
export const makeDocumentId = (fileName: string): Promise<string> =>
    sha256(`name:${fileName.trim().toLowerCase()}`);

/** Reduce text to what is actually narrated before including it in a key. */
const normaliseForKey = (text: string): string => text.replace(/\s+/g, ' ').trim();

/** Identity for one clip: document, narrated words, voice and model. */
export const makeClipKey = async (args: {
    documentId: string; text: string; voice: string; model: string;
}): Promise<string> =>
    sha256([args.documentId, normaliseForKey(args.text), args.voice, args.model].join(' '));

/** The key used by the former position-based scheme, for adopting old clips. */
export const makeLegacyClipKey = async (args: {
    documentId: string; index: number; voice: string; model: string;
}): Promise<string> =>
    sha256([args.documentId, args.index, args.voice, args.model].join(' '));
