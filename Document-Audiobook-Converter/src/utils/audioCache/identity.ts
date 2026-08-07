import {
    NARRATION_POLICY_VERSION,
    normalizeNarrationStyle,
} from '../../config/narrationPolicy';
import type { ClipMeta } from './types';

/** Bump whenever text/style normalization or key field ordering changes. */
export const NARRATION_CACHE_NORMALIZATION_VERSION = 'narration-cache-v2';

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

interface NarrationIdentityOptions {
    styleInstructions?: string;
    policyVersion?: string;
    normalizationVersion?: string;
}

const resolvedNarrationIdentity = (options: NarrationIdentityOptions) => ({
    styleInstructions: normalizeNarrationStyle(options.styleInstructions),
    policyVersion: options.policyVersion ?? NARRATION_POLICY_VERSION,
    normalizationVersion: options.normalizationVersion
        ?? NARRATION_CACHE_NORMALIZATION_VERSION,
});

/** Identity for one clip, including every input that can change its delivery. */
export const makeClipKey = async (args: {
    documentId: string; text: string; voice: string; model: string;
} & NarrationIdentityOptions): Promise<string> => {
    const identity = resolvedNarrationIdentity(args);
    return sha256(JSON.stringify([
        identity.normalizationVersion,
        identity.policyVersion,
        args.documentId,
        normaliseForKey(args.text),
        args.voice,
        args.model,
        identity.styleInstructions,
    ]));
};

/** Legacy metadata must prove it used the exact current narration identity. */
export const isClipNarrationIdentityCompatible = (
    meta: Pick<ClipMeta,
        'styleInstructions' | 'narrationPolicyVersion' | 'cacheNormalizationVersion'>,
    options: NarrationIdentityOptions = {},
): boolean => {
    const identity = resolvedNarrationIdentity(options);
    return meta.cacheNormalizationVersion === identity.normalizationVersion
        && meta.narrationPolicyVersion === identity.policyVersion
        && normalizeNarrationStyle(meta.styleInstructions) === identity.styleInstructions;
};

/** The key used by the former position-based scheme, for adopting old clips. */
export const makeLegacyClipKey = async (args: {
    documentId: string; index: number; voice: string; model: string;
}): Promise<string> =>
    sha256([args.documentId, args.index, args.voice, args.model].join(' '));
