import React from 'react';
import { formatBytes } from '../utils/audioCache';
import AudioCacheDocumentList from './audioCache/AudioCacheDocumentList';
import AudioCachePolicyControls from './audioCache/AudioCachePolicyControls';
import { useAudioCacheManager } from './audioCache/useAudioCacheManager';

interface Props {
    /** Document currently loaded in the reader, so it can be surfaced first. */
    activeDocumentId: string | null;
    /** Current source passages, used to detect stale or drifting narration. */
    activeSentences?: string[];
    /** Move the reader to the passage represented by a stored clip. */
    onJumpToSentence?: (index: number) => void;
}

const AudioCacheManager: React.FC<Props> = ({
    activeDocumentId,
    activeSentences,
    onJumpToSentence,
}) => {
    const cache = useAudioCacheManager();

    return (
        <div className="bg-gray-900/60 rounded-lg border border-gray-700/30">
            <button
                onClick={cache.toggleExpanded}
                className="w-full flex items-center justify-between gap-2 p-3 text-left"
            >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 min-w-0">
                    <h3 className="text-sm font-medium text-white whitespace-nowrap">Saved Audio</h3>
                    <span className="text-xs text-gray-400 whitespace-nowrap">
                        {cache.stats.clips} clip{cache.stats.clips === 1 ? '' : 's'} · {formatBytes(cache.stats.bytes)}
                        {cache.stats.documents > 0 && ` · ${cache.stats.documents} document${cache.stats.documents === 1 ? '' : 's'}`}
                    </span>
                    {cache.activity && (
                        <span className={`text-xs flex items-center gap-1 min-w-0 ${cache.activity.state === 'generating' ? 'text-blue-300' : 'text-green-400'}`}>
                            {cache.activity.state === 'generating' && (
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse shrink-0" />
                            )}
                            <span className="truncate">
                                {cache.activity.state === 'generating' && `generating #${cache.activity.index}…`}
                                {cache.activity.state === 'hit' && `#${cache.activity.index} from cache`}
                                {cache.activity.state === 'saved' && `#${cache.activity.index} saved`}
                            </span>
                        </span>
                    )}
                </div>
                <span className="text-gray-400 text-sm shrink-0">{cache.isExpanded ? '▼' : '▶'}</span>
            </button>

            {cache.isExpanded && (
                <div className="p-4 pt-0 space-y-4">
                    <p className="text-xs text-gray-500">
                        Generated narration is kept so replaying a passage costs no API call.
                        Stored in this browser; clearing site data clears it too.
                    </p>
                    <AudioCachePolicyControls cache={cache} />
                    <AudioCacheDocumentList
                        cache={cache}
                        activeDocumentId={activeDocumentId}
                        activeSentences={activeSentences}
                        onJumpToSentence={onJumpToSentence}
                    />
                </div>
            )}
        </div>
    );
};

export default AudioCacheManager;
