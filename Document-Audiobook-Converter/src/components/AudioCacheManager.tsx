import React, { useCallback, useEffect, useState } from 'react';
import {
    ClipMeta, DocumentSummary, CacheLimits, CacheEvent,
    listDocuments, listClips, deleteClip, deleteDocument, clearAll,
    getStats, setLiveOnly, getLimits, setLimits, enforceLimits,
    formatBytes, formatDuration, subscribe,
    compareNarration, isSavingEnabled, setSavingEnabled, MatchLevel,
} from '../utils/audioCache';

interface Activity {
    index: number;
    text: string;
    state: 'generating' | 'hit' | 'saved' | 'idle';
    at: number;
}

interface Props {
    /** Document currently loaded in the reader, so it can be surfaced first. */
    activeDocumentId: string | null;
    /**
     * The loaded document's sentences as they read right now. A stored clip is
     * compared against the text at its own position, so an edit to the source
     * shows up as a changed marker rather than silently stale audio.
     */
    activeSentences?: string[];
}

/**
 * Oversight for stored narration audio: what is held, for which document, and
 * what to throw away. Clips are scoped per document, so opening one book never
 * shows another's audio.
 */
const MARKER_STYLES: Record<MatchLevel, { dot: string; text: string }> = {
    match:    { dot: 'bg-green-400',  text: 'text-green-400' },
    drift:    { dot: 'bg-amber-400',  text: 'text-amber-400' },
    diverged: { dot: 'bg-red-500',    text: 'text-red-400' },
    unknown:  { dot: 'bg-gray-600',   text: 'text-gray-500' },
};

