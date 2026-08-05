/**
 * Persistent store for generated narration audio.
 *
 * Re-listening to a passage used to mean paying for it again - a fresh Live API
 * turn, and the wait that comes with it. Clips are kept here instead, keyed to
 * the document they came from so one book's audio can never surface while
 * another is open.
 *
 * Audio is stored as raw 16-bit PCM, the same format the server streams. At
 * 24kHz mono that is 48 KB per second, so the store is capped and evicts the
 * least recently used clips once it is full.
 */

const DB_NAME = 'document-audiobook-cache';
const DB_VERSION = 1;
const META_STORE = 'meta';
const BLOB_STORE = 'blobs';
const LIMITS_KEY = 'audioCacheLimits';

export interface CacheLimits {
    /** Hard ceiling on total stored audio. */
    maxBytes: number;
    /** Clips untouched for longer than this are swept regardless of size. */
    maxAgeDays: number;
}

export const DEFAULT_LIMITS: CacheLimits = {
    maxBytes: 750 * 1024 * 1024,   // ~4.5 hours of narration
    maxAgeDays: 30,
};

export interface ClipMeta {
    key: string;
    documentId: string;
    documentName: string;
    index: number;
    /** The source text this clip was generated from, as it read at the time. */
    text: string;
    /**
     * What the model reported actually saying, from the session's own output
     * transcription. Compared against `text` to flag narration that drifted -
     * and, once the source file is edited, to show that the stored audio no
     * longer matches the document. Empty for clips stored before this existed.
     */
    spokenText: string;
    voice: string;
    model: string;
    bytes: number;
    durationSec: number;
    sampleRate: number;
    createdAt: number;
    lastUsedAt: number;
    /**
     * When true this clip is bypassed and regenerated on next play, then
     * replaced. This is the "generate live" switch in the manager.
     */
    liveOnly: boolean;
}

export interface DocumentSummary {
    documentId: string;
    documentName: string;
    clips: number;
    bytes: number;
    durationSec: number;
    lastUsedAt: number;
}

// --- change notifications ---------------------------------------------------

/**
 * The manager needs to reflect work as it happens, not on a timer. Every write
 * announces itself, and the engine reports what it is doing per sentence, so
 * the panel can show live progress instead of a stale snapshot.
 */
export type CacheEvent =
    | { type: 'changed' }
    | {
        type: 'activity';
        index: number;
        text: string;
        state: 'generating' | 'hit' | 'saved' | 'idle';
    };

const listeners = new Set<(event: CacheEvent) => void>();

export const subscribe = (fn: (event: CacheEvent) => void): (() => void) => {
    listeners.add(fn);
    return () => { listeners.delete(fn); };
};

const emit = (event: CacheEvent) => {
    for (const fn of [...listeners]) {
        try { fn(event); } catch { /* a bad listener must not break a write */ }
    }
};

/** Called by the audio engine as it works through sentences. */
export const noteActivity = (
    index: number, text: string, state: 'generating' | 'hit' | 'saved' | 'idle',
) => emit({ type: 'activity', index, text, state });

// --- limits -----------------------------------------------------------------

export const getLimits = (): CacheLimits => {
    try {
        const raw = localStorage.getItem(LIMITS_KEY);
        if (raw) return { ...DEFAULT_LIMITS, ...JSON.parse(raw) };
    } catch { /* fall through to defaults */ }
    return { ...DEFAULT_LIMITS };
};

export const setLimits = (limits: Partial<CacheLimits>): CacheLimits => {
    const merged = { ...getLimits(), ...limits };
    try { localStorage.setItem(LIMITS_KEY, JSON.stringify(merged)); } catch { /* non-fatal */ }
    return merged;
};

// --- database ---------------------------------------------------------------

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
    run: (t: IDBTransaction) => Promise<T> | T,
): Promise<T> => {
    const db = await openDb();
    return new Promise<T>((resolve, reject) => {
        const t = db.transaction(stores, mode);
        let result: T;
        t.oncomplete = () => resolve(result);
        t.onerror = () => reject(t.error);
        t.onabort = () => reject(t.error);
        Promise.resolve(run(t)).then(r => { result = r; }, reject);
    });
};

