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

/** Wait for a stream to prove it has audio without reviving an invalidated attempt. */
export const waitForStreamAvailability = async (
    record: StreamRecord,
    isCurrent: () => boolean,
): Promise<boolean> => {
    if (!isCurrent() || record.done) return false;
    if (record.chunks.length > 0) return true;

    const hasAudio = await new Promise<boolean>(resolve => {
        const probe = (pcm: ArrayBuffer | null) => {
            record.listeners.delete(probe);
            resolve(pcm !== null);
        };
        record.listeners.add(probe);
    });
    return hasAudio && isCurrent();
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
