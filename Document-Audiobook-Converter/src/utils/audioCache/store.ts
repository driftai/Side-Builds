import { emitCacheEvent } from './events';
import { getLimits } from './preferences';
import { pcm16ToAudioBuffer } from './pcm';
import type { ClipMeta, DocumentSummary } from './types';

// These names and the version are persistent data contracts. Do not change
// them as part of a code-only modularization.
const DB_NAME = 'document-audiobook-cache';
const DB_VERSION = 1;
const META_STORE = 'meta';
const BLOB_STORE = 'blobs';

/** One lazy database handle shared by every cache operation. */
let dbPromise: Promise<IDBDatabase> | null = null;

const openDb = (): Promise<IDBDatabase> => {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(META_STORE)) {
                const meta = db.createObjectStore(META_STORE, { keyPath: 'key' });
                meta.createIndex('documentId', 'documentId', { unique: false });
                meta.createIndex('lastUsedAt', 'lastUsedAt', { unique: false });
            }
            if (!db.objectStoreNames.contains(BLOB_STORE)) {
                db.createObjectStore(BLOB_STORE);
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
    return dbPromise;
};

const tx = async <T>(
    stores: string[],
    mode: IDBTransactionMode,
    run: (transaction: IDBTransaction) => Promise<T> | T,
): Promise<T> => {
    const db = await openDb();
    return new Promise<T>((resolve, reject) => {
        const transaction = db.transaction(stores, mode);
        let result: T;
        transaction.oncomplete = () => resolve(result);
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
        Promise.resolve(run(transaction)).then(value => { result = value; }, reject);
    });
};

const req = <T>(request: IDBRequest<T>): Promise<T> =>
    new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });

/** Record where a text-keyed clip currently sits in the document. */
export const updateClipPosition = async (key: string, index: number): Promise<void> => {
    try {
        await tx([META_STORE], 'readwrite', async transaction => {
            const store = transaction.objectStore(META_STORE);
            const meta = await req<ClipMeta | undefined>(store.get(key));
            if (!meta || meta.index === index) return;
            store.put({ ...meta, index });
        });
    } catch (error) {
        // Cosmetic only - never worth failing playback over.
        console.warn('Could not update stored clip position:', error);
    }
};

/** Move a position-keyed legacy clip onto its current text-based key. */
export const adoptLegacyClip = async (legacyKey: string, key: string): Promise<boolean> => {
    try {
        return await tx([META_STORE, BLOB_STORE], 'readwrite', async transaction => {
            const metaStore = transaction.objectStore(META_STORE);
            const blobStore = transaction.objectStore(BLOB_STORE);
            const meta = await req<ClipMeta | undefined>(metaStore.get(legacyKey));
            const blob = await req<ArrayBuffer | undefined>(blobStore.get(legacyKey));
            if (!meta || !blob) return false;
            metaStore.put({ ...meta, key });
            blobStore.put(blob, key);
            metaStore.delete(legacyKey);
            blobStore.delete(legacyKey);
            return true;
        });
    } catch (error) {
        console.warn('Could not adopt a clip stored under the old key:', error);
        return false;
    }
};

/** Fetch a clip and mark it used, or return null when it must be generated. */
export const getClip = async (
    key: string, context: BaseAudioContext,
): Promise<{ buffer: AudioBuffer; meta: ClipMeta } | null> => {
    try {
        return await tx([META_STORE, BLOB_STORE], 'readwrite', async transaction => {
            const metaStore = transaction.objectStore(META_STORE);
            const meta = await req<ClipMeta | undefined>(metaStore.get(key));
            if (!meta || meta.liveOnly) return null;

            const blob = await req<ArrayBuffer | undefined>(
                transaction.objectStore(BLOB_STORE).get(key),
            );
            if (!blob) return null;

            meta.lastUsedAt = Date.now();
            metaStore.put(meta);
            return { buffer: pcm16ToAudioBuffer(blob, meta.sampleRate, context), meta };
        });
    } catch (error) {
        console.warn('Audio cache read failed, falling back to generation:', error);
        return null;
    }
};

export const listDocuments = async (): Promise<DocumentSummary[]> => {
    const all = await tx([META_STORE], 'readonly', transaction =>
        req<ClipMeta[]>(transaction.objectStore(META_STORE).getAll()));

    const byDoc = new Map<string, DocumentSummary>();
    for (const meta of all) {
        const existing = byDoc.get(meta.documentId);
        if (existing) {
            existing.clips += 1;
            existing.bytes += meta.bytes;
            existing.durationSec += meta.durationSec;
            existing.lastUsedAt = Math.max(existing.lastUsedAt, meta.lastUsedAt);
            existing.documentName = existing.documentName || meta.documentName;
        } else {
            byDoc.set(meta.documentId, {
                documentId: meta.documentId,
                documentName: meta.documentName,
                clips: 1,
                bytes: meta.bytes,
                durationSec: meta.durationSec,
                lastUsedAt: meta.lastUsedAt,
            });
        }
    }
    return [...byDoc.values()].sort((a, b) => b.lastUsedAt - a.lastUsedAt);
};

