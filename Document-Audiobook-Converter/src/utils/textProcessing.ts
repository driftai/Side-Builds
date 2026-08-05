
/**
 * Longest passage handed to the TTS engine in one request, in characters.
 *
 * ~600 characters is roughly 45 seconds of narration. The cap exists because
 * the sentence splitter can only break on punctuation, and real prose does not
 * always supply it - a run-on paragraph ("...which was noticeable As the man
 * moved...") arrives as one 1,900-character "sentence", i.e. a two-minute
 * single request. That is fragile in every direction: slow to first audio, a
 * large amount of work to lose if the turn fails, and long enough to run into
 * model output limits. Splitting it keeps every request a comfortable size and
 * gives the prefetch queue finer granularity to work with.
 */
const MAX_CHUNK_CHARS = 600;

// Titles and abbreviations whose trailing period is not a sentence end. This
// pass runs after the main splitter has already restored its placeholders, so
// without guarding them here "Mr. Teke" splits into "...specifically Mr." and
// "Teke at the moment...", which narrates as a cut-off name across two requests.
const ABBREVIATIONS = [
    'Mr', 'Mrs', 'Ms', 'Dr', 'Prof', 'Sr', 'Jr', 'St', 'Mt', 'Lt', 'Sgt', 'Capt',
    'Gen', 'Rev', 'Hon', 'etc', 'vs', 'cf', 'al', 'Fig', 'Eq', 'No', 'pp', 'pg',
    'Vol', 'Ch', 'Sec', 'Inc', 'Ltd', 'Corp', 'Co', 'Approx', 'Dept', 'Est',
].join('|');

// Whitespace after sentence-ending punctuation, but not after an abbreviation
// ("Mr. Teke") or a single-letter initial ("J. Smith").
const SENTENCE_BOUNDARY = new RegExp(
    `(?<!\\b(?:${ABBREVIATIONS})\\.)(?<!\\b[A-Z]\\.)(?<=[.!?]["'”’)\\]]?)\\s+`
);

/**
 * Where a long passage may be broken, best first. Each is a point a narrator
 * would naturally pause, so the seams are not audible.
 */
