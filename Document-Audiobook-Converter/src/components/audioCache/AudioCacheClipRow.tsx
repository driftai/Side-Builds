import React from 'react';
import {
    compareNarration,
    formatBytes,
    formatDuration,
} from '../../utils/audioCache';
import type { ClipMeta, MatchLevel } from '../../utils/audioCache';

interface Props {
    clip: ClipMeta;
    documentId: string;
    activeDocumentId: string | null;
    activeSentences?: string[];
    busy: boolean;
    expanded: boolean;
    onToggleDetails: () => void;
    onJumpToSentence?: (index: number) => void;
    onToggleLive: () => void;
    onDelete: () => void;
}

const markerStyles: Record<MatchLevel, { dot: string; text: string }> = {
    match: { dot: 'bg-green-400', text: 'text-green-400' },
    drift: { dot: 'bg-amber-400', text: 'text-amber-400' },
    diverged: { dot: 'bg-red-500', text: 'text-red-400' },
    unknown: { dot: 'bg-gray-600', text: 'text-gray-500' },
};

const shortModelName = (model: string): string => model
    .replace(/^models\//, '')
    .replace(/^gemini-/, '')
    .replace(/-preview(-\d{2}-\d{4})?$/, '')
    .replace(/-latest$/, ' (latest)');

const findJumpTarget = (
    clip: ClipMeta,
    documentId: string,
    activeDocumentId: string | null,
    activeSentences: string[] | undefined,
    enabled: boolean,
): number | null => {
    if (!enabled || !activeSentences?.length || documentId !== activeDocumentId) return null;
    if (activeSentences[clip.index] === clip.text) return clip.index;
    const movedIndex = activeSentences.indexOf(clip.text);
    if (movedIndex >= 0) return movedIndex;
    return clip.index < activeSentences.length ? clip.index : null;
};

const AudioCacheClipRow: React.FC<Props> = ({
    clip,
    documentId,
    activeDocumentId,
    activeSentences,
    busy,
    expanded,
    onToggleDetails,
    onJumpToSentence,
    onToggleLive,
    onDelete,
}) => {
    const currentText = activeSentences && documentId === activeDocumentId
        ? activeSentences[clip.index]
        : undefined;
    const compareAgainst = currentText ?? clip.text;
    const match = compareNarration(compareAgainst, clip.spokenText, clip.durationSec);
    const sourceChanged = currentText !== undefined && currentText !== clip.text;
    const style = markerStyles[match.level];
    const jumpTarget = findJumpTarget(
        clip,
        documentId,
        activeDocumentId,
        activeSentences,
        Boolean(onJumpToSentence),
    );

    return (
        <div className="p-2 pl-5">
            <div className="flex items-start gap-2">
                <span title={match.label} className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${style.dot}`} />
                <span className="text-[10px] text-gray-600 w-7 shrink-0 pt-0.5">#{clip.index}</span>
                <button onClick={onToggleDetails} className="flex-1 min-w-0 text-left">
                    <p className="text-xs text-gray-300 truncate">{compareAgainst || clip.text}</p>
                    <p className="text-[10px] mt-0.5 flex flex-wrap gap-x-2">
                        <span className="text-gray-500" title={clip.model || 'model not recorded'}>
                            {formatDuration(clip.durationSec)} · {formatBytes(clip.bytes)} · {clip.voice}
                            {clip.model && <> · {shortModelName(clip.model)}</>}
                        </span>
                        <span className={style.text}>{match.label}</span>
                        {match.wordDelta > 2 && <span className="text-amber-400">+{match.wordDelta} words spoken</span>}
                        {sourceChanged && <span className="text-amber-300">source text has changed</span>}
                        {clip.liveOnly && <span className="text-amber-400">regenerates next play</span>}
                    </p>
                </button>
                {jumpTarget !== null && (
                    <button
                        title={jumpTarget === clip.index
                            ? `Go to passage ${jumpTarget} in the document`
                            : `Go to this passage - it has moved to ${jumpTarget} since the audio was made`}
                        onClick={() => onJumpToSentence?.(jumpTarget)}
                        className="text-[10px] px-1.5 py-0.5 rounded border border-gray-600 text-gray-400 hover:text-blue-300 hover:border-blue-600 whitespace-nowrap"
                    >
                        Go to
                    </button>
                )}
                <button
                    disabled={busy}
                    title={clip.liveOnly ? 'Use the saved audio again' : 'Generate this passage fresh next time'}
                    onClick={onToggleLive}
                    className={`text-[10px] px-1.5 py-0.5 rounded border whitespace-nowrap disabled:opacity-50 ${clip.liveOnly
                        ? 'border-amber-600 text-amber-300'
                        : 'border-gray-600 text-gray-400 hover:text-white'}`}
                >
                    {clip.liveOnly ? 'Live' : 'Saved'}
                </button>
                <button
                    disabled={busy}
                    title="Delete this clip so it regenerates from the current text"
                    onClick={onDelete}
                    className="text-[10px] px-1.5 py-0.5 rounded border border-gray-600 text-gray-400 hover:text-red-300 hover:border-red-700 disabled:opacity-50"
                >
                    ✕
                </button>
            </div>

            {expanded && (
                <div className="mt-2 ml-9 space-y-2 text-[11px]">
                    <div>
                        <p className="text-gray-500 mb-0.5">Source text{sourceChanged ? ' (current)' : ''}</p>
                        <p className="text-gray-300 bg-gray-800/50 rounded p-2 whitespace-pre-wrap">
                            {compareAgainst || '(none)'}
                        </p>
                    </div>
                    {sourceChanged && (
                        <div>
                            <p className="text-gray-500 mb-0.5">Text this audio was made from</p>
                            <p className="text-gray-400 bg-gray-800/50 rounded p-2 whitespace-pre-wrap">{clip.text}</p>
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
};

export default AudioCacheClipRow;
