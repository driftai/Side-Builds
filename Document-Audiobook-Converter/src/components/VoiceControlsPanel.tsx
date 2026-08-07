import React from 'react';
import type { GeminiApiConfig, GeminiConnectionState } from '../types/gemini';
import type { PlaybackControlHandlers, VoiceMode } from '../types/playback';
import { AppState } from '../types/playback';
import PlayerControls from './PlayerControls';

const GEMINI_VOICES = [
    'Zephyr', 'Puck', 'Charon', 'Kore', 'Fenrir', 'Leda', 'Orus', 'Aoede',
    'Callirrhoe', 'Autonoe', 'Enceladus', 'Iapetus', 'Umbriel', 'Algieba',
    'Despina', 'Erinome', 'Algenib', 'Rasalgethi', 'Laomedeia', 'Achernar',
    'Alnilam', 'Schedar', 'Gacrux', 'Pulcherrima', 'Achird', 'Zubenelgenubi',
    'Vindemiatrix', 'Sadachbia', 'Sadaltager', 'Sulafat',
];

interface VoiceControlsPanelProps extends PlaybackControlHandlers {
    collapsed: boolean;
    onCollapsedChange: (collapsed: boolean) => void;
    appState: AppState;
    currentSentenceIndex: number;
    sentences: string[];
    voiceMode: VoiceMode;
    onVoiceModeChange: (mode: VoiceMode) => void;
    selectedVoiceURI: string | null;
    onBrowserVoiceChange: (voiceURI: string) => void;
    selectedGeminiVoice: string;
    voices: SpeechSynthesisVoice[];
    geminiConfig: GeminiApiConfig | null;
    onGeminiConfigChange: (config: GeminiApiConfig) => void;
    connectionState: GeminiConnectionState;
    error: string | null;
    detachedActive: boolean;
    isElectron: boolean;
    onToggleDetached: () => void;
}

