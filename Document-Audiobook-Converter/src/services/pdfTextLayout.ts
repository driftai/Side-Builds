/**
 * The public subset of pdf.js TextItem metadata used by the layout reader.
 * Keeping this structural avoids depending on pdf.js internal item classes.
 */
export interface PdfTextItemLike {
    str: string;
    dir?: string;
    transform?: ArrayLike<number>;
    width?: number;
    height?: number;
    fontName?: string;
    hasEOL?: boolean;
}

/** Distinguish pdf.js TextItem records from TextMarkedContent sentinels. */
export const isPdfTextItemLike = <T>(item: T): item is T & PdfTextItemLike =>
    typeof item === 'object'
    && item !== null
    && typeof (item as { str?: unknown }).str === 'string';

export interface PdfPageText {
    text: string;
    lines: string[];
    confidence: number;
    usedPositionalLayout: boolean;
}

interface PositionedItem {
    text: string;
    x: number;
    y: number;
    width: number;
    fontSize: number;
    dir: string;
}

interface LayoutLine {
    items: PositionedItem[];
    text: string;
    y: number;
    minX: number;
    maxX: number;
    fontSize: number;
}

const median = (values: number[]): number => {
    if (!values.length) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

const fallbackEolText = (items: PdfTextItemLike[]): string => {
    let text = '';
    for (const item of items) {
        if (typeof item.str !== 'string') continue;
        text += item.str;
        text += item.hasEOL ? '\n' : ' ';
    }
    return text.replace(/[ \t]+\n/g, '\n').trim();
};

const toPositionedItem = (item: PdfTextItemLike): PositionedItem | null => {
    if (typeof item.str !== 'string' || !item.str.trim()) return null;
    const transform = item.transform;
    if (!transform || transform.length < 6) return null;

    const x = Number(transform[4]);
    const y = Number(transform[5]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;

    const horizontalScale = Math.abs(Number(transform[0]) || 0);
    const verticalSkew = Math.abs(Number(transform[1]) || 0);
    if (item.dir === 'ttb' || verticalSkew > Math.max(0.5, horizontalScale * 0.5)) return null;

    const transformHeight = Math.hypot(Number(transform[2]) || 0, Number(transform[3]) || 0);
    const transformWidth = Math.hypot(Number(transform[0]) || 0, Number(transform[1]) || 0);
    const fontSize = Math.abs(Number(item.height)) || transformHeight || transformWidth;
    if (!Number.isFinite(fontSize) || fontSize <= 0) return null;

    const suppliedWidth = Math.abs(Number(item.width));
    const estimatedWidth = item.str.trim().length * fontSize * 0.52;
    const width = Number.isFinite(suppliedWidth) && suppliedWidth > 0 ? suppliedWidth : estimatedWidth;

    return {
        text: item.str.trim(),
        x,
        y,
        width,
        fontSize,
        dir: item.dir || 'ltr',
    };
};

const renderLine = (items: PositionedItem[], fontSize: number): string => {
    const rtl = items.filter(item => item.dir === 'rtl').length > items.length / 2;
    const ordered = [...items].sort((a, b) => rtl ? b.x - a.x : a.x - b.x);
    let output = '';
    let previous: PositionedItem | null = null;

    for (const item of ordered) {
        if (previous) {
            const gap = rtl
                ? previous.x - (item.x + item.width)
                : item.x - (previous.x + previous.width);
            const noSpaceBefore = /^[,.;:!?%)\]}]/u.test(item.text);
            const noSpaceAfter = /[(\[{]$/u.test(previous.text);
            if (!noSpaceBefore && !noSpaceAfter && gap > Math.max(0.8, fontSize * 0.12)) {
                output += gap > fontSize * 0.9 ? '  ' : ' ';
            }
        }
        output += item.text;
        previous = item;
    }

    return output.replace(/[ \t]+/g, match => match.length > 1 ? '  ' : ' ').trim();
};

const makeLine = (items: PositionedItem[]): LayoutLine => {
    const fontSize = median(items.map(item => item.fontSize)) || 10;
    return {
        items,
        text: renderLine(items, fontSize),
        y: median(items.map(item => item.y)),
        minX: Math.min(...items.map(item => item.x)),
        maxX: Math.max(...items.map(item => item.x + item.width)),
        fontSize,
    };
};

const groupIntoLines = (items: PositionedItem[]): LayoutLine[] => {
    const rows: PositionedItem[][] = [];
    const byPosition = [...items].sort((a, b) => b.y - a.y || a.x - b.x);

    for (const item of byPosition) {
        let bestRow: PositionedItem[] | null = null;
        let bestDelta = Number.POSITIVE_INFINITY;
        for (const row of rows) {
            const rowY = median(row.map(entry => entry.y));
            const rowFont = median(row.map(entry => entry.fontSize));
            const delta = Math.abs(item.y - rowY);
            const tolerance = Math.max(1.5, Math.max(item.fontSize, rowFont) * 0.52);
            if (delta <= tolerance && delta < bestDelta) {
                bestRow = row;
                bestDelta = delta;
            }
        }
        if (bestRow) bestRow.push(item);
        else rows.push([item]);
    }

    const pageMinX = Math.min(...items.map(item => item.x));
    const pageMaxX = Math.max(...items.map(item => item.x + item.width));
    const pageWidth = Math.max(1, pageMaxX - pageMinX);
    const lines: LayoutLine[] = [];

    for (const row of rows) {
        const ordered = [...row].sort((a, b) => a.x - b.x);
        const rowFont = median(ordered.map(item => item.fontSize)) || 10;
        const splitGap = Math.max(rowFont * 3, pageWidth * 0.075);
        let segment: PositionedItem[] = [];

        for (const item of ordered) {
            const previous = segment[segment.length - 1];
            const gap = previous ? item.x - (previous.x + previous.width) : 0;
            if (previous && gap > splitGap) {
                lines.push(makeLine(segment));
                segment = [];
            }
            segment.push(item);
        }
        if (segment.length) lines.push(makeLine(segment));
    }

    return lines;
};

interface ColumnSplit {
    x: number;
    score: number;
}

const findColumnSplit = (lines: LayoutLine[]): ColumnSplit | null => {
    if (lines.length < 4) return null;
    const pageMinX = Math.min(...lines.map(line => line.minX));
    const pageMaxX = Math.max(...lines.map(line => line.maxX));
    const pageWidth = pageMaxX - pageMinX;
    const typicalFont = median(lines.map(line => line.fontSize)) || 10;
    if (pageWidth <= typicalFont * 8) return null;

    let best: ColumnSplit | null = null;
    for (let step = 0; step <= 40; step++) {
        const x = pageMinX + pageWidth * (0.25 + step * 0.0125);
        const left = lines.filter(line => line.maxX < x);
        const right = lines.filter(line => line.minX > x);
        if (left.length < 2 || right.length < 2) continue;

        const covered = left.length + right.length;
        const coverage = covered / lines.length;
        const balance = Math.min(left.length, right.length) / Math.max(left.length, right.length);
        const leftTop = Math.max(...left.map(line => line.y));
        const leftBottom = Math.min(...left.map(line => line.y));
        const rightTop = Math.max(...right.map(line => line.y));
        const rightBottom = Math.min(...right.map(line => line.y));
        const verticalOverlap = Math.max(0, Math.min(leftTop, rightTop) - Math.max(leftBottom, rightBottom));
        const shorterColumnSpan = Math.max(
            typicalFont,
            Math.min(leftTop - leftBottom, rightTop - rightBottom),
        );
        const overlapRatio = verticalOverlap / shorterColumnSpan;
        const leftEdge = Math.max(...left.map(line => line.maxX));
        const rightEdge = Math.min(...right.map(line => line.minX));
        const gutter = rightEdge - leftEdge;
        const minimumGutter = Math.max(typicalFont * 1.5, pageWidth * 0.035);
        if (gutter < minimumGutter || coverage < 0.6 || balance < 0.35 || overlapRatio < 0.25) continue;

        const score = coverage * 0.45
            + balance * 0.2
            + Math.min(1, gutter / (pageWidth * 0.12)) * 0.2
            + Math.min(1, overlapRatio) * 0.15;
        if (!best || score > best.score) best = { x, score };
    }
    return best;
};

const topToBottom = (lines: LayoutLine[]): LayoutLine[] =>
    [...lines].sort((a, b) => b.y - a.y || a.minX - b.minX);

const orderByColumns = (lines: LayoutLine[], splitX: number): LayoutLine[] => {
    const ordered: LayoutLine[] = [];
    let section: LayoutLine[] = [];

    const flushSection = () => {
        if (!section.length) return;
        const left = topToBottom(section.filter(line => line.maxX < splitX));
        const right = topToBottom(section.filter(line => line.minX > splitX));
        const ambiguous = topToBottom(section.filter(line => line.maxX >= splitX && line.minX <= splitX));
        ordered.push(...left, ...right, ...ambiguous);
        section = [];
    };

    for (const line of topToBottom(lines)) {
        const spansGutter = line.minX <= splitX && line.maxX >= splitX;
        if (spansGutter) {
            flushSection();
            ordered.push(line);
        } else {
            section.push(line);
        }
    }
    flushSection();
    return ordered;
};

/** Order one PDF page using coordinates when they are trustworthy. */
export const extractPdfPageText = (items: PdfTextItemLike[]): PdfPageText => {
    const textItems = items.filter(item => typeof item.str === 'string' && item.str.trim());
    const positioned = textItems.map(toPositionedItem).filter((item): item is PositionedItem => item !== null);
    const positionedRatio = textItems.length ? positioned.length / textItems.length : 1;
    const ySpread = positioned.length
        ? Math.max(...positioned.map(item => item.y)) - Math.min(...positioned.map(item => item.y))
        : 0;
    const typicalFont = median(positioned.map(item => item.fontSize)) || 10;
    const coordinateConfidence = positioned.length <= 1 || ySpread > typicalFont * 0.5 ? 1 : 0.45;
    const confidence = positionedRatio * coordinateConfidence;

    if (!textItems.length) {
        return { text: '', lines: [], confidence: 1, usedPositionalLayout: true };
    }
    if (confidence < 0.72) {
        const text = fallbackEolText(items);
        return { text, lines: text.split(/\n+/).filter(Boolean), confidence, usedPositionalLayout: false };
    }

    const lines = groupIntoLines(positioned);
    const columnSplit = findColumnSplit(lines);
    const ordered = columnSplit ? orderByColumns(lines, columnSplit.x) : topToBottom(lines);
    const rendered = ordered.map(line => line.text).filter(Boolean);
    return {
        text: rendered.join('\n'),
        lines: rendered,
        confidence: columnSplit ? Math.min(1, confidence * columnSplit.score) : confidence,
        usedPositionalLayout: true,
    };
};

const marginKey = (line: string): string => line
    .toLocaleLowerCase()
    .replace(/\s+/g, ' ')
    .trim();

const isPurePageNumber = (line: string): boolean => /^\p{N}+$/u.test(line.trim());

/** Remove only lines repeated in the same outer margin across at least 3 pages. */
export const combinePdfPages = (pages: PdfPageText[]): string => {
    if (pages.length < 3) return pages.map(page => page.text).filter(Boolean).join('\n\n');

    const counts = new Map<string, number>();
    let numericTopPages = 0;
    let numericBottomPages = 0;
    for (const page of pages) {
        if (page.lines.length < 3) continue;
        if (isPurePageNumber(page.lines[0])) numericTopPages += 1;
        if (isPurePageNumber(page.lines[page.lines.length - 1])) numericBottomPages += 1;
        const keys = new Set([
            `top:${marginKey(page.lines[0])}`,
            `bottom:${marginKey(page.lines[page.lines.length - 1])}`,
        ]);
        for (const key of keys) counts.set(key, (counts.get(key) || 0) + 1);
    }

    const threshold = Math.max(3, Math.ceil(pages.length * 0.6));
    return pages.map(page => {
        const lines = [...page.lines];
        const removeTop = lines.length >= 3
            && ((isPurePageNumber(lines[0]) && numericTopPages >= threshold)
                || (counts.get(`top:${marginKey(lines[0])}`) || 0) >= threshold);
        const removeBottom = lines.length >= 3
            && ((isPurePageNumber(lines[lines.length - 1]) && numericBottomPages >= threshold)
                || (counts.get(`bottom:${marginKey(lines[lines.length - 1])}`) || 0) >= threshold);
        if (removeTop) lines.shift();
        if (removeBottom) lines.pop();
        return lines.join('\n');
    }).filter(Boolean).join('\n\n');
};