export const listClips = async (documentId: string): Promise<ClipMeta[]> => {
    const clips = await tx([META_STORE], 'readonly', transaction =>
        req<ClipMeta[]>(transaction.objectStore(META_STORE).index('documentId').getAll(documentId)));
    return clips.sort((a, b) => a.index - b.index);
};

export const getStats = async (): Promise<{ clips: number; bytes: number; documents: number }> => {
    const all = await tx([META_STORE], 'readonly', transaction =>
        req<ClipMeta[]>(transaction.objectStore(META_STORE).getAll()));
    return {
        clips: all.length,
        bytes: all.reduce((sum, meta) => sum + meta.bytes, 0),
        documents: new Set(all.map(meta => meta.documentId)).size,
    };
};

export const putClip = async (
    meta: Omit<ClipMeta, 'createdAt' | 'lastUsedAt' | 'liveOnly'>,
    pcm: ArrayBuffer,
    keepLiveOnly = false,
): Promise<void> => {
    try {
        const now = Date.now();
        await tx([META_STORE, BLOB_STORE], 'readwrite', async transaction => {
            const store = transaction.objectStore(META_STORE);
            const previous = await req<ClipMeta | undefined>(store.get(meta.key));
            store.put({
                ...meta,
                createdAt: previous?.createdAt ?? now,
                lastUsedAt: now,
                // A regenerate request clears itself once satisfied, unless the
                // clip is pinned to always regenerate.
                liveOnly: keepLiveOnly ? (previous?.liveOnly ?? false) : false,
            });
            transaction.objectStore(BLOB_STORE).put(pcm, meta.key);
        });
        emitCacheEvent({ type: 'changed' });
        await enforceLimits();
    } catch (error) {
        // Generation already succeeded, so a storage failure must not stop play.
        console.warn('Audio cache write failed (playback unaffected):', error);
    }
};

export const setLiveOnly = async (key: string, liveOnly: boolean): Promise<void> => {
    await tx([META_STORE], 'readwrite', async transaction => {
        const store = transaction.objectStore(META_STORE);
        const meta = await req<ClipMeta | undefined>(store.get(key));
        if (meta) store.put({ ...meta, liveOnly });
    });
    emitCacheEvent({ type: 'changed' });
    emitCacheEvent({ type: 'removed' });
};

export const deleteClip = async (key: string): Promise<void> => {
    await tx([META_STORE, BLOB_STORE], 'readwrite', transaction => {
        transaction.objectStore(META_STORE).delete(key);
        transaction.objectStore(BLOB_STORE).delete(key);
    });
    emitCacheEvent({ type: 'changed' });
    emitCacheEvent({ type: 'removed' });
};

export const deleteDocument = async (documentId: string): Promise<number> => {
    const clips = await listClips(documentId);
    await tx([META_STORE, BLOB_STORE], 'readwrite', transaction => {
        for (const clip of clips) {
            transaction.objectStore(META_STORE).delete(clip.key);
            transaction.objectStore(BLOB_STORE).delete(clip.key);
        }
    });
    emitCacheEvent({ type: 'changed' });
    emitCacheEvent({ type: 'removed' });
    return clips.length;
};

export const clearAll = async (): Promise<void> => {
    await tx([META_STORE, BLOB_STORE], 'readwrite', transaction => {
        transaction.objectStore(META_STORE).clear();
        transaction.objectStore(BLOB_STORE).clear();
    });
    emitCacheEvent({ type: 'changed' });
    emitCacheEvent({ type: 'removed' });
};

/** Remove old clips, then least-recently-used clips until under the size cap. */
export const enforceLimits = async (): Promise<number> => {
    const { maxBytes, maxAgeDays } = getLimits();
    const all = await tx([META_STORE], 'readonly', transaction =>
        req<ClipMeta[]>(transaction.objectStore(META_STORE).getAll()));

    const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000;
    const doomed = new Set(all.filter(meta => meta.lastUsedAt < cutoff).map(meta => meta.key));

    let total = all.reduce((sum, meta) => sum + (doomed.has(meta.key) ? 0 : meta.bytes), 0);
    if (total > maxBytes) {
        const survivors = all
            .filter(meta => !doomed.has(meta.key))
            .sort((a, b) => a.lastUsedAt - b.lastUsedAt);
        for (const meta of survivors) {
            if (total <= maxBytes) break;
            doomed.add(meta.key);
            total -= meta.bytes;
        }
    }

    if (!doomed.size) return 0;
    await tx([META_STORE, BLOB_STORE], 'readwrite', transaction => {
        for (const key of doomed) {
            transaction.objectStore(META_STORE).delete(key);
            transaction.objectStore(BLOB_STORE).delete(key);
        }
    });
    emitCacheEvent({ type: 'changed' });
    emitCacheEvent({ type: 'removed' });
    return doomed.size;
};
