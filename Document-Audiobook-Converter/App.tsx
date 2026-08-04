import React, { useState, useRef, useCallback, useEffect } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import GeminiAudiobookApiConfig, { type GeminiApiConfig } from './src/components/GeminiConfig';
import { useAudioEngine, AppState } from './src/hooks/useAudioEngine';
import { useGemini } from './src/hooks/useGemini';
import { splitIntoSentences, handleTxtFile, handleDocxFile } from './src/utils/textProcessing';
import PlayerControls from './src/components/PlayerControls';
import ReadingInterface from './src/components/ReadingInterface';

// Electron integration
declare global {
    interface Window {
        electronAPI?: {
            updateAudioState: (state: any) => void;
            onAudioCommand: (callback: (event: any, command: string) => void) => void;
            toggleControls: () => void;
            sendCommand?: (command: string) => void;
            hasMessagePort?: () => boolean;
            closeControls?: () => void;
            removeAllListeners: () => void;
            onIpcMessage?: (channel: string, callback: (event: any, ...args: any[]) => void) => void;
            removeIpcListeners?: (channel: string) => void;
        };
        electron?: {
            ipcRenderer: {
                on: (channel: string, callback: (event: any, ...args: any[]) => void) => void;
                removeAllListeners: (channel: string) => void;
            };
        };
        messagePort?: MessagePort;
    }
}

// Check for Electron API (either directly from Electron or via extension)
const getElectronAPI = () => {
    if (typeof window !== 'undefined' && window.electronAPI) {
        return window.electronAPI;
    }
    return null;
};

const isElectron = !!getElectronAPI();
const electronAPI = getElectronAPI();

// Direct WebSocket connection to Electron app (fallback)
let electronWebSocket: WebSocket | null = null;

// MessageChannel port for direct communication with Electron
let messageChannelPort: MessagePort | null = null;

const connectToElectronWebSocket = () => {
    if (electronWebSocket && electronWebSocket.readyState === WebSocket.OPEN) {
        return electronWebSocket;
    }

    // Try different ports in case the primary port is taken
    const ports = [3001, 3002, 3003, 3004, 3005, 3006];

    for (const port of ports) {
        try {
            const ws = new WebSocket(`ws://localhost:${port}`);
            ws.onopen = () => {
                console.log(`✅ Electron app connected on port ${port}`);
                electronWebSocket = ws; // Set global reference only on successful connection
            };
            ws.onmessage = (event) => {
                // Handle messages silently
            };
            ws.onclose = () => {
                console.log('❌ Electron app disconnected');
                if (electronWebSocket === ws) {
                    electronWebSocket = null;
                }
            };
            ws.onerror = (error) => {
                // Connection failed, try next port
            };
            return ws;
        } catch (error) {
            continue;
        }
    }

    console.log('❌ Could not connect to Electron app on any port');
    return null;
};

// Listen for MessageChannel port from main process
window.addEventListener('message', (event) => {
    if (event.data === 'init-port' && event.ports && event.ports[0]) {
        messageChannelPort = event.ports[0];
        messageChannelPort.start();
        console.log('React App: MessageChannel port received and started');
    }
});

// Utility function to send commands to Electron
const sendToElectron = (command: string) => {
    // Try direct WebSocket connection (working method)
    const ws = connectToElectronWebSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
        console.log('🎵 Toggling floating controls');
        ws.send(JSON.stringify({ action: 'toggleControls' }));
        return;
    }

    // Try extension API if WebSocket not available
    if (electronAPI) {
        try {
            console.log('🎵 Toggling floating controls (extension)');
            electronAPI.toggleControls();
            return;
        } catch (error) {
            // Connection not available
        }
    }

    // Try Chrome extension messaging
    if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
        try {
            console.log('🎵 Toggling floating controls (messaging)');
            chrome.runtime.sendMessage({
                action: 'electronCommand',
                method: 'toggleControls'
            });
            return;
        } catch (error) {
            // Connection not available
        }
    }

    // Fallback to global shortcut simulation
    console.log('🎵 Using global shortcut fallback');
    simulateKeyPress('B', true, true);
};

