import React from 'react';
import { formatBytes, formatDuration } from '../../utils/audioCache';
import type { DocumentSummary } from '../../utils/audioCache';
import AudioCacheClipRow from './AudioCacheClipRow';
import type { AudioCacheManagerState } from './useAudioCacheManager';

interface Props {
    cache: AudioCacheManagerState;
    activeDocumentId: string | null;
    activeSentences?: string[];
    onJumpToSentence?: (index: number) => void;
}

const AudioCacheDocumentList: React.FC<Props> = ({
    cache,
    activeDocumentId,
    activeSentences,
    onJumpToSentence,
}) => {
    if (cache.documents.length === 0) {
        return (
            <p className="text-xs text-gray-500 italic">
                Nothing saved yet. Play something with the Gemini engine and it will appear here.
            </p>
        );
    }

    const removeDocument = (document: DocumentSummary) => {
        if (confirm(`Delete ${document.clips} clips for "${document.documentName}"?`)) {
            void cache.removeDocument(document);
        }
    };

    return (
        <div className="space-y-1 max-h-72 overflow-y-auto">
            {cache.documents.map(document => (
                <div key={document.documentId} className="rounded border border-gray-700/40">
                    <div className="flex items-center justify-between gap-2 p-2">
                        <button
                            onClick={() => { void cache.openDocument(document.documentId); }}
                            className="flex-1 text-left min-w-0"
                        >
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-400">
                                    {cache.openDocId === document.documentId ? '▼' : '▶'}
                                </span>
                                <span className="text-sm text-white truncate">
                                    {document.documentName || 'Untitled document'}
                                </span>
                                {document.documentId === activeDocumentId && (
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-600/30 text-blue-300 whitespace-nowrap">
                                        open now
                                    </span>
                                )}
                            </div>
                            <div className="text-xs text-gray-500 mt-0.5 ml-5">
                                {document.clips} clips · {formatBytes(document.bytes)} · {formatDuration(document.durationSec)}
                            </div>
                        </button>
                        <button
                            disabled={cache.busy}
                            onClick={() => removeDocument(document)}
                            className="text-xs px-2 py-1 rounded border border-gray-600 text-gray-400 hover:text-red-300 hover:border-red-700 disabled:opacity-50 whitespace-nowrap"
                        >
                            Delete
                        </button>
                    </div>

                    {cache.openDocId === document.documentId && (
                        <div className="border-t border-gray-700/40 divide-y divide-gray-800">
                            {cache.clips.map(clip => (
                                <AudioCacheClipRow
                                    key={clip.key}
                                    clip={clip}
                                    documentId={document.documentId}
                                    activeDocumentId={activeDocumentId}
                                    activeSentences={activeSentences}
                                    busy={cache.busy}
                                    expanded={cache.openClip === clip.key}
                                    onToggleDetails={() => cache.toggleClipDetails(clip.key)}
                                    onJumpToSentence={onJumpToSentence}
                                    onToggleLive={() => { void cache.toggleClipLive(clip); }}
                                    onDelete={() => { void cache.removeClip(clip); }}
                                />
                            ))}
                            {cache.clips.length === 0 && (
                                <p className="text-xs text-gray-500 italic p-2 pl-5">No clips.</p>
                            )}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
};

export default AudioCacheDocumentList;