const PASSAGE_SPLIT_PATTERNS: RegExp[] = [
    SENTENCE_BOUNDARY,      // end of a sentence, keeping any closing quote
    /\n+/,                  // paragraph and line breaks
    /(?<=["”])\s+/,         // after closing dialogue quotes
    /(?<=[;:—])\s+/,        // semicolon, colon, em dash
    /(?<=,)\s+/,            // commas, last resort before hard wrapping
];

/** Break at word boundaries when no punctuation offers a seam. */
const hardWrap = (text: string, max: number): string[] => {
    const out: string[] = [];
    let rest = text.trim();
    while (rest.length > max) {
        let cut = rest.lastIndexOf(' ', max);
        if (cut <= 0) cut = max;  // one enormous unbroken token
        out.push(rest.slice(0, cut).trim());
        rest = rest.slice(cut).trim();
    }
    if (rest) out.push(rest);
    return out;
};

/**
 * Split one over-long passage into speakable chunks, trying progressively
 * weaker boundaries. Lossless apart from whitespace between pieces.
 */
const splitLongPassage = (text: string, max: number = MAX_CHUNK_CHARS, depth = 0): string[] => {
    const trimmed = text.trim();
    if (trimmed.length <= max) return trimmed ? [trimmed] : [];
    if (depth >= PASSAGE_SPLIT_PATTERNS.length) return hardWrap(trimmed, max);

    const pieces = trimmed.split(PASSAGE_SPLIT_PATTERNS[depth]).map(p => p.trim()).filter(Boolean);
    if (pieces.length <= 1) return splitLongPassage(trimmed, max, depth + 1);

    // Re-pack the pieces so chunks land near the cap rather than being tiny.
    const out: string[] = [];
    let current = '';
    const flush = () => { if (current) { out.push(current); current = ''; } };

    for (const piece of pieces) {
        if (piece.length > max) {
            flush();
            out.push(...splitLongPassage(piece, max, depth + 1));
            continue;
        }
        const candidate = current ? `${current} ${piece}` : piece;
        if (candidate.length <= max) {
            current = candidate;
        } else {
            flush();
            current = piece;
        }
    }
    flush();
    return out;
};

/**
 * Improved sentence segmentation function
 */
export const splitIntoSentences = (text: string): string[] => {
    // First, handle decimal numbers by temporarily replacing them
    const decimalNumberPattern = /\b\d+\.\d+\b/g;
    const decimalPlaceholders: string[] = [];
    let placeholderIndex = 0;

    const textWithDecimalPlaceholders = text.replace(decimalNumberPattern, (match) => {
        const placeholder = `__DECIMAL_${placeholderIndex}__`;
        decimalPlaceholders.push(match);
        placeholderIndex++;
        return placeholder;
    });

    // Handle common abbreviations by temporarily replacing them
    const abbreviationPattern = /\b(?:Mr|Mrs|Dr|Prof|Sr|Jr|Inc|Ltd|Corp|Co|Ltd|etc|e\.g|i\.e|vs|cf|et al|al|Fig|Figure|Table|Eq|Equation|Section|Chapter|Appendix|Vol|Volume|No|Number|pp|pg|para|par)\./g;
    const abbreviationPlaceholders: string[] = [];
    let abbrevIndex = 0;

    const textWithAbbrevPlaceholders = textWithDecimalPlaceholders.replace(abbreviationPattern, (match) => {
        const placeholder = `__ABBREV_${abbrevIndex}__`;
        abbreviationPlaceholders.push(match);
        abbrevIndex++;
        return placeholder;
    });

    // Handle middle initials in names (e.g., "Jay H. Matternes")
    // Pattern: word + single letter + period + space + word (not followed by lowercase)
    const middleInitialPattern = /\b([A-Z][a-z]+)\s+([A-Z])\.\s+([A-Z][a-z]+)\b/g;
    const namePlaceholders: string[] = [];
    let nameIndex = 0;

    const textWithNamePlaceholders = textWithAbbrevPlaceholders.replace(middleInitialPattern, (match) => {
        const placeholder = `__NAME_${nameIndex}__`;
        namePlaceholders.push(match);
        nameIndex++;
        return placeholder;
    });

    // Handle single initial + last name patterns (e.g., "J. Smith")
    const singleInitialPattern = /\b([A-Z])\.\s+([A-Z][a-z]+)\b/g;
    const singleInitialPlaceholders: string[] = [];
    let singleIndex = 0;

    const textWithAllPlaceholders = textWithNamePlaceholders.replace(singleInitialPattern, (match) => {
        const placeholder = `__SINGLE_${singleIndex}__`;
        singleInitialPlaceholders.push(match);
        singleIndex++;
        return placeholder;
    });

    // Now split on sentence boundaries (periods followed by space and capital letter)
    let sentences = textWithAllPlaceholders.split(/(?<=[.!?])\s+(?=[A-Z])/g);

    // Restore all placeholders
    sentences = sentences.map(sentence => {
        let result = sentence;
        // Restore abbreviations
        result = result.replace(/__ABBREV_(\d+)__/g, (match, index) => {
            return abbreviationPlaceholders[parseInt(index)] || match;
        });
        // Restore decimal numbers
        result = result.replace(/__DECIMAL_(\d+)__/g, (match, index) => {
            return decimalPlaceholders[parseInt(index)] || match;
        });
        // Restore full names
        result = result.replace(/__NAME_(\d+)__/g, (match, index) => {
            return namePlaceholders[parseInt(index)] || match;
        });
        // Restore single initials + last names
        result = result.replace(/__SINGLE_(\d+)__/g, (match, index) => {
            return singleInitialPlaceholders[parseInt(index)] || match;
        });
        return result;
    });

    // Post-process to handle any remaining edge cases
    const finalSentences: string[] = [];
    for (let i = 0; i < sentences.length; i++) {
        const sentence = sentences[i].trim();
        if (sentence.length === 0) continue;

        // Check if this is just a placeholder that got split
        if (sentence.match(/^__\w+__\.$/) && i > 0) {
            // Merge with previous sentence
            finalSentences[finalSentences.length - 1] += ' ' + sentence;
        } else {
            finalSentences.push(sentence);
        }
    }

    // Drop fragments with nothing speakable in them.
    //
    // Real PDFs are full of bare page numbers, rule characters and stray
    // punctuation, and the splitter happily emits each as its own "sentence".
    // Sending one to the Live API returns an empty turn, which surfaced as
    // "No audio chunks were received before transcription" and - because
    // playSentence treats a generation failure as fatal - could pause an entire
    // book on a page number. Requiring at least one letter removes them.
    //
    // \p{L} rather than [a-z]: this has to keep Japanese and other non-Latin
    // scripts, which are otherwise entirely letterless to a Latin-only test.
    const hasSpeakableContent = (s: string) => /\p{L}/u.test(s);

    // Finally, break anything still too long to narrate in one request.
    return finalSentences
        .filter(s => s.length > 0 && hasSpeakableContent(s))
        .flatMap(s => splitLongPassage(s))
        .filter(s => s.length > 0 && hasSpeakableContent(s));
};

export const handleTxtFile = async (file: File): Promise<string> => {
    const reader = new FileReader();
    return new Promise<string>((resolve, reject) => {
        reader.onload = (e) => {
            const textContent = e.target?.result as string;
            resolve(textContent);
        };
        reader.onerror = () => reject(new Error('Failed to read text file'));
        reader.readAsText(file);
    });
};

// mammoth's browser bundle. Previously this was a global provided by a
// <script> tag pointing at mammoth 1.4.2 on cdnjs, which meant .docx support
// silently depended on a network fetch and on a build from 2021.
import mammoth from 'mammoth/mammoth.browser';

export const handleDocxFile = async (file: File): Promise<string> => {
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    return result.value;
};

// --- what can actually be spoken -------------------------------------------

/**
 * Runs of rule characters used as visual dividers.
 *
 * Deliberately a character class rather than a repeated single character:
 * dividers pasted from elsewhere mix ASCII hyphens with U+2010, en and em
 * dashes, so matching one repeated character leaves stragglers behind.
 */
const DIVIDER_RUN = /[-=_*~+#|<>.‐‑‒–—―·•●─-╿]{3,}/gu;

/**
 * The passage as it should be read aloud, with visual furniture removed.
 *
 * A stat block or scene break carries rules like `---------------` that mean
 * something on the page and nothing in speech. Sent as-is they are worse than
 * useless: the Live model returns a turn with no audio in it at all, which
 * surfaces as "No audio data received" and stops the book.
 */
export const narratableText = (text: string): string =>
    text.replace(DIVIDER_RUN, ' ').replace(/\s+/g, ' ').trim();

/** Is there anything here worth sending to be spoken? */
export const isNarratable = (text: string): boolean =>
    /[\p{L}\p{N}]/u.test(narratableText(text));