const VoiceControlsPanel: React.FC<VoiceControlsPanelProps> = ({
    collapsed,
    onCollapsedChange,
    appState,
    currentSentenceIndex,
    sentences,
    voiceMode,
    onVoiceModeChange,
    selectedVoiceURI,
    onBrowserVoiceChange,
    selectedGeminiVoice,
    voices,
    geminiConfig,
    onGeminiConfigChange,
    connectionState,
    error,
    detachedActive,
    isElectron,
    onToggleDetached,
    onPlay,
    onPause,
    onStop,
    onSkipForward,
    onSkipBackward,
}) => {
    const updateGeminiConfig = (updates: Partial<GeminiApiConfig>) => {
        if (!geminiConfig) return;
        onGeminiConfigChange({ ...geminiConfig, ...updates });
    };

    const playerControls = (
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
        <div className={`shrink-0 ${collapsed ? '' : 'max-h-[38dvh] min-h-[8rem]'} bg-gray-900/60 rounded-lg border border-gray-700/30 overflow-hidden relative transition-all duration-300 ease-in-out flex flex-col`}>
            <div
                className="bg-gray-800/40 px-6 py-2 border-b border-gray-700/20 cursor-pointer hover:bg-gray-700/40 transition-colors duration-200"
                onClick={() => onCollapsedChange(!collapsed)}
            >
                <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-400 font-serif flex items-center gap-2">
                        🎛️ Voice Controls
                        <span className={`text-xs transition-transform duration-200 ${collapsed ? 'rotate-90' : ''}`}>
                            {collapsed ? '▶' : '▼'}
                        </span>
                    </div>
                    <div className="flex items-center justify-end gap-3">
                        {collapsed && (
                            <div
                                className="flex items-center justify-center gap-1 self-center mt-[-3px]"
                                onClick={event => event.stopPropagation()}
                            >
                                {playerControls}
                                <button
                                    onClick={event => {
                                        event.stopPropagation();
                                        onToggleDetached();
                                    }}
                                    className={`p-1.5 rounded-md transition-colors duration-200 ${detachedActive && !isElectron
                                        ? 'bg-blue-500/70 text-white'
                                        : 'bg-blue-700/50 text-blue-300 hover:bg-blue-600/50 hover:text-white'}`}
                                    aria-label="Floating controls"
                                    title={isElectron
                                        ? 'Electron floating controls (always on top)'
                                        : 'Detach the playback controls into a window that stays on top'}
                                >
                                    <svg
                                        className="h-3.5 w-3.5"
                                        fill="none"
                                        viewBox="0 0 24 24"
                                        stroke="currentColor"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                                        />
                                    </svg>
                                </button>
                            </div>
                        )}
                        <div className="text-xs text-gray-500">
                            {collapsed ? 'Click to expand' : 'Audio Engine & Playback'}
                        </div>
                    </div>
                </div>
            </div>

            <div className={`p-4 overflow-y-auto space-y-4 transition-all duration-300 ease-in-out ${collapsed
                ? 'max-h-0 opacity-0 invisible'
                : 'grow min-h-0 opacity-100 visible'}`}
            >
                <div className="flex items-center justify-between">
                    <label className="block text-sm font-medium text-gray-400">
                        Voice Engine
                    </label>
                    <button
                        onClick={() => onVoiceModeChange(
                            voiceMode === 'browser' ? 'gemini' : 'browser',
                        )}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900 ${voiceMode === 'gemini' ? 'bg-blue-600' : 'bg-gray-600'}`}
                    >
                        <span
                            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${voiceMode === 'gemini' ? 'translate-x-6' : 'translate-x-1'}`}
                        />
                    </button>
                </div>

                <div className="flex justify-between text-xs text-gray-400">
                    <span className={voiceMode === 'browser' ? 'text-blue-400 font-medium' : ''}>
                        Browser TTS
                    </span>
                    <span className={voiceMode === 'gemini' ? 'text-blue-400 font-medium' : ''}>
                        Gemini Live API
                        {voiceMode === 'gemini' && (
                            <span className="ml-1">
                                {connectionState === 'connected' && '🟢'}
                                {connectionState === 'connecting' && '🟡'}
                                {connectionState === 'error' && '🔴'}
                                {connectionState === 'disconnected' && '⚪'}
                            </span>
                        )}
                        {(!geminiConfig || !geminiConfig.apiKey) && ' (Configure API)'}
                    </span>
                </div>

                <div>
                    <label
                        htmlFor="voice-select"
                        className="block text-sm font-medium text-gray-400 mb-2"
                    >
                        Voice {voiceMode === 'gemini'
                            && (!geminiConfig || !geminiConfig.apiKey)
                            && '(API Key Required)'}
                    </label>
                    <select
                        id="voice-select"
                        value={voiceMode === 'browser'
                            ? (selectedVoiceURI || '')
                            : selectedGeminiVoice}
                        onChange={event => {
                            if (voiceMode === 'browser') {
                                onBrowserVoiceChange(event.target.value);
                            } else {
                                updateGeminiConfig({ voice: event.target.value });
                            }
                        }}
                        disabled={voiceMode === 'browser'
                            ? voices.length === 0
                            : !geminiConfig}
                        className="w-full bg-gray-800 border border-gray-600 text-white text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2.5"
                        aria-label="Select a voice for text-to-speech"
                    >
                        {voiceMode === 'browser' ? (
                            voices.length === 0 ? (
                                <option>Loading voices...</option>
                            ) : (
                                voices.map(voice => (
                                    <option key={voice.voiceURI} value={voice.voiceURI}>
                                        {`${voice.name} (${voice.lang})`}
                                    </option>
                                ))
                            )
                        ) : (
                            !geminiConfig ? (
                                <option>Loading voices...</option>
                            ) : (
                                GEMINI_VOICES.map(voice => (
                                    <option key={voice} value={voice}>
                                        {voice}
                                    </option>
                                ))
                            )
                        )}
                    </select>
                </div>

                {voiceMode === 'gemini' && (
                    <div className="mt-3">
                        <div className="flex items-center justify-between mb-2">
                            <label className="block text-sm font-medium text-gray-400">
                                Instructions (optional)
                            </label>
                            {geminiConfig?.instructions && (
                                <button
                                    onClick={() => updateGeminiConfig({ instructions: '' })}
                                    className="text-xs text-gray-400 hover:text-white transition-colors"
                                >
                                    Clear
                                </button>
                            )}
                        </div>
                        <textarea
                            value={geminiConfig?.instructions || ''}
                            onChange={event => {
                                if (event.target.value.length <= 8000) {
                                    updateGeminiConfig({
                                        instructions: event.target.value,
                                    });
                                }
                            }}
                            placeholder="e.g., 'You are a professional audiobook narrator with clear pronunciation and natural pacing.'"
                            rows={2}
                            className="w-full bg-gray-700 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                            maxLength={8000}
                        />
                        <div className="flex items-center justify-between mt-1">
                            <div className="text-xs text-gray-500">
                                {(geminiConfig?.instructions || '').length}/8000
                            </div>
                            <button
                                onClick={() => updateGeminiConfig({
                                    instructions: 'You are a professional audiobook narrator with clear pronunciation and natural pacing.',
                                })}
                                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                            >
                                Narrator
                            </button>
                        </div>
                    </div>
                )}

                {voiceMode === 'gemini' && (
                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-2">
                            Reading Model
                        </label>
                        <div className="w-full bg-gray-800 border border-gray-600 text-gray-300 rounded-lg px-3 py-2 text-sm">
                            {geminiConfig?.model || 'gemini-2.0-flash-live-001'}
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                            Model currently used for text-to-speech in reading section
                        </p>
                    </div>
                )}

                {error && (
                    <div className="bg-red-900/50 border border-red-600/50 rounded-lg p-3 mb-4">
                        <div className="flex items-start space-x-2">
                            <svg
                                className="w-5 h-5 text-red-400 shrink-0 mt-0.5"
                                fill="currentColor"
                                viewBox="0 0 20 20"
                            >
                                <path
                                    fillRule="evenodd"
                                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                                    clipRule="evenodd"
                                />
                            </svg>
                            <p className="text-red-300 text-sm">{error}</p>
                        </div>
                    </div>
                )}
            </div>

            {!collapsed && (
                <div className="shrink-0 border-t border-gray-700/20 px-4 py-3 space-y-3">
                    <div className="bg-gray-800/50 rounded-lg p-3 min-h-[60px] flex items-center justify-center relative">
                        <p className="text-blue-300 italic text-center text-sm leading-relaxed">
                            {appState === AppState.PLAYING || appState === AppState.PAUSED
                                ? currentText(sentences, currentSentenceIndex)
                                : 'Press play to start listening.'}
                        </p>
                    </div>
                    {playerControls}
                </div>
            )}
        </div>
    );
};

const currentText = (
    sentences: string[],
    currentSentenceIndex: number,
): string => (
    currentSentenceIndex >= 0 && currentSentenceIndex < sentences.length
        ? sentences[currentSentenceIndex]
        : 'Press play to start listening.'
);

export default VoiceControlsPanel;