const AudioCacheManager: React.FC<Props> = ({ activeDocumentId, activeSentences }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [documents, setDocuments] = useState<DocumentSummary[]>([]);
    const [stats, setStats] = useState({ clips: 0, bytes: 0, documents: 0 });
    const [openDocId, setOpenDocId] = useState<string | null>(null);
    const [clips, setClips] = useState<ClipMeta[]>([]);
    const [limits, setLimitsState] = useState<CacheLimits>(getLimits());
    const [busy, setBusy] = useState(false);
    const [activity, setActivity] = useState<Activity | null>(null);
    const [saving, setSaving] = useState<boolean>(isSavingEnabled());
    const [openClip, setOpenClip] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        try {
            const [docs, s] = await Promise.all([listDocuments(), getStats()]);
            setDocuments(docs);
            setStats(s);
            if (openDocId) setClips(await listClips(openDocId));
        } catch (error) {
            console.warn('Could not read audio cache:', error);
        }
    }, [openDocId]);

    // Load the totals once on mount, not only when opened - the collapsed
    // header is the only hint that anything is stored at all.
    useEffect(() => { void getStats().then(setStats).catch(() => { }); }, []);

    useEffect(() => { if (isExpanded) void refresh(); }, [isExpanded, refresh]);

    // Follow the cache as it changes rather than polling it.
    //
    // This panel used to re-read on a 4s timer, and only while expanded: the
    // collapsed header never moved, and an open panel showed figures up to four
    // seconds behind the work being done. Writes and engine progress now
    // announce themselves, so what is on screen matches what is happening.
    useEffect(() => {
        const unsubscribe = subscribe((event: CacheEvent) => {
            if (event.type === 'changed') {
                // Totals matter even when collapsed; the listings only when open.
                void getStats().then(setStats).catch(() => { });
                if (isExpanded) void refresh();
                return;
            }
            setActivity(
                event.state === 'idle'
                    ? null
                    : { index: event.index, text: event.text, state: event.state, at: Date.now() },
            );
        });
        return unsubscribe;
    }, [isExpanded, refresh]);

    // Let a finished note fade out rather than sit there implying live work.
    useEffect(() => {
        if (!activity || activity.state === 'generating') return;
        const id = window.setTimeout(() => setActivity(null), 2500);
        return () => window.clearTimeout(id);
    }, [activity]);

    const withBusy = async (fn: () => Promise<unknown>) => {
        setBusy(true);
        try { await fn(); await refresh(); } finally { setBusy(false); }
    };

    const openDocument = async (id: string) => {
        if (openDocId === id) { setOpenDocId(null); setClips([]); return; }
        setOpenDocId(id);
        setClips(await listClips(id));
    };

    const usagePct = limits.maxBytes > 0
        ? Math.min(100, (stats.bytes / limits.maxBytes) * 100)
        : 0;

    return (
        <div className="bg-gray-900/60 rounded-lg border border-gray-700/30">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-between gap-2 p-3 text-left"
            >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 min-w-0">
                    <h3 className="text-sm font-medium text-white whitespace-nowrap">Saved Audio</h3>
                    <span className="text-xs text-gray-400 whitespace-nowrap">
                        {stats.clips} clip{stats.clips === 1 ? '' : 's'} · {formatBytes(stats.bytes)}
                        {stats.documents > 0 && ` · ${stats.documents} document${stats.documents === 1 ? '' : 's'}`}
                    </span>
                    {activity && (
                        <span className={`text-xs flex items-center gap-1 min-w-0 ${activity.state === 'generating' ? 'text-blue-300' : 'text-green-400'}`}>
                            {activity.state === 'generating' && (
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse shrink-0" />
                            )}
                            <span className="truncate">
                                {activity.state === 'generating' && `generating #${activity.index}…`}
                                {activity.state === 'hit' && `#${activity.index} from cache`}
                                {activity.state === 'saved' && `#${activity.index} saved`}
                            </span>
                        </span>
                    )}
                </div>
                <span className="text-gray-400 text-sm shrink-0">{isExpanded ? '▼' : '▶'}</span>
            </button>

            {isExpanded && (
                <div className="p-4 pt-0 space-y-4">
                    <p className="text-xs text-gray-500">
                        Generated narration is kept so replaying a passage costs no API call.
                        Stored in this browser; clearing site data clears it too.
                    </p>

                    {/* Usage against the cap */}
                    <div>
                        <div className="flex justify-between text-xs text-gray-400 mb-1">
                            <span>{formatBytes(stats.bytes)} of {formatBytes(limits.maxBytes)}</span>
                            <span>{usagePct.toFixed(0)}%</span>
                        </div>
                        <div className="h-1.5 w-full bg-gray-700 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full transition-all ${usagePct > 90 ? 'bg-red-500' : 'bg-blue-500'}`}
                                style={{ width: `${usagePct}%` }}
                            />
                        </div>
                    </div>

                    {/* Retention settings */}
                    <div className="flex flex-wrap items-end gap-3">
                        <label className="text-xs text-gray-400">
                            Keep up to
                            <select
                                value={limits.maxBytes}
                                onChange={e => setLimitsState(setLimits({ maxBytes: Number(e.target.value) }))}
                                className="ml-2 bg-gray-800 border border-gray-600 text-white text-xs rounded p-1"
                            >
                                <option value={250 * 1024 * 1024}>250 MB</option>
                                <option value={500 * 1024 * 1024}>500 MB</option>
                                <option value={750 * 1024 * 1024}>750 MB</option>
                                <option value={1536 * 1024 * 1024}>1.5 GB</option>
                                <option value={3072 * 1024 * 1024}>3 GB</option>
                            </select>
                        </label>
                        <label className="text-xs text-gray-400">
                            Discard unused after
                            <select
                                value={limits.maxAgeDays}
                                onChange={e => setLimitsState(setLimits({ maxAgeDays: Number(e.target.value) }))}
                                className="ml-2 bg-gray-800 border border-gray-600 text-white text-xs rounded p-1"
                            >
                                <option value={7}>7 days</option>
                                <option value={30}>30 days</option>
                                <option value={90}>90 days</option>
                                <option value={3650}>never</option>
                            </select>
                        </label>
                        <label className="text-xs text-gray-400 flex items-center gap-2">
                            <button
                                type="button"
                                role="switch"
                                aria-checked={saving}
                                onClick={() => setSaving(setSavingEnabled(!saving))}
                                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${saving ? 'bg-blue-600' : 'bg-gray-600'}`}
                            >
                                <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${saving ? 'translate-x-5' : 'translate-x-1'}`} />
                            </button>
                            {saving ? 'Saving on' : 'Saving off - every passage generated live'}
                        </label>
                        <button
                            disabled={busy}
                            onClick={() => withBusy(enforceLimits)}
                            className="text-xs px-2 py-1 rounded border border-gray-600 text-gray-300 hover:text-white disabled:opacity-50"
                        >
                            Apply now
                        </button>
                        <button
                            disabled={busy || stats.clips === 0}
                            onClick={() => withBusy(async () => {
                                if (confirm(`Delete all ${stats.clips} saved clips (${formatBytes(stats.bytes)})?`)) {
                                    await clearAll();
                                    setOpenDocId(null); setClips([]);
                                }
                            })}
                            className="text-xs px-2 py-1 rounded border border-red-700 text-red-400 hover:text-red-300 disabled:opacity-50"
                        >
                            Delete all
                        </button>
                    </div>

                    {/* Per-document listing */}
                    {documents.length === 0 ? (
                        <p className="text-xs text-gray-500 italic">
                            Nothing saved yet. Play something with the Gemini engine and it will appear here.
                        </p>
                    ) : (
                        <div className="space-y-1 max-h-72 overflow-y-auto">
                            {documents.map(doc => (
                                <div key={doc.documentId} className="rounded border border-gray-700/40">
                                    <div className="flex items-center justify-between gap-2 p-2">
                                        <button
                                            onClick={() => openDocument(doc.documentId)}
                                            className="flex-1 text-left min-w-0"
                                        >
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-gray-400">
                                                    {openDocId === doc.documentId ? '▼' : '▶'}
                                                </span>
                                                <span className="text-sm text-white truncate">
                                                    {doc.documentName || 'Untitled document'}
                                                </span>
                                                {doc.documentId === activeDocumentId && (
                                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-600/30 text-blue-300 whitespace-nowrap">
                                                        open now
                                                    </span>
                                                )}
                                            </div>
                                            <div className="text-xs text-gray-500 mt-0.5 ml-5">
                                                {doc.clips} clips · {formatBytes(doc.bytes)} · {formatDuration(doc.durationSec)}
                                            </div>
                                        </button>
                                        <button
                                            disabled={busy}
                                            onClick={() => withBusy(async () => {
                                                if (confirm(`Delete ${doc.clips} clips for "${doc.documentName}"?`)) {
                                                    await deleteDocument(doc.documentId);
                                                    if (openDocId === doc.documentId) { setOpenDocId(null); setClips([]); }
                                                }
                                            })}
                                            className="text-xs px-2 py-1 rounded border border-gray-600 text-gray-400 hover:text-red-300 hover:border-red-700 disabled:opacity-50 whitespace-nowrap"
                                        >
                                            Delete
                                        </button>
                                    </div>

                                    {openDocId === doc.documentId && (
                                        <div className="border-t border-gray-700/40 divide-y divide-gray-800">
                                            {clips.map(clip => {
                                                const currentText = activeSentences && doc.documentId === activeDocumentId
                                                    ? activeSentences[clip.index]
                                                    : undefined;
                                                // Compare against the document as it reads now when we
                                                // have it, otherwise against the text the clip was made
                                                // from. The first catches an edited source, the second
                                                // catches narration that wandered.
                                                const compareAgainst = currentText ?? clip.text;
                                                const match = compareNarration(compareAgainst, clip.spokenText);
                                                const sourceChanged = currentText !== undefined && currentText !== clip.text;
                                                const style = MARKER_STYLES[match.level];
                                                const isOpen = openClip === clip.key;
                                                return (
                                                <div key={clip.key} className="p-2 pl-5">
                                                    <div className="flex items-start gap-2">
                                                        <span
                                                            title={match.label}
                                                            className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${style.dot}`}
                                                        />
                                                        <span className="text-[10px] text-gray-600 w-7 shrink-0 pt-0.5">
                                                            #{clip.index}
                                                        </span>
                                                        <button
                                                            onClick={() => setOpenClip(isOpen ? null : clip.key)}
                                                            className="flex-1 min-w-0 text-left"
                                                        >
                                                            <p className="text-xs text-gray-300 truncate">{compareAgainst || clip.text}</p>
                                                            <p className="text-[10px] mt-0.5 flex flex-wrap gap-x-2">
                                                                <span className="text-gray-500">
                                                                    {formatDuration(clip.durationSec)} · {formatBytes(clip.bytes)} · {clip.voice}
                                                                </span>
                                                                <span className={style.text}>{match.label}</span>
                                                                {match.wordDelta > 2 && (
                                                                    <span className="text-amber-400">+{match.wordDelta} words spoken</span>
                                                                )}
                                                                {sourceChanged && (
                                                                    <span className="text-amber-300">source text has changed</span>
                                                                )}
                                                                {clip.liveOnly && (
                                                                    <span className="text-amber-400">regenerates next play</span>
                                                                )}
                                                            </p>
                                                        </button>
                                                        <button
                                                            disabled={busy}
                                                            title={clip.liveOnly
                                                                ? 'Use the saved audio again'
                                                                : 'Ignore the saved audio and generate this one fresh next time'}
                                                            onClick={() => withBusy(() => setLiveOnly(clip.key, !clip.liveOnly))}
                                                            className={`text-[10px] px-1.5 py-0.5 rounded border whitespace-nowrap disabled:opacity-50 ${clip.liveOnly
                                                                ? 'border-amber-600 text-amber-300'
                                                                : 'border-gray-600 text-gray-400 hover:text-white'}`}
                                                        >
                                                            {clip.liveOnly ? 'Live' : 'Saved'}
                                                        </button>
                                                        <button
                                                            disabled={busy}
                                                            title="Delete this clip so it regenerates from the current text"
                                                            onClick={() => withBusy(() => deleteClip(clip.key))}
                                                            className="text-[10px] px-1.5 py-0.5 rounded border border-gray-600 text-gray-400 hover:text-red-300 hover:border-red-700 disabled:opacity-50"
                                                        >
                                                            ✕
                                                        </button>
                                                    </div>

                                                    {isOpen && (
                                                        <div className="mt-2 ml-9 space-y-2 text-[11px]">
                                                            <div>
                                                                <p className="text-gray-500 mb-0.5">
                                                                    Source text{sourceChanged ? ' (current)' : ''}
                                                                </p>
                                                                <p className="text-gray-300 bg-gray-800/50 rounded p-2 whitespace-pre-wrap">
                                                                    {compareAgainst || '(none)'}
                                                                </p>
                                                            </div>
                                                            {sourceChanged && (
                                                                <div>
                                                                    <p className="text-gray-500 mb-0.5">Text this audio was made from</p>
                                                                    <p className="text-gray-400 bg-gray-800/50 rounded p-2 whitespace-pre-wrap">
                                                                        {clip.text}
                                                                    </p>
                                                                </div>
                                                            )}
                                                            <div>
                                                                <p className="text-gray-500 mb-0.5">What the model actually said</p>
                                                                <p className={`bg-gray-800/50 rounded p-2 whitespace-pre-wrap ${clip.spokenText ? 'text-gray-300' : 'text-gray-600 italic'}`}>
                                                                    {clip.spokenText || 'no transcript stored for this clip'}
                                                                </p>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                                );
                                            })}
                                            {clips.length === 0 && (
                                                <p className="text-xs text-gray-500 italic p-2 pl-5">No clips.</p>
                                            )}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default AudioCacheManager;
