import { useCallback, useEffect, useState } from 'react';
import {
    clearAll,
    deleteClip,
    deleteDocument,
    enforceLimits,
    getLimits,
    getStats,
    isSavingEnabled,
    isStreamingEnabled,
    listClips,
    listDocuments,
    setLimits,
    setLiveOnly,
    setSavingEnabled,
    setStreamingEnabled,
    subscribe,
} from '../../utils/audioCache';
import type {
    CacheEvent,
    CacheLimits,
    ClipMeta,
    DocumentSummary,
} from '../../utils/audioCache';

export interface CacheActivity {
    index: number;
    text: string;
    state: 'generating' | 'hit' | 'saved';
    at: number;
}

export interface CacheStats {
    clips: number;
    bytes: number;
    documents: number;
}

export const useAudioCacheManager = () => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [documents, setDocuments] = useState<DocumentSummary[]>([]);
    const [stats, setStats] = useState<CacheStats>({ clips: 0, bytes: 0, documents: 0 });
    const [openDocId, setOpenDocId] = useState<string | null>(null);
    const [clips, setClips] = useState<ClipMeta[]>([]);
    const [limits, setLimitsState] = useState<CacheLimits>(getLimits());
    const [busy, setBusy] = useState(false);
    const [activity, setActivity] = useState<CacheActivity | null>(null);
    const [saving, setSaving] = useState(isSavingEnabled());
    const [streaming, setStreaming] = useState(isStreamingEnabled());
    const [openClip, setOpenClip] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        try {
            const [nextDocuments, nextStats] = await Promise.all([listDocuments(), getStats()]);
            setDocuments(nextDocuments);
            setStats(nextStats);
            if (openDocId) setClips(await listClips(openDocId));
        } catch (error) {
            console.warn('Could not read audio cache:', error);
        }
    }, [openDocId]);

    useEffect(() => { void getStats().then(setStats).catch(() => { }); }, []);
    useEffect(() => { if (isExpanded) void refresh(); }, [isExpanded, refresh]);

    useEffect(() => subscribe((event: CacheEvent) => {
        if (event.type === 'changed' || event.type === 'removed') {
            void getStats().then(setStats).catch(() => { });
            if (isExpanded) void refresh();
            return;
        }
        setActivity(event.state === 'idle'
            ? null
            : { index: event.index, text: event.text, state: event.state, at: Date.now() });
    }), [isExpanded, refresh]);

    useEffect(() => {
        if (!activity || activity.state === 'generating') return;
        const id = window.setTimeout(() => setActivity(null), 2500);
        return () => window.clearTimeout(id);
    }, [activity]);

    const withBusy = useCallback(async (operation: () => Promise<unknown>) => {
        setBusy(true);
        try {
            await operation();
            await refresh();
        } finally {
            setBusy(false);
        }
    }, [refresh]);

    const openDocument = useCallback(async (id: string) => {
        if (openDocId === id) {
            setOpenDocId(null);
            setClips([]);
            return;
        }
        setOpenDocId(id);
        setClips(await listClips(id));
    }, [openDocId]);

    const removeDocument = useCallback((document: DocumentSummary) => withBusy(async () => {
        await deleteDocument(document.documentId);
        if (openDocId === document.documentId) {
            setOpenDocId(null);
            setClips([]);
        }
    }), [openDocId, withBusy]);

    const clearCache = useCallback(() => withBusy(async () => {
        await clearAll();
        setOpenDocId(null);
        setClips([]);
    }), [withBusy]);

    return {
        isExpanded,
        documents,
        stats,
        openDocId,
        clips,
        limits,
        busy,
        activity,
        saving,
        streaming,
        openClip,
        toggleExpanded: () => setIsExpanded(value => !value),
        openDocument,
        removeDocument,
        clearCache,
        enforceLimits: () => withBusy(enforceLimits),
        updateLimits: (patch: Partial<CacheLimits>) => setLimitsState(setLimits(patch)),
        toggleSaving: () => setSaving(setSavingEnabled(!saving)),
        toggleStreaming: () => setStreaming(setStreamingEnabled(!streaming)),
        toggleClipDetails: (key: string) => setOpenClip(value => value === key ? null : key),
        toggleClipLive: (clip: ClipMeta) => withBusy(() => setLiveOnly(clip.key, !clip.liveOnly)),
        removeClip: (clip: ClipMeta) => withBusy(() => deleteClip(clip.key)),
    };
};

export type AudioCacheManagerState = ReturnType<typeof useAudioCacheManager>;
