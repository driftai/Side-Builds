import React, { useCallback, useEffect, useState } from 'react';
import AudioCacheManager from './AudioCacheManager';
import GeminiAudiobookApiConfig from './GeminiConfig';
import PlaybackOverlays from './PlaybackOverlays';
import ReadingInterface from './ReadingInterface';
import VoiceControlsPanel from './VoiceControlsPanel';
import { useAudioEngine } from '../hooks/useAudioEngine';
import { useDetachedControls } from '../hooks/useDetachedControls';
import { useDocumentSession } from '../hooks/useDocumentSession';
import { useElectronAudioBridge } from '../hooks/useElectronAudioBridge';
import { useGemini } from '../hooks/useGemini';
import { isElectronRuntime } from '../integrations/electronBridge';
import type { GeminiApiConfig } from '../types/gemini';
import { AppState } from '../types/playback';

const UploadIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg
        className={className}
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={1.5}
        stroke="currentColor"
    >
        <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16.5V9.75m0 0l-3.75 3.75M12 9.75l3.75 3.75M3 17.25V21h18v-3.75M4.5 12.75l7.5-7.5 7.5 7.5"
        />
    </svg>
);

const CloseIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg
        className={className}
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={1.5}
        stroke="currentColor"
    >
        <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M6 18L18 6M6 6l12 12"
        />
    </svg>
);

const LoadingSpinner: React.FC = () => (
    <div className="border-gray-300 h-20 w-20 animate-spin rounded-full border-8 border-t-blue-600" />
);

