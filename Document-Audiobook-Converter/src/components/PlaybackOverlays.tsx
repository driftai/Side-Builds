import React from 'react';
import { createPortal } from 'react-dom';
import { isElectronRuntime } from '../integrations/electronBridge';
import type { PlaybackControlHandlers } from '../types/playback';
import { AppState } from '../types/playback';
import PlayerControls from './PlayerControls';

interface PlaybackOverlaysProps extends PlaybackControlHandlers {
    appState: AppState;
    currentSentenceIndex: number;
    sentences: string[];
    fileName: string;
    documentOpen: boolean;
    pipWindow: Window | null;
    pipCompact: boolean;
    onTogglePipCompact: () => void;
    floatingControls: boolean;
    floatingAt: { x: number; y: number };
    onFloatingAtChange: (at: { x: number; y: number }) => void;
    onCloseFloating: () => void;
}

const currentText = (
    sentences: string[],
    currentSentenceIndex: number,
): string => (
    currentSentenceIndex >= 0 && currentSentenceIndex < sentences.length
        ? sentences[currentSentenceIndex]
        : 'Press play to start listening.'
);

const PlaybackOverlays: React.FC<PlaybackOverlaysProps> = ({
    appState,
    currentSentenceIndex,
    sentences,
    fileName,
    documentOpen,
    pipWindow,
    pipCompact,
    onTogglePipCompact,
    floatingControls,
    floatingAt,
    onFloatingAtChange,
    onCloseFloating,
    onPlay,
    onPause,
    onStop,
    onSkipForward,
    onSkipBackward,
}) => {
    const controls = (
        <PlayerControls
            appState={appState}
            currentSentenceIndex={currentSentenceIndex}
            totalSentences={sentences.length}
            onPlay={onPlay}
            onPause={onPause}
            onStop={onStop}
            onSkipForward={onSkipForward}
            onSkipBackward={onSkipBackward}
        />
    );

    return (
        <>
            {pipWindow && createPortal(
                <div className={`w-full h-full bg-gray-900 text-white flex flex-col justify-between font-sans ${pipCompact ? 'p-1.5' : 'p-3'}`}>
                    <div className="flex items-baseline justify-between gap-2">
                        <span className="text-[11px] text-gray-400 whitespace-nowrap">
                            Clip #{currentSentenceIndex >= 0 ? currentSentenceIndex : '-'} of {sentences.length}
                        </span>
                        <div className="flex items-center gap-2 min-w-0">
                            {!pipCompact && (
                                <span className="text-[10px] text-gray-600 truncate">
                                    {fileName}
                                </span>
                            )}
                            <button
                                onClick={onTogglePipCompact}
                                title={pipCompact ? 'Expand' : 'Minimise to the transport only'}
                                aria-label={pipCompact ? 'Expand controls' : 'Minimise controls'}
                                className="shrink-0 text-gray-500 hover:text-white text-xs leading-none px-1"
                            >
                                {pipCompact ? '▣' : '▁'}
                            </button>
                        </div>
                    </div>
                    {!pipCompact && (
                        <p className="text-xs text-blue-300/90 italic my-2 leading-snug line-clamp-3">
                            {currentText(sentences, currentSentenceIndex)}
                        </p>
                    )}
                    {controls}
                </div>,
                pipWindow.document.body,
            )}

            {floatingControls && !isElectronRuntime && documentOpen && (
                <div
                    className="fixed z-50 w-64 rounded-lg border border-blue-500/30 bg-gray-900/95 backdrop-blur-md shadow-2xl shadow-black/50"
                    style={{ left: floatingAt.x, top: floatingAt.y }}
                >
                    <div
                        className="flex items-center justify-between px-3 py-1.5 border-b border-gray-700/40 cursor-move select-none"
                        onPointerDown={event => {
                            const startX = event.clientX - floatingAt.x;
                            const startY = event.clientY - floatingAt.y;
                            const move = (pointerEvent: PointerEvent) => {
                                onFloatingAtChange({
                                    x: Math.max(
                                        0,
                                        Math.min(
                                            pointerEvent.clientX - startX,
                                            window.innerWidth - 256,
                                        ),
                                    ),
                                    y: Math.max(
                                        0,
                                        Math.min(
                                            pointerEvent.clientY - startY,
                                            window.innerHeight - 80,
                                        ),
                                    ),
                                });
                            };
                            const up = () => {
                                window.removeEventListener('pointermove', move);
                                window.removeEventListener('pointerup', up);
                            };
                            window.addEventListener('pointermove', move);
                            window.addEventListener('pointerup', up);
                        }}
                    >
                        <span className="text-[11px] text-gray-400">
                            Clip #{currentSentenceIndex >= 0 ? currentSentenceIndex : '-'} of {sentences.length}
                        </span>
                        <button
                            onClick={onCloseFloating}
                            className="text-gray-500 hover:text-white text-xs leading-none px-1"
                            aria-label="Close floating controls"
                        >
                            ✕
                        </button>
                    </div>
                    <div className="px-3 py-2">
                        <p className="text-[11px] text-blue-300/90 italic mb-2 line-clamp-2 min-h-[2.2em]">
                            {currentText(sentences, currentSentenceIndex)}
                        </p>
                        {controls}
                    </div>
                </div>
            )}
        </>
    );
};

export default PlaybackOverlays;