const req = <T>(r: IDBRequest<T>): Promise<T> =>
    new Promise((resolve, reject) => {
        r.onsuccess = () => resolve(r.result);
        r.onerror = () => reject(r.error);
    });

// --- identity ---------------------------------------------------------------

const sha256 = async (input: string): Promise<string> => {
    const bytes = new TextEncoder().encode(input);
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
};

/**
 * Identity for a document, from its filename.
 *
 * This was a hash of the extracted text, which meant editing a file produced a
 * brand new document and orphaned everything generated for the old version.
 * Keying on the name instead lets a file be revised while remaining the same
 * document, so its stored audio stays visible - and comparing each clip's text
 * against the document's current text is what reveals the edit.
 */
export const makeDocumentId = (fileName: string): Promise<string> =>
    sha256(`name:${fileName.trim().toLowerCase()}`);

/**
 * Identity for one clip: document, position, voice and model.
 *
 * Deliberately not the sentence text. Including it meant an edit produced a new
 * key, so the old clip lingered invisibly at the same position rather than being
 * shown as out of date. One clip per position per voice keeps the manager a true
 * picture of what is stored, and stale audio is surfaced by its marker instead
 * of hidden.
 */
export const makeClipKey = async (args: {
    documentId: string; index: number; voice: string; model: string;
}): Promise<string> =>
    sha256([args.documentId, args.index, args.voice, args.model].join(' '));

// --- comparing narration against the source ---------------------------------

export type MatchLevel = 'match' | 'drift' | 'diverged' | 'unknown';

export interface MatchResult {
    level: MatchLevel;
    /** 0-1 similarity, or null when there is nothing to compare. */
    ratio: number | null;
    /** Words spoken minus words in the source; positive means the model added. */
    wordDelta: number;
    label: string;
}