const AudiobookApp: React.FC = () => {
    const [fileName, setFileName] = useState('');
    const [documentId, setDocumentId] = useState<string | null>(null);
    const [geminiConfig, setGeminiConfig] = useState<GeminiApiConfig | null>(null);
    const [voiceControlsCollapsed, setVoiceControlsCollapsed] = useState(false);

    const {
        wsState,
        generateAudioForSentence,
        disconnect,
        allowConnections,
        connectionsBlocked,
        resetContinuity,
    } = useGemini(geminiConfig);

    // A new document begins a new narration continuity chain.
    useEffect(() => {
        resetContinuity();
    }, [documentId, resetContinuity]);

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
        handleJumpToSentence: seekToSentence,
        error,
        setError,
        voiceMode,
        setVoiceMode,
        selectedVoiceURI,
        setSelectedVoiceURI,
        selectedGeminiVoice,
        setSelectedGeminiVoice,
        voices,
        spokenCharIndex,
        applySentenceUpdate,
    } = useAudioEngine(
        geminiConfig,
        generateAudioForSentence,
        documentId,
        fileName,
    );

    const {
        liveWatching,
        lastEdit,
        sessionStartTime,
        fileInputRef,
        closeDocument,
        uploadDocument,
        handleFileChange,
    } = useDocumentSession({
        currentSentenceIndex,
        setCurrentSentenceIndex,
        sentencesRef,
        setFileName,
        setDocumentId,
        setAppState,
        setError,
        handleStop,
        applySentenceUpdate,
    });

    useEffect(() => {
        if (geminiConfig?.voice && geminiConfig.voice !== selectedGeminiVoice) {
            setSelectedGeminiVoice(geminiConfig.voice);
        }
    }, [
        geminiConfig?.voice,
        selectedGeminiVoice,
        setSelectedGeminiVoice,
    ]);

    useElectronAudioBridge({
        appState,
        currentSentenceIndex,
        sentencesRef,
        onPlay: handlePlay,
        onPause: handlePause,
        onStop: handleStop,
        onSkipForward: handleSkipForward,
        onSkipBackward: handleSkipBackward,
    });

    const {
        pipWindow,
        pipCompact,
        floatingControls,
        floatingAt,
        setFloatingAt,
        closeFloatingControls,
        toggleDetachedControls,
        togglePipCompact,
    } = useDetachedControls(fileName, currentSentenceIndex);

    const handleJumpToSentence = useCallback((index: number) => {
        if (!seekToSentence(index)) return;
        requestAnimationFrame(() => {
            document.getElementById(`sentence-${index}`)
                ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
    }, [seekToSentence]);

    const handleGeminiConfigChange = useCallback((config: GeminiApiConfig) => {
        setGeminiConfig(config);
        setSelectedGeminiVoice(config.voice);
        try {
            localStorage.setItem('geminiAudiobookConfig', JSON.stringify(config));
        } catch (cause) {
            console.error('Failed to save configuration to localStorage:', cause);
        }
    }, [setSelectedGeminiVoice]);

    const sentences = sentencesRef.current;

    const renderContent = () => {
        switch (appState) {
            case AppState.PROCESSING:
                return (
                    <div className="text-center">
                        <LoadingSpinner />
                        <p className="mt-4 text-lg text-gray-300 animate-pulse">
                            Extracting text from "{fileName}"...
                        </p>
                    </div>
                );

            case AppState.READY:
            case AppState.PLAYING:
            case AppState.PAUSED:
                return (
                    <div className="w-full h-full flex flex-col max-h-full min-h-0">
                        <div className="flex items-center justify-between mb-3 shrink-0">
                            <h2
                                className="text-lg font-semibold text-white truncate grow mr-3"
                                title={fileName}
                            >
                                {fileName}
                            </h2>
                            <button
                                onClick={closeDocument}
                                className="shrink-0 p-1.5 rounded-full animated-close-button text-white hover:text-white focus:outline-hidden focus:ring-2 focus:ring-red-400/75"
                                aria-label="Close PDF and select another"
                                title="Close current PDF"
                            >
                                <CloseIcon className="h-4 w-4" />
                            </button>
                        </div>

                        <ReadingInterface
                            sentences={sentences}
                            currentSentenceIndex={currentSentenceIndex}
                            appState={appState}
                            onSentenceClick={index => {
                                seekToSentence(index, 'play');
                            }}
                            sessionStartTime={sessionStartTime}
                            spokenCharIndex={spokenCharIndex}
                        />

                        <VoiceControlsPanel
                            collapsed={voiceControlsCollapsed}
                            onCollapsedChange={setVoiceControlsCollapsed}
                            appState={appState}
                            currentSentenceIndex={currentSentenceIndex}
                            sentences={sentences}
                            voiceMode={voiceMode}
                            onVoiceModeChange={setVoiceMode}
                            selectedVoiceURI={selectedVoiceURI}
                            onBrowserVoiceChange={setSelectedVoiceURI}
                            selectedGeminiVoice={selectedGeminiVoice}
                            voices={voices}
                            geminiConfig={geminiConfig}
                            onGeminiConfigChange={handleGeminiConfigChange}
                            connectionState={wsState}
                            error={error}
                            detachedActive={Boolean(pipWindow || floatingControls)}
                            isElectron={isElectronRuntime}
                            onToggleDetached={() => {
                                void toggleDetachedControls();
                            }}
                            onPlay={handlePlay}
                            onPause={handlePause}
                            onStop={handleStop}
                            onSkipForward={handleSkipForward}
                            onSkipBackward={handleSkipBackward}
                        />
                    </div>
                );

            case AppState.ERROR:
                return (
                    <div className="text-center text-red-400">
                        <p className="text-xl mb-4">{error}</p>
                        <button
                            onClick={() => { void uploadDocument(); }}
                            className="bg-red-500 text-white font-bold py-2 px-4 rounded-sm hover:bg-red-600 transition-colors"
                        >
                            Try Again
                        </button>
                    </div>
                );

            case AppState.IDLE:
            default:
                return (
                    <div className="text-center w-full max-w-lg mx-auto">
                        <button
                            onClick={() => { void uploadDocument(); }}
                            className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-gray-500 rounded-lg cursor-pointer hover:bg-gray-800/50 transition-colors"
                        >
                            <UploadIcon className="w-12 h-12 text-gray-400 mb-3" />
                            <p className="text-lg font-semibold text-gray-300">
                                Click to upload a document
                            </p>
                            <p className="text-gray-400 text-sm">
                                Supports PDF, TXT, and DOCX files
                            </p>
                        </button>
                    </div>
                );
        }
    };

    const documentOpen = appState !== AppState.IDLE && sentences.length > 0;

    return (
        <main className="animated-gradient min-h-screen w-full flex justify-center p-2 sm:p-4 overflow-y-auto">
            <div className={`w-full max-w-6xl my-auto ${documentOpen
                ? 'h-[calc(100dvh-1rem)] sm:h-[calc(100dvh-2rem)]'
                : 'max-h-[calc(100dvh-1rem)] sm:max-h-[calc(100dvh-2rem)]'
            } bg-black/30 backdrop-blur-xl rounded-xl sm:rounded-2xl shadow-2xl shadow-indigo-500/10 border border-white/10 text-white p-3 sm:p-6 flex flex-col`}
            >
                <header className={`shrink-0 text-center mb-3 sm:mb-4 overflow-y-auto ${!documentOpen
                    ? 'max-h-[45dvh]'
                    : voiceControlsCollapsed
                        ? 'max-h-[35dvh]'
                        : 'max-h-[26dvh]'}`}
                >
                    <h1 className="text-2xl font-bold tracking-tight bg-linear-to-r from-blue-400 to-purple-500 text-transparent bg-clip-text mb-2">
                        Document Audiobook Converter
                    </h1>
                    <p className="text-gray-400 text-sm mb-3">
                        Upload a PDF, TXT, or DOCX file and listen to it.
                        {liveWatching && (
                            <span className="ml-2 text-xs text-green-400 whitespace-nowrap">
                                ● watching file for edits
                            </span>
                        )}
                        {lastEdit && (
                            <span className="ml-2 text-xs text-blue-300 whitespace-nowrap">
                                · updated {lastEdit.changed} passage{lastEdit.changed === 1 ? '' : 's'} in place
                            </span>
                        )}
                    </p>

                    <div className="max-w-2xl mx-auto space-y-2">
                        <GeminiAudiobookApiConfig
                            onConfigChange={handleGeminiConfigChange}
                            initialConfig={geminiConfig || undefined}
                            onDisconnect={disconnect}
                            onAllowConnections={allowConnections}
                            connectionsBlocked={connectionsBlocked}
                            isConnected={
                                wsState === 'connected'
                                || wsState === 'connecting'
                            }
                        />
                        <AudioCacheManager
                            activeDocumentId={documentId}
                            activeSentences={sentences}
                            onJumpToSentence={handleJumpToSentence}
                        />
                    </div>
                </header>

                <div className="grow flex items-stretch justify-center min-h-0">
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

            <PlaybackOverlays
                appState={appState}
                currentSentenceIndex={currentSentenceIndex}
                sentences={sentences}
                fileName={fileName}
                documentOpen={documentOpen}
                pipWindow={pipWindow}
                pipCompact={pipCompact}
                onTogglePipCompact={togglePipCompact}
                floatingControls={floatingControls}
                floatingAt={floatingAt}
                onFloatingAtChange={setFloatingAt}
                onCloseFloating={closeFloatingControls}
                onPlay={handlePlay}
                onPause={handlePause}
                onStop={handleStop}
                onSkipForward={handleSkipForward}
                onSkipBackward={handleSkipBackward}
            />
        </main>
    );
};

export default AudiobookApp;