// Utility function to simulate keypress (fallback when other methods fail)
const simulateKeyPress = (key: string, ctrlKey: boolean = false, shiftKey: boolean = false) => {

    // Create keyboard events with different approaches for Edge compatibility
    const createEvent = (type: 'keydown' | 'keyup') => {
        const event = new KeyboardEvent(type, {
            key: key,
            code: `Key${key.toUpperCase()}`,
            ctrlKey: ctrlKey,
            shiftKey: shiftKey,
            bubbles: true,
            cancelable: true,
            composed: true,
            // Add Edge-specific properties
            altKey: false,
            metaKey: false,
            repeat: false
        });

        // Add properties that Edge might need
        Object.defineProperty(event, 'which', { value: key.charCodeAt(0) });
        Object.defineProperty(event, 'keyCode', { value: key.charCodeAt(0) });

        return event;
    };

    // Dispatch on multiple targets for better compatibility
    const targets = [document, window, document.body, document.activeElement];
    targets.forEach(target => {
        try {
            target.dispatchEvent(createEvent('keydown'));
            target.dispatchEvent(createEvent('keyup'));
        } catch (e) {
            // Ignore dispatch errors
        }
    });

    // Additional Edge-specific approach: try dispatching to document.body specifically
    try {
        const edgeEvent = new CustomEvent('keydown', {
            detail: { key: 'A', ctrlKey: true, shiftKey: true }
        });
        document.body.dispatchEvent(edgeEvent);
    } catch (e) {
        // Ignore
    }
};

// pdf.js used to arrive as a global from a <script> tag pointing at version
// 3.11.174 on cdnjs, with its worker fetched from the same host. That made PDF
// parsing depend on a network round-trip (so it failed offline and in packaged
// Electron builds), pinned nothing in package.json, and left the app on a 2023
// build of the parser. It is now a real dependency, bundled with its worker.
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

