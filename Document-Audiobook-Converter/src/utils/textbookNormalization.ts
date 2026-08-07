export interface TextbookNormalizationOptions {
    /** Empty removes known metadata; a value such as "Filler" replaces it. */
    metadataReplacement?: string;
}

const HEADING_WORDS = new Set([
    'a', 'after', 'alexander', 'alexandria', 'and', 'ape', 'beyond', 'chapter',
    'europe', 'from', 'ganges', 'guns', 'history', 'indus', 'kingdom', 'middle',
    'of', 'part', 'pharaohs', 'plagues', 'plows', 'science', 'section', 'solar',
    'stirrups', 'system', 'the', 'to', 'world',
]);

const PRESERVED_COMPOUNDS = new Set([
    'cost-effective', 'decision-making', 'evidence-based', 'first-class',
    'full-time', 'half-life', 'high-quality', 'ice-cream', 'long-term',
    'low-level', 'mother-in-law', 'north-east', 'part-time', 'peer-reviewed',
    'real-time', 'self-aware', 'short-term', 'state-of-the-art', 'user-facing',
    'well-known', 'world-wide',
]);

const KNOWN_BROKEN_WORDS = new Set([
    'aristo-tle', 'coperni-cus', 'exam-ple', 'fore-bears', 'man-ual',
    'pre-determined', 'ques-tion', 'tra-dition',
]);

const REMOVED_METADATA = '\uE000';

const replacementText = (replacement: string): string =>
    replacement ? ` ${replacement} ` : REMOVED_METADATA;

const removeKnownMetadata = (text: string, replacement: string): string => {
    const replacementValue = replacementText(replacement);
    return text
        .replace(/\([^)]*(?:EBSCOhost|eBook Collection)[^)]*\)/giu, replacementValue)
        .replace(/\((?:Source|Credit)\s*:[^)]*\)/giu, replacementValue)
        .replace(/^.*(?:EBSCOhost\s*:|eBook Collection\s*\(EBSCOhost\)|printed on .* UTC via .*|All use subject to .*ebsco).*$/gimu, replacementValue)
        .replace(/https?:\/\/(?:www\.\s*)?ebsco\.\s*com\/terms-of-use\.?/giu, replacementValue)
        .replace(/https?:\/\/[^\s)\]}]+/giu, replacementValue);
};

const shouldJoinFragment = (left: string, right: string): boolean => {
    const pair = `${left}-${right}`.toLocaleLowerCase();
    if (PRESERVED_COMPOUNDS.has(pair)) return false;
    if (!/^\p{Ll}/u.test(right)) return false;
    return KNOWN_BROKEN_WORDS.has(pair);
};

const repairHyphenation = (text: string): string => {
    return text
        .replace(
            /([\p{L}]{2,})-[ \t]*\n[ \t]*([\p{L}]{2,})/gu,
            (_match, left: string, right: string) =>
                shouldJoinFragment(left, right) ? `${left}${right}` : `${left}-${right}`,
        )
        .replace(
            /([\p{L}]{2,})-([ \t]+)([\p{L}]{2,})/gu,
            (match, left: string, _separator: string, right: string) =>
                shouldJoinFragment(left, right) ? `${left}${right}` : match,
        )
        .replace(/\b([\p{L}]{2,})-([\p{Ll}]{2,})\b/gu, (match, left: string, right: string) =>
            KNOWN_BROKEN_WORDS.has(`${left}-${right}`.toLocaleLowerCase()) ? `${left}${right}` : match,
        );
};

const segmentHeading = (joined: string): string[] | null => {
    const lower = joined.toLocaleLowerCase();
    const memo = new Map<number, string[][]>();

    const visit = (start: number): string[][] => {
        if (start === lower.length) return [[]];
        if (memo.has(start)) return memo.get(start)!;
        const results: string[][] = [];
        for (let end = start + 1; end <= lower.length; end++) {
            const word = lower.slice(start, end);
            if (!HEADING_WORDS.has(word)) continue;
            for (const rest of visit(end)) {
                results.push([joined.slice(start, end), ...rest]);
                if (results.length > 2) break;
            }
        }
        memo.set(start, results);
        return results;
    };

    const candidates = visit(0)
        .filter(words => words.length > 0)
        .sort((a, b) => a.length - b.length);
    if (!candidates.length) return null;
    const best = candidates[0];
    const next = candidates[1];
    if (next && next.length === best.length) return null;
    return best;
};

const collapseLetterSpacedHeadings = (text: string): string => text.replace(
    /(?<!\p{L})(?:\p{Lu}[ \t]+){3,}\p{Lu}(?!\p{L})/gu,
    match => {
        const joined = match.replace(/\s+/g, '');
        const words = segmentHeading(joined);
        return words ? words.join(' ') : match;
    },
);

/**
 * Repair high-confidence textbook extraction artifacts without paraphrasing.
 * Numbers, isolated letters, equations, list markers, and ordinary hyphenated
 * compounds are deliberately left intact.
 */
export const normalizeTextbookText = (
    input: string,
    options: TextbookNormalizationOptions = {},
): string => {
    const metadataReplacement = options.metadataReplacement ?? '';
    let text = input.replace(/\r\n?/g, '\n').replace(/\u00ad/g, '');
    text = removeKnownMetadata(text, metadataReplacement);
    text = repairHyphenation(text);
    text = collapseLetterSpacedHeadings(text);
    return text
        .split('\n')
        .filter(line => line.trim() !== REMOVED_METADATA)
        .map(line => line.replaceAll(REMOVED_METADATA, ''))
        .map(line => line.replace(/[ \t]+/g, ' ').trim())
        .join('\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
};
