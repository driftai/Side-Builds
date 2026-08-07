import type { PrefetchEntry, StreamRecord } from './types';

export const createStreamRecord = (): StreamRecord => ({
    chunks: [],
    done: false,
    listeners: new Set(),
});

export const collectStreamChunk = (record: StreamRecord, pcm: ArrayBuffer): void => {
    record.chunks.push(pcm);
    for (const listener of record.listeners) listener(pcm);
};

export const closeStreamRecord = (record: StreamRecord | null): void => {
    if (!record || record.done) return;
    record.done = true;
    for (const listener of record.listeners) listener(null);
};

export const abortPrefetchEntry = (entry: PrefetchEntry): void => {
    entry.controller.abort();
    entry.promise.catch(() => { });
};

export const clearPrefetchQueue = (queue: Map<number, PrefetchEntry>): void => {
    for (const entry of queue.values()) abortPrefetchEntry(entry);
    queue.clear();
};

export const prunePrefetchQueue = (
    queue: Map<number, PrefetchEntry>,
    beforeIndex: number,
): void => {
    for (const [index, entry] of [...queue.entries()]) {
        if (index >= beforeIndex) continue;
        if (!entry.keepToCompletion) abortPrefetchEntry(entry);
        queue.delete(index);
    }
};

export const remapPrefetchQueue = (
    queue: Map<number, PrefetchEntry>,
    next: string[],
    oldToNew: (number | null)[],
): Map<number, PrefetchEntry> => {
    const remapped = new Map<number, PrefetchEntry>();
    for (const [oldIndex, entry] of queue) {
        const newIndex = oldIndex < oldToNew.length ? oldToNew[oldIndex] : null;
        if (newIndex === null || next[newIndex] !== entry.text) {
            abortPrefetchEntry(entry);
            continue;
        }
        remapped.set(newIndex, entry);
    }
    return remapped;
};