const normaliseWords = (s: string): string[] =>
    s.toLowerCase()
        .replace(/[^\p{L}\p{N}\s']/gu, ' ')
        .split(/\s+/)
        .filter(Boolean);

/** Length of the longest common subsequence of two word arrays. */
const lcsLength = (a: string[], b: string[]): number => {
    if (!a.length || !b.length) return 0;
    // Only two rows are needed; passages can be a few hundred words.
    let previous = new Array(b.length + 1).fill(0);
    let current = new Array(b.length + 1).fill(0);
    for (let i = 1; i <= a.length; i++) {
        for (let j = 1; j <= b.length; j++) {
            current[j] = a[i - 1] === b[j - 1]
                ? previous[j - 1] + 1
                : Math.max(previous[j], current[j - 1]);
        }
        [previous, current] = [current, previous];
        current.fill(0);
    }
    return previous[b.length];
};

/**
 * How closely the narration matched the text it was asked to read.
 *
 * Uses the longest common subsequence over words rather than a set overlap, so
 * word order matters and - importantly - added words count against the score.
 * A passage where the model read one sentence and then improvised a second
 * scores low even though every source word appears, which is exactly the
 * divergence worth flagging.
 */
export const compareNarration = (sourceText: string, spokenText: string): MatchResult => {
    const source = normaliseWords(sourceText || '');
    const spoken = normaliseWords(spokenText || '');

    if (!spoken.length) {
        return {
            level: 'unknown', ratio: null, wordDelta: -source.length,
            label: source.length ? 'no transcript stored' : 'nothing to compare',
        };
    }

    const common = lcsLength(source, spoken);
    const ratio = (2 * common) / (source.length + spoken.length);
    const wordDelta = spoken.length - source.length;

    const level: MatchLevel = ratio >= 0.75 ? 'match' : ratio >= 0.5 ? 'drift' : 'diverged';
    const pct = Math.round(ratio * 100);
    const label =
        level === 'match' ? (ratio >= 0.995 ? 'read word for word' : `${pct}% match`)
            : level === 'drift' ? `${pct}% match - drifted from the source`
                : `${pct}% match - diverged from the source`;

    return { level, ratio, wordDelta, label };
};

// --- storing at all ---------------------------------------------------------

const SAVING_KEY = 'audioCacheSavingEnabled';

/**
 * Whether generated audio is kept. Off means every passage is generated live
 * and nothing is written - useful when working on a throwaway document that
 * should not fill the store.
 */
export const isSavingEnabled = (): boolean => {
    try { return localStorage.getItem(SAVING_KEY) !== 'false'; } catch { return true; }
};

export const setSavingEnabled = (enabled: boolean): boolean => {
    try { localStorage.setItem(SAVING_KEY, enabled ? 'true' : 'false'); } catch { /* non-fatal */ }
    emit({ type: 'changed' });
    return enabled;
};

// --- PCM conversion ---------------------------------------------------------

/** AudioBuffer (float) -> the 16-bit PCM the server originally sent. */
export const audioBufferToPcm16 = (buffer: AudioBuffer): ArrayBuffer => {
    const channel = buffer.getChannelData(0);
    const out = new Int16Array(channel.length);
    for (let i = 0; i < channel.length; i++) {
        const clamped = Math.max(-1, Math.min(1, channel[i]));
        out[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    }
    return out.buffer;
};

/** 16-bit PCM -> a playable AudioBuffer. */
export const pcm16ToAudioBuffer = (
    pcm: ArrayBuffer, sampleRate: number, context: BaseAudioContext,
): AudioBuffer => {
    const samples = new Int16Array(pcm);
    const buffer = context.createBuffer(1, samples.length, sampleRate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 32768;
    return buffer;
};

// --- reads ------------------------------------------------------------------

/**
 * Fetch a clip and mark it used. Returns null on a miss, or when the clip is
 * flagged live-only and must be regenerated.
 */
export const getClip = async (
    key: string, context: BaseAudioContext,
): Promise<{ buffer: AudioBuffer; meta: ClipMeta } | null> => {
    try {
        return await tx([META_STORE, BLOB_STORE], 'readwrite', async t => {
            const metaStore = t.objectStore(META_STORE);
            const meta = await req<ClipMeta | undefined>(metaStore.get(key));
            if (!meta || meta.liveOnly) return null;

            const blob = await req<ArrayBuffer | undefined>(t.objectStore(BLOB_STORE).get(key));
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
    const all = await tx([META_STORE], 'readonly', t =>
        req<ClipMeta[]>(t.objectStore(META_STORE).getAll()));

    const byDoc = new Map<string, DocumentSummary>();
    for (const m of all) {
        const existing = byDoc.get(m.documentId);
        if (existing) {
            existing.clips += 1;
            existing.bytes += m.bytes;
            existing.durationSec += m.durationSec;
            existing.lastUsedAt = Math.max(existing.lastUsedAt, m.lastUsedAt);
            existing.documentName = existing.documentName || m.documentName;
        } else {
            byDoc.set(m.documentId, {
                documentId: m.documentId,
                documentName: m.documentName,
                clips: 1,
                bytes: m.bytes,
                durationSec: m.durationSec,
                lastUsedAt: m.lastUsedAt,
            });
        }
    }
    return [...byDoc.values()].sort((a, b) => b.lastUsedAt - a.lastUsedAt);
};

export const listClips = async (documentId: string): Promise<ClipMeta[]> => {
    const clips = await tx([META_STORE], 'readonly', t =>
        req<ClipMeta[]>(t.objectStore(META_STORE).index('documentId').getAll(documentId)));
    return clips.sort((a, b) => a.index - b.index);
};

export const getStats = async (): Promise<{ clips: number; bytes: number; documents: number }> => {
    const all = await tx([META_STORE], 'readonly', t =>
        req<ClipMeta[]>(t.objectStore(META_STORE).getAll()));
    return {
        clips: all.length,
        bytes: all.reduce((sum, m) => sum + m.bytes, 0),
        documents: new Set(all.map(m => m.documentId)).size,
    };
};

// --- writes -----------------------------------------------------------------

export const putClip = async (
    meta: Omit<ClipMeta, 'createdAt' | 'lastUsedAt' | 'liveOnly'>,
    pcm: ArrayBuffer,
    keepLiveOnly = false,
): Promise<void> => {
    try {
        const now = Date.now();
        await tx([META_STORE, BLOB_STORE], 'readwrite', async t => {
            const store = t.objectStore(META_STORE);
            const previous = await req<ClipMeta | undefined>(store.get(meta.key));
            store.put({
                ...meta,
                createdAt: previous?.createdAt ?? now,
                lastUsedAt: now,
                // A regenerate request clears itself once satisfied, unless the
                // clip is pinned to always regenerate.
                liveOnly: keepLiveOnly ? (previous?.liveOnly ?? false) : false,
            });
            t.objectStore(BLOB_STORE).put(pcm, meta.key);
        });
        emit({ type: 'changed' });
        await enforceLimits();
    } catch (error) {
        // Storage full or blocked: generation already succeeded, so this is not
        // worth failing playback over.
        console.warn('Audio cache write failed (playback unaffected):', error);
    }
};

export const setLiveOnly = async (key: string, liveOnly: boolean): Promise<void> => {
    await tx([META_STORE], 'readwrite', async t => {
        const store = t.objectStore(META_STORE);
        const meta = await req<ClipMeta | undefined>(store.get(key));
        if (meta) store.put({ ...meta, liveOnly });
    });
    emit({ type: 'changed' });
};

export const deleteClip = async (key: string): Promise<void> => {
    await tx([META_STORE, BLOB_STORE], 'readwrite', t => {
        t.objectStore(META_STORE).delete(key);
        t.objectStore(BLOB_STORE).delete(key);
    });
    emit({ type: 'changed' });
};

export const deleteDocument = async (documentId: string): Promise<number> => {
    const clips = await listClips(documentId);
    await tx([META_STORE, BLOB_STORE], 'readwrite', t => {
        for (const c of clips) {
            t.objectStore(META_STORE).delete(c.key);
            t.objectStore(BLOB_STORE).delete(c.key);
        }
    });
    emit({ type: 'changed' });
    return clips.length;
};

export const clearAll = async (): Promise<void> => {
    await tx([META_STORE, BLOB_STORE], 'readwrite', t => {
        t.objectStore(META_STORE).clear();
        t.objectStore(BLOB_STORE).clear();
    });
    emit({ type: 'changed' });
};

/**
 * Drop clips that are too old, then the least recently used ones until the
 * store is under its size cap. Returns how many were removed.
 */
export const enforceLimits = async (): Promise<number> => {
    const { maxBytes, maxAgeDays } = getLimits();
    const all = await tx([META_STORE], 'readonly', t =>
        req<ClipMeta[]>(t.objectStore(META_STORE).getAll()));

    const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000;
    const doomed = new Set(all.filter(m => m.lastUsedAt < cutoff).map(m => m.key));

    let total = all.reduce((sum, m) => sum + (doomed.has(m.key) ? 0 : m.bytes), 0);
    if (total > maxBytes) {
        const survivors = all
            .filter(m => !doomed.has(m.key))
            .sort((a, b) => a.lastUsedAt - b.lastUsedAt);  // oldest use first
        for (const m of survivors) {
            if (total <= maxBytes) break;
            doomed.add(m.key);
            total -= m.bytes;
        }
    }

    if (!doomed.size) return 0;
    await tx([META_STORE, BLOB_STORE], 'readwrite', t => {
        for (const key of doomed) {
            t.objectStore(META_STORE).delete(key);
            t.objectStore(BLOB_STORE).delete(key);
        }
    });
    emit({ type: 'changed' });
    return doomed.size;
};

export const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
};

export const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s.toString().padStart(2, '0')}s`;
};