// --- SVG Icons (No changes needed here) ---
const UploadIcon: React.FC<{ className?: string }> = ({ className }) => (<svg className={className} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l-3.75 3.75M12 9.75l3.75 3.75M3 17.25V21h18v-3.75M4.5 12.75l7.5-7.5 7.5 7.5" /></svg>);
const CloseIcon: React.FC<{ className?: string }> = ({ className }) => (<svg className={className} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>);
const LoadingSpinner: React.FC = () => (<div className="border-gray-300 h-20 w-20 animate-spin rounded-full border-8 border-t-blue-600" />);

const GEMINI_VOICES = [
    'Zephyr', 'Puck', 'Charon', 'Kore', 'Fenrir', 'Leda', 'Orus', 'Aoede',
    'Callirrhoe', 'Autonoe', 'Enceladus', 'Iapetus', 'Umbriel', 'Algieba',
    'Despina', 'Erinome', 'Algenib', 'Rasalgethi', 'Laomedeia', 'Achernar',
    'Alnilam', 'Schedar', 'Gacrux', 'Pulcherrima', 'Achird', 'Zubenelgenubi',
    'Vindemiatrix', 'Sadachbia', 'Sadaltager', 'Sulafat'
];

const App: React.FC = () => {
    const [fileName, setFileName] = useState<string>('');
    const [geminiConfig, setGeminiConfig] = useState<GeminiApiConfig | null>(null);
    const [sessionStartTime, setSessionStartTime] = useState<number | null>(null);
    const [voiceControlsCollapsed, setVoiceControlsCollapsed] = useState<boolean>(false);
    const fileInputRef = useRef<HTMLInputElement | null>(null);

    const { wsState, generateAudioForSentence } = useGemini(geminiConfig);

    const {
        appState,
        setAppState,
        currentSentenceIndex,
        setCurrentSentenceIndex,
        sentencesRef,
        handlePlay,
        handlePause,
        handleStop,
        handleSkipForward,
        handleSkipBackward,
        error,
        setError,
        smoothPlayback,
        setSmoothPlayback,
        voiceMode,
        setVoiceMode,
        selectedVoiceURI,
        setSelectedVoiceURI,
        selectedGeminiVoice,
        setSelectedGeminiVoice,
        voices
    } = useAudioEngine(geminiConfig, generateAudioForSentence);

    // Sync selectedGeminiVoice with geminiConfig.voice when config changes
    useEffect(() => {
        if (geminiConfig?.voice && geminiConfig.voice !== selectedGeminiVoice) {
            setSelectedGeminiVoice(geminiConfig.voice);
        }
    }, [geminiConfig?.voice, selectedGeminiVoice, setSelectedGeminiVoice]);

    // Electron integration - sync audio state
    useEffect(() => {
        if (isElectron && electronAPI) {
            const currentSentence = sentencesRef.current[currentSentenceIndex];
            const audioState = {
                isPlaying: appState === AppState.PLAYING,
                currentIndex: currentSentenceIndex,
                totalSentences: sentencesRef.current.length,
                currentSentence: currentSentence ? currentSentence.substring(0, 60) + (currentSentence.length > 60 ? '...' : '') : ''
            };

            electronAPI.updateAudioState(audioState);
        }
    }, [appState, currentSentenceIndex, isElectron, sentencesRef]);

    // Electron integration - listen for commands from floating controls
    useEffect(() => {
        if (isElectron) {
            const handleAudioCommand = (event: any, command: string) => {
                console.log('React App: Received audio command:', command);
                switch (command) {
                    case 'play':
                        console.log('React App: Executing play command');
                        handlePlay();
                        break;
                    case 'pause':
                        console.log('React App: Executing pause command');
                        handlePause();
                        break;
                    case 'skipBackward':
                        console.log('React App: Executing skipBackward command');
                        handleSkipBackward();
                        break;
                    case 'skipForward':
                        console.log('React App: Executing skipForward command');
                        handleSkipForward();
                        break;
                    default:
                        console.log('React App: Unknown command:', command);
                }
            };

            // Listen for commands via electronAPI (extension method)
            if (electronAPI) {
                electronAPI.onAudioCommand(handleAudioCommand);
            }

            // Also listen for direct IPC commands from main process (MessageChannel path)
            const handleIpcMessage = (event: any, command: string) => {
                console.log('React App: Received IPC command:', command);
                handleAudioCommand(null, command);
            };

            // Set up IPC listener using electronAPI
            if (electronAPI && electronAPI.onIpcMessage) {
                electronAPI.onIpcMessage('execute-audio-command', handleIpcMessage);
            }

            return () => {
                if (electronAPI) {
                    electronAPI.removeAllListeners();
                    if (electronAPI.removeIpcListeners) {
                        electronAPI.removeIpcListeners('execute-audio-command');
                    }
                }
            };
        }
    }, [isElectron, handlePlay, handlePause, handleSkipBackward, handleSkipForward]);

    const handleClosePdf = useCallback(() => {
        handleStop();
        setAppState(AppState.IDLE);
        setFileName('');
        setError(null);
        setCurrentSentenceIndex(-1);
        sentencesRef.current = [];
        setSessionStartTime(null); // Reset focus time tracking
        // Clear the file input
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    }, [handleStop, setAppState, setError, setCurrentSentenceIndex, sentencesRef]);

    const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        const fileExtension = file.name.split('.').pop()?.toLowerCase();
        const supportedTypes = ['pdf', 'txt', 'docx'];

        if (!fileExtension || !supportedTypes.includes(fileExtension)) {
            setError(`Please select a valid file. Supported formats: ${supportedTypes.join(', ')}`);
            setAppState(AppState.IDLE);
            return;
        }

        handleStop();
        setFileName(file.name);
        setAppState(AppState.PROCESSING);

        try {
            let fullText = '';

            if (fileExtension === 'pdf') {
                const arrayBuffer = await file.arrayBuffer();
                const loadingTask = pdfjsLib.getDocument({ data: new Uint8Array(arrayBuffer) });
                const pdf = await loadingTask.promise;
                try {
                    for (let i = 1; i <= pdf.numPages; i++) {
                        const page = await pdf.getPage(i);
                        const content = await page.getTextContent();
                        // Join on spaces but honour the parser's end-of-line markers.
                        // Flattening every item with a space (the previous behaviour)
                        // welded headings onto the following paragraph, which is what
                        // produced single "sentences" hundreds of characters long.
                        let pageText = '';
                        for (const item of content.items as any[]) {
                            if (typeof item.str !== 'string') continue;
                            pageText += item.str;
                            pageText += item.hasEOL ? '\n' : ' ';
                        }
                        fullText += pageText + '\n';
                        page.cleanup();
                    }
                } finally {
                    // Releases the pdf.js worker; without this each opened
                    // document leaks one until the tab is reloaded.
                    await loadingTask.destroy();
                }
            } else if (fileExtension === 'txt') {
                fullText = await handleTxtFile(file);
            } else if (fileExtension === 'docx') {
                fullText = await handleDocxFile(file);
            }

            // Use improved sentence splitting instead of simple regex
            sentencesRef.current = splitIntoSentences(fullText);
            setSessionStartTime(Date.now()); // Start focus time tracking
            setAppState(AppState.READY);
        } catch (err) {
            console.error(`Error processing ${fileExtension.toUpperCase()} file:`, err);
            setError(`Failed to process the ${fileExtension.toUpperCase()} file. It might be corrupted or in an unsupported format.`);
            setAppState(AppState.ERROR);
        }
    };

    const handleUploadClick = useCallback(() => fileInputRef.current?.click(), []);
    const handleVoiceModeToggle = useCallback(() => setVoiceMode(prev => prev === 'browser' ? 'gemini' : 'browser'), [setVoiceMode]);
    const handleSmoothPlaybackToggle = useCallback(() => {
        setSmoothPlayback(!smoothPlayback);
    }, [smoothPlayback, setSmoothPlayback]);

    const handleVoiceChange = useCallback((event: React.ChangeEvent<HTMLSelectElement>) => {
        if (voiceMode === 'browser') {
            setSelectedVoiceURI(event.target.value);
            try { localStorage.setItem('selectedVoiceURI', event.target.value); }
            catch (error) { console.error('Failed to save voice selection to localStorage:', error); }
        }
        else {
            const newVoice = event.target.value;
            setSelectedGeminiVoice(newVoice);
            // Also update the gemini config voice
            if (geminiConfig) {
                const updatedConfig = { ...geminiConfig, voice: newVoice };
                setGeminiConfig(updatedConfig);
                try { localStorage.setItem('geminiAudiobookConfig', JSON.stringify(updatedConfig)); }
                catch (error) { console.error('Failed to save voice change to localStorage:', error); }
            }
        }
    }, [voiceMode, geminiConfig, setSelectedVoiceURI, setSelectedGeminiVoice]);

    const handleGeminiConfigChange = useCallback((config: GeminiApiConfig) => {
        setGeminiConfig(config);
        // Sync the selectedGeminiVoice with the config voice
        setSelectedGeminiVoice(config.voice);
        try { localStorage.setItem('geminiAudiobookConfig', JSON.stringify(config)); }
        catch (error) { console.error('Failed to save configuration to localStorage:', error); }
    }, [setSelectedGeminiVoice]);

    const renderContent = () => {
        switch (appState) {
            case AppState.PROCESSING:
                return (
                    <div className="text-center">
                        <LoadingSpinner />
                        <p className="mt-4 text-lg text-gray-300 animate-pulse">Extracting text from "{fileName}"...</p>
                    </div>
                );
            case AppState.READY:
            case AppState.PLAYING:
            case AppState.PAUSED:
                return (
                    <div className="w-full h-full flex flex-col max-h-full">
                        <div className="flex items-center justify-between mb-3 shrink-0">
                            <h2 className="text-lg font-semibold text-white truncate grow mr-3" title={fileName}>{fileName}</h2>
                            <button
                                onClick={handleClosePdf}
                                className="shrink-0 p-1.5 rounded-full animated-close-button text-white hover:text-white focus:outline-hidden focus:ring-2 focus:ring-red-400/75"
                                aria-label="Close PDF and select another"
                                title="Close current PDF"
                            >
                                <CloseIcon className="h-4 w-4" />
                            </button>
                        </div>

                        {/* Minimalist Reading Experience */}
                        <ReadingInterface
                            sentences={sentencesRef.current}
                            currentSentenceIndex={currentSentenceIndex}
                            appState={appState}
                            onSentenceClick={(index) => {
                                handleStop();
                                setCurrentSentenceIndex(index);
                                setAppState(AppState.PLAYING);
                            }}
                            voiceControlsCollapsed={voiceControlsCollapsed}
                            sessionStartTime={sessionStartTime}
                        />

                        {/* Voice Controls Section */}
                        <div className={`flex-none ${voiceControlsCollapsed ? 'min-h-[3vh] max-h-[3vh]' : 'h-[48vh]'} bg-gray-900/60 rounded-lg border border-gray-700/30 overflow-hidden relative transition-all duration-300 ease-in-out`}>
                            {/* Voice Controls Header - Clickable */}
                            <div
                                className={`bg-gray-800/40 px-6 py-2 border-b border-gray-700/20 cursor-pointer hover:bg-gray-700/40 transition-colors duration-200`}
                                onClick={() => setVoiceControlsCollapsed(!voiceControlsCollapsed)}
                            >
                                <div className="flex items-center justify-between">
                                    <div className="text-sm text-gray-400 font-serif flex items-center gap-2">
                                        🎛️ Voice Controls
                                        <span className={`text-xs transition-transform duration-200 ${voiceControlsCollapsed ? 'rotate-90' : ''}`}>
                                            {voiceControlsCollapsed ? '▶' : '▼'}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-end gap-3">
                                        {voiceControlsCollapsed && (
                                            <div className="flex items-center justify-center gap-1 self-center mt-[-3px]" onClick={(e) => e.stopPropagation()}>
                                                <PlayerControls
                                                    appState={appState}
                                                    currentSentenceIndex={currentSentenceIndex}
                                                    totalSentences={sentencesRef.current.length}
                                                    onPlay={handlePlay}
                                                    onPause={handlePause}
                                                    onStop={handleStop}
                                                    onSkipForward={handleSkipForward}
                                                    onSkipBackward={handleSkipBackward}
                                                />
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        // Try multiple methods to communicate with Electron
                                                        sendToElectron('toggleControls');
                                                    }}
                                                    className="p-1.5 rounded-md bg-blue-700/50 text-blue-300 hover:bg-blue-600/50 hover:text-white transition-colors duration-200"
                                                    aria-label="Electron floating controls"
                                                    title="Electron floating controls (always on top)"
                                                >
                                                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                                    </svg>
                                                </button>
                                            </div>
                                        )}
                                        <div className="text-xs text-gray-500">
                                            {voiceControlsCollapsed ? 'Click to expand' : 'Audio Engine & Playback'}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Scrollable Voice Controls - Always present but hidden when collapsed */}
                            <div className={`p-4 overflow-y-auto space-y-4 transition-all duration-300 ease-in-out ${voiceControlsCollapsed
                                    ? 'max-h-0 opacity-0 invisible'
                                    : 'h-[28vh] opacity-100 visible'
                                }`}>
                                {/* Voice Mode Toggle */}
                                <div className="flex items-center justify-between">
                                    <label className="block text-sm font-medium text-gray-400">
                                        Voice Engine
                                    </label>
                                    <button
                                        onClick={handleVoiceModeToggle}
                                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900 ${voiceMode === 'gemini' ? 'bg-blue-600' : 'bg-gray-600'
                                            }`}
                                        /* Previously disabled when no client-side apiKey was set, which
                                           both blocked Gemini mode unnecessarily (the server supplies the
                                           key) and trapped you in it with no way to toggle back. */
                                    >
                                        <span
                                            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${voiceMode === 'gemini' ? 'translate-x-6' : 'translate-x-1'
                                                }`}
                                        />
                                    </button>
                                </div>

                                {/* Voice Mode Labels */}
                                <div className="flex justify-between text-xs text-gray-400">
                                    <span className={voiceMode === 'browser' ? 'text-blue-400 font-medium' : ''}>
                                        Browser TTS
                                    </span>
                                    <span className={voiceMode === 'gemini' ? 'text-blue-400 font-medium' : ''}>
                                        Gemini Live API
                                        {voiceMode === 'gemini' && (
                                            <span className="ml-1">
                                                {wsState === 'connected' && '🟢'}
                                                {wsState === 'connecting' && '🟡'}
                                                {wsState === 'error' && '🔴'}
                                                {wsState === 'disconnected' && '⚪'}
                                            </span>
                                        )}
                                        {(!geminiConfig || !geminiConfig.apiKey) && ' (Configure API)'}
                                    </span>
                                </div>

                                {/* Voice Selection */}
                                <div>
                                    <label htmlFor="voice-select" className="block text-sm font-medium text-gray-400 mb-2">
                                        Voice {voiceMode === 'gemini' && (!geminiConfig || !geminiConfig.apiKey) && '(API Key Required)'}
                                    </label>
                                    <select
                                        id="voice-select"
                                        value={voiceMode === 'browser' ? (selectedVoiceURI || '') : selectedGeminiVoice}
                                        onChange={handleVoiceChange}
                                        /* Gemini voices no longer require a client-side key - the server
                                           supplies one - so only gate on the config having loaded. */
                                        disabled={voiceMode === 'browser' ? voices.length === 0 : !geminiConfig}
                                        className="w-full bg-gray-800 border border-gray-600 text-white text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2.5"
                                        aria-label="Select a voice for text-to-speech"
                                    >
                                        {voiceMode === 'browser' ? (
                                            voices.length === 0 ? (
                                                <option>Loading voices...</option>
                                            ) : (
                                                voices.map((voice) => (
                                                    <option key={voice.voiceURI} value={voice.voiceURI}>
                                                        {`${voice.name} (${voice.lang})`}
                                                    </option>
                                                ))
                                            )
                                        ) : (
                                            !geminiConfig ? (
                                                <option>Loading voices...</option>
                                            ) : (
                                                GEMINI_VOICES.map((voice) => (
                                                    <option key={voice} value={voice}>
                                                        {voice}
                                                    </option>
                                                ))
                                            )
                                        )}
                                    </select>
                                </div>

                                {/* Instructions Input - Only show for Gemini mode */}
                                {voiceMode === 'gemini' && (
                                    <div className="mt-3">
                                        <div className="flex items-center justify-between mb-2">
                                            <label className="block text-sm font-medium text-gray-400">
                                                Instructions (optional)
                                            </label>
                                            {geminiConfig?.instructions && (
                                                <button
                                                    onClick={() => {
                                                        if (geminiConfig) {
                                                            const newConfig = { ...geminiConfig, instructions: '' };
                                                            setGeminiConfig(newConfig);
                                                            try { localStorage.setItem('geminiAudiobookConfig', JSON.stringify(newConfig)); }
                                                            catch (error) { console.error('Failed to clear instructions in localStorage:', error); }
                                                        }
                                                    }}
                                                    className="text-xs text-gray-400 hover:text-white transition-colors"
                                                >
                                                    Clear
                                                </button>
                                            )}
                                        </div>
                                        <textarea
                                            value={geminiConfig?.instructions || ''}
                                            onChange={(e) => {
                                                if (geminiConfig) {
                                                    const newValue = e.target.value;
                                                    if (newValue.length <= 8000) {
                                                        const newConfig = { ...geminiConfig, instructions: newValue };
                                                        setGeminiConfig(newConfig);
                                                        try { localStorage.setItem('geminiAudiobookConfig', JSON.stringify(newConfig)); }
                                                        catch (error) { console.error('Failed to save instructions to localStorage:', error); }
                                                    }
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
                                                onClick={() => {
                                                    if (geminiConfig) {
                                                        const newConfig = { ...geminiConfig, instructions: "You are a professional audiobook narrator with clear pronunciation and natural pacing." };
                                                        setGeminiConfig(newConfig);
                                                        try { localStorage.setItem('geminiAudiobookConfig', JSON.stringify(newConfig)); }
                                                        catch (error) { console.error('Failed to save preset to localStorage:', error); }
                                                    }
                                                }}
                                                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                                            >
                                                Narrator
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {/* Reading Model Display - Only show for Gemini mode */}
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

                                {/* Error Display */}
                                {error && (
                                    <div className="bg-red-900/50 border border-red-600/50 rounded-lg p-3 mb-4">
                                        <div className="flex items-start space-x-2">
                                            <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                                            </svg>
                                            <p className="text-red-300 text-sm">{error}</p>
                                        </div>
                                    </div>
                                )}

                                {/* Current Sentence Display */}
                                <div className="bg-gray-800/50 rounded-lg p-3 min-h-[60px] flex items-center justify-center relative">
                                    <p className="text-blue-300 italic text-center text-sm leading-relaxed">
                                        {appState === AppState.PLAYING || appState === AppState.PAUSED
                                            ? (currentSentenceIndex >= 0 && currentSentenceIndex < sentencesRef.current.length
                                                ? sentencesRef.current[currentSentenceIndex]
                                                : 'Press play to start listening.')
                                            : 'Press play to start listening.'}
                                    </p>
                                </div>

                                {/* Playback Controls */}
                                <PlayerControls
                                    appState={appState}
                                    currentSentenceIndex={currentSentenceIndex}
                                    totalSentences={sentencesRef.current.length}
                                    onPlay={handlePlay}
                                    onPause={handlePause}
                                    onStop={handleStop}
                                    onSkipForward={handleSkipForward}
                                    onSkipBackward={handleSkipBackward}
                                />
                            </div>
                        </div>
                    </div>
                );
            case AppState.ERROR:
                return (
                    <div className="text-center text-red-400">
                        <p className="text-xl mb-4">{error}</p>
                        <button onClick={handleUploadClick} className="bg-red-500 text-white font-bold py-2 px-4 rounded-sm hover:bg-red-600 transition-colors">
                            Try Again
                        </button>
                    </div>
                );
            case AppState.IDLE:
            default:
                return (
                    <div className="text-center w-full max-w-lg mx-auto">
                        <button onClick={handleUploadClick} className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-gray-500 rounded-lg cursor-pointer hover:bg-gray-800/50 transition-colors">
                            <UploadIcon className="w-12 h-12 text-gray-400 mb-3" />
                            <p className="text-lg font-semibold text-gray-300">Click to upload a document</p>
                            <p className="text-gray-400 text-sm">Supports PDF, TXT, and DOCX files</p>
                        </button>
                    </div>
                );
        }
    };

    return (
        <main className="animated-gradient min-h-screen w-full flex items-center justify-center p-2 sm:p-4">
            <div className="w-full max-w-6xl h-[95vh] sm:h-[90vh] min-h-[600px] sm:min-h-[700px] bg-black/30 backdrop-blur-xl rounded-xl sm:rounded-2xl shadow-2xl shadow-indigo-500/10 border border-white/10 text-white p-4 sm:p-6 flex flex-col">
                <header className="shrink-0 text-center mb-4">
                    <h1 className="text-2xl font-bold tracking-tight bg-linear-to-r from-blue-400 to-purple-500 text-transparent bg-clip-text mb-2">
                        Document Audiobook Converter
                    </h1>
                    <p className="text-gray-400 text-sm mb-3">Upload a PDF, TXT, or DOCX file and listen to it.</p>

                    {/* Gemini API Configuration */}
                    <div className="max-w-2xl mx-auto">
                        <GeminiAudiobookApiConfig
                            onConfigChange={handleGeminiConfigChange}
                            initialConfig={geminiConfig || undefined}
                        />
                    </div>
                </header>
                <div className="grow flex items-center justify-center min-h-0 overflow-hidden">
                    {renderContent()}
                </div>
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    className="hidden"
                    accept=".pdf,.txt,.docx"
                />
            </div>
        </main>
    );
};

export default App;
