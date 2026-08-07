import React from 'react';
import { formatBytes } from '../../utils/audioCache';
import type { AudioCacheManagerState } from './useAudioCacheManager';

interface Props {
    cache: AudioCacheManagerState;
}

const AudioCachePolicyControls: React.FC<Props> = ({ cache }) => {
    const usagePct = cache.limits.maxBytes > 0
        ? Math.min(100, (cache.stats.bytes / cache.limits.maxBytes) * 100)
        : 0;

    const clearAll = () => {
        if (confirm(`Delete all ${cache.stats.clips} saved clips (${formatBytes(cache.stats.bytes)})?`)) {
            void cache.clearCache();
        }
    };

    return (
        <>
            <div>
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>{formatBytes(cache.stats.bytes)} of {formatBytes(cache.limits.maxBytes)}</span>
                    <span>{usagePct.toFixed(0)}%</span>
                </div>
                <div className="h-1.5 w-full bg-gray-700 rounded-full overflow-hidden">
                    <div
                        className={`h-full rounded-full transition-all ${usagePct > 90 ? 'bg-red-500' : 'bg-blue-500'}`}
                        style={{ width: `${usagePct}%` }}
                    />
                </div>
            </div>

            <div className="flex flex-wrap items-end gap-3">
                <label className="text-xs text-gray-400">
                    Keep up to
                    <select
                        value={cache.limits.maxBytes}
                        onChange={event => cache.updateLimits({ maxBytes: Number(event.target.value) })}
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
                        value={cache.limits.maxAgeDays}
                        onChange={event => cache.updateLimits({ maxAgeDays: Number(event.target.value) })}
                        className="ml-2 bg-gray-800 border border-gray-600 text-white text-xs rounded p-1"
                    >
                        <option value={7}>7 days</option>
                        <option value={30}>30 days</option>
                        <option value={90}>90 days</option>
                        <option value={3650}>never</option>
                    </select>
                </label>
                <Toggle
                    checked={cache.saving}
                    onClick={cache.toggleSaving}
                    label={cache.saving ? 'Saving on' : 'Saving off - every passage generated live'}
                />
                <Toggle
                    checked={cache.streaming}
                    onClick={cache.toggleStreaming}
                    label={cache.streaming ? 'Play while generating' : 'Play only complete passages'}
                    title={'Start a passage as soon as part of it exists, instead of waiting for the whole thing. '
                        + 'Removes the pause when the look-ahead falls behind, at the risk of the audio running '
                        + 'dry mid-sentence if generation cannot keep up.'}
                />
                <button
                    disabled={cache.busy}
                    onClick={() => { void cache.enforceLimits(); }}
                    className="text-xs px-2 py-1 rounded border border-gray-600 text-gray-300 hover:text-white disabled:opacity-50"
                >
                    Apply now
                </button>
                <button
                    disabled={cache.busy || cache.stats.clips === 0}
                    onClick={clearAll}
                    className="text-xs px-2 py-1 rounded border border-red-700 text-red-400 hover:text-red-300 disabled:opacity-50"
                >
                    Delete all
                </button>
            </div>
        </>
    );
};

const Toggle: React.FC<{
    checked: boolean;
    label: string;
    onClick: () => void;
    title?: string;
}> = ({ checked, label, onClick, title }) => (
    <label className="text-xs text-gray-400 flex items-center gap-2" title={title}>
        <button
            type="button"
            role="switch"
            aria-checked={checked}
            onClick={onClick}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${checked ? 'bg-blue-600' : 'bg-gray-600'}`}
        >
            <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${checked ? 'translate-x-5' : 'translate-x-1'}`} />
        </button>
        {label}
    </label>
);

export default AudioCachePolicyControls;
