import { describe, expect, it, vi } from 'vitest';
import {
    closeStreamRecord,
    collectStreamChunk,
    createStreamRecord,
    prunePrefetchQueue,
    remapPrefetchQueue,
} from '../src/hooks/audioEngine/prefetchQueue';
import type { PrefetchEntry } from '../src/hooks/audioEngine/types';

const makeEntry = (text: string, keepToCompletion = false): PrefetchEntry => ({
    text,
    keepToCompletion,
    controller: new AbortController(),
    promise: Promise.resolve({} as AudioBuffer),
});

describe('audio prefetch queue helpers', () => {
    it('delivers chunks in order and closes a stream exactly once', () => {
        const record = createStreamRecord();
        const listener = vi.fn();
        record.listeners.add(listener);
        const chunk = new ArrayBuffer(4);

        collectStreamChunk(record, chunk);
        closeStreamRecord(record);
        closeStreamRecord(record);

        expect(record.chunks).toEqual([chunk]);
        expect(listener.mock.calls).toEqual([[chunk], [null]]);
    });

    it('aborts stale entries but lets heard generations finish for storage', () => {
        const stale = makeEntry('stale');
        const heard = makeEntry('heard', true);
        const current = makeEntry('current');
        const queue = new Map([[0, stale], [1, heard], [2, current]]);

        prunePrefetchQueue(queue, 2);

        expect([...queue.keys()]).toEqual([2]);
        expect(stale.controller.signal.aborted).toBe(true);
        expect(heard.controller.signal.aborted).toBe(false);
        expect(current.controller.signal.aborted).toBe(false);
    });

    it('moves surviving text and aborts entries invalidated by an edit', () => {
        const moved = makeEntry('keep');
        const changed = makeEntry('old words');
        const remapped = remapPrefetchQueue(
            new Map([[2, moved], [3, changed]]),
            ['new', 'keep', 'replacement'],
            [null, null, 1, 2],
        );

        expect(remapped.get(1)).toBe(moved);
        expect(changed.controller.signal.aborted).toBe(true);
        expect(remapped.has(2)).toBe(false);
    });
});
