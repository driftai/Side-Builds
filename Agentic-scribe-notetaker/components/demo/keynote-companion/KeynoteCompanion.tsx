/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/
import React, { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { GoogleGenAI } from '@google/genai';
import { useLiveAPIContext } from '../../../contexts/LiveAPIContext';
import { PLACEHOLDER_DOC } from '../../../lib/constants';
import {
  useAgent,
  useInsertStore,
  usePerfLogStore,
  useSourceStore,
  useUI,
  useUser,
  useVersionStore,
} from '../../../lib/state';
import { AudioLogEntry, TranscriptEntry, UnidexLogEntry } from './types';
import { useDocumentEnhancements } from './hooks/useDocumentEnhancements';
import { useDocumentLoadActions } from './hooks/useDocumentLoadActions';
import { useDownloadActions } from './hooks/useDownloadActions';
import { useElementResize } from './hooks/useElementResize';
import { useAudioLogActions } from './hooks/useAudioLogActions';
import { useLiveEventHandlers } from './hooks/useLiveEventHandlers';
import { useLiveConfigEffects } from './hooks/useLiveConfigEffects';
import { useScribeCommands } from './hooks/useScribeCommands';
import type { DocumentSelection, ScribeCommandId } from './hooks/useScribeCommands';
import { useTranscriptActions } from './hooks/useTranscriptActions';
import { useWelcomeShortcuts } from './hooks/useWelcomeShortcuts';
import { useWorkspaceRuntimeRestore } from './hooks/useWorkspaceRuntimeRestore';
import { KeynoteContentView } from './views/KeynoteContentView';
import { getAudioDuration } from './utils/audio';
export default function KeynoteCompanion() {
  const { client, setConfig, stopAudio, connected, connect, isConnecting, setMuted, audioStreamerRef } = useLiveAPIContext();
  const user = useUser();
  const { current } = useAgent();
  const {
    incrementChangeCount,
    setAgentState,
    suppressStaleAgentResponses,
    suppressPostFlushAudio,
    mainTab,
    setMainTab,
    documentTab,
    setDocumentTab,
    font,
    setFont,
    setSpeechBubbleText,
    documentContent,
    setDocumentContent,
    outputModality,
    useSearch,
    setUseSearch,
    liveApiModel, scribeMode, documentGoal, exportProfile, workspaceInstruction,
    setDocumentGoal, setExportProfile, setScribeMode, setWorkspaceInstruction,
    setShowUserConfig, setShowStorageModal,
    setPendingSourceFocus,
    setShowExportPackageModal,
  } = useUI();
  useEffect(() => {
    setMuted(outputModality === 'text');
  }, [outputModality, setMuted]);
  const { inserts, addInsert, updateInsert } = useInsertStore();
  const { sources, addSource, upsertSource } = useSourceStore();
  const { addVersion } = useVersionStore();
  const { addLog: addPerfLog, startNewSession } = usePerfLogStore();
  const [documentHistory, setDocumentHistory] = useState<string[]>([]), [redoHistory, setRedoHistory] = useState<string[]>([]);
  const [documentSelection, setDocumentSelection] = useState<DocumentSelection | null>(null), [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [unidexLog, setUnidexLog] = useState<UnidexLogEntry[]>([]), [audioLog, setAudioLog] = useState<AudioLogEntry[]>([]);
  const [correctedTranscript, setCorrectedTranscript] = useState('');
  const [accurateTranscript, setAccurateTranscript] = useState('');
  const [isCorrectingTranscript, setIsCorrectingTranscript] = useState(false), [isGeneratingAccurateTranscript, setIsGeneratingAccurateTranscript] = useState(false);
  const [copyButtonText, setCopyButtonText] = useState('Copy');
  const [pdfStatus, setPdfStatus] = useState<'idle' | 'preparing' | 'generating'>('idle');
  const [playingAudio, setPlayingAudio] = useState<{ index: number; element: HTMLAudioElement; url: string } | null>(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [showMobileToolbar, setShowMobileToolbar] = useState(false);
  const [downloadMenuOpen, setDownloadMenuOpen] = useState<'editor' | 'rendered' | null>(null);
  const renderedViewRef = useRef<HTMLDivElement>(null);
  const minutesViewRef = useRef<HTMLDivElement>(null);
  const transcriptRef = useRef(transcript);
  transcriptRef.current = transcript;
  const unidexLogRef = useRef(unidexLog); unidexLogRef.current = unidexLog;
  const unidexLogIdRef = useRef(0);
  const documentContentRef = useRef(documentContent);
  documentContentRef.current = documentContent;
  const currentUserText = useRef(''); const currentModelText = useRef('');
  const currentUserAudioChunks = useRef<ArrayBuffer[]>([]);
  const currentAgentAudioChunks = useRef<ArrayBuffer[]>([]);
  const docContentBeforeEditRef = useRef(documentContent);
  const promptVersionRef = useRef(0);
  const systemInstructionTextRef = useRef('');
  const lastTurnCompleteTimestampRef = useRef(0);
  const lastUserRequestRef = useRef('');
  const selfInterruptionDetectedRef = useRef(false);
  const lastSpeakerRef = useRef<'user' | 'agent' | null>(null);
  const hasSentGreetingRef = useRef(false);
  const typedUserCommittedRef = useRef(false);
  const turnCounterRef = useRef(0);
  const hasLoggedFirstUserTextThisTurnRef = useRef(false);
  const hasLoggedFirstAgentTextThisTurnRef = useRef(false);
  const hasLoggedFirstAgentAudioThisTurnRef = useRef(false);
  const currentAgentTurnStartTimeRef = useRef<Date | null>(null);
  const agentAudioPlaybackStartTimeRef = useRef<Date | null>(null);
  const agentAudioPlaybackEndTimeRef = useRef<Date | null>(null);
  const latestUserTurnIdRef = useRef(0);
  const currentUserTurnStartTimeRef = useRef<Date | null>(null);
  const processedAgentTurnIdRef = useRef(0);
  const isSuppressingAgentOutputRef = useRef(false);
  const hasFlushedThisTurnRef = useRef(false);
  const isStaleSuppressedThisTurnRef = useRef(false);
  const isPostFlushSuppressedThisTurnRef = useRef(false);
  const isAgentSpeakingRef = useRef(false);
  const hasSearchedThisTurnRef = useRef(false);
  const userRef = useRef(user);
  userRef.current = user;
  const agentRef = useRef(current);
  agentRef.current = current;
  const { apiKey: _runtimeApiKey, imageModel, imageGenerationEnabled } = useUI();
  const ai = useRef(_runtimeApiKey ? new GoogleGenAI({ apiKey: _runtimeApiKey }) : null);
  const activeSources = useMemo(() => sources.filter(source => source.active), [sources]);
  const addUnidexLog = useCallback((entry: Omit<UnidexLogEntry, 'id' | 'timestamp'>) => {
    setUnidexLog(prev => [
      ...prev,
      {
        ...entry,
        id: unidexLogIdRef.current++,
        timestamp: new Date(),
      },
    ]);
  }, []);
  useEffect(() => {
    if (_runtimeApiKey) {
      ai.current = new GoogleGenAI({ apiKey: _runtimeApiKey });
    }
  }, [_runtimeApiKey]);
  useEffect(() => {
    if (documentContent && documentContent !== PLACEHOLDER_DOC) {
      upsertSource('source_current_document', {
        kind: 'document',
        title: 'Current Working Document',
        content: documentContent,
        tags: ['live', 'document'],
        active: false,
      });
    }
  }, [documentContent, upsertSource]);
  useEffect(() => {
    if (transcript.length) {
      upsertSource('source_live_transcript', {
        kind: 'transcript',
        title: 'Live Transcript',
        content: transcript.map(entry => `${entry.speaker}: ${entry.text}`).join('\n'),
        tags: ['live', 'transcript'],
        active: false,
      });
    }
  }, [transcript, upsertSource]);
  useDocumentEnhancements({
    documentContent,
    setDocumentContent,
    inserts,
    addInsert,
    updateInsert,
    ai,
    imageModel,
    imageGenerationEnabled,
  });
  const pushToHistory = (content: string) => {
    setDocumentHistory(prev => [...prev, content]);
    setRedoHistory([]);
  };
  const { commandLabel, runCommand, runningCommand } = useScribeCommands({
    ai,
    documentContent,
    pushToHistory,
    setDocumentContent,
    activeSources,
    addSource,
    addVersion,
    addUnidexLog,
    topic: user.topic,
    userContext: user.info,
    documentGoal,
    exportProfile,
    workspaceInstruction,
  });
  const {
    handleStartConversation,
    handleEnableSearchShortcut,
    handlePdfContextShortcut,
    handleInsertGraphShortcut,
    handleInsertIllustrationShortcut,
    handleEditDocumentShortcut,
  } = useWelcomeShortcuts({
    addPerfLog,
    ai,
    client,
    connect,
    connected,
    documentContentRef,
    isConnecting,
    pushToHistory,
    setDocumentContent,
    setDocumentTab,
    setMainTab,
    setShowUserConfig,
    setSpeechBubbleText,
    addUnidexLog,
    setUseSearch,
    startNewSession,
    topic: user.topic,
    userContext: user.info,
  });
  const { handleElementResize, handleRenderedContentMouseDown } = useElementResize({
    addUnidexLog,
    renderedViewRef,
    setDocumentContent,
    pushToHistory,
  });
  useLiveConfigEffects({
    addPerfLog,
    addUnidexLog,
    activeSources,
    client,
    connected,
    current,
    documentContent,
    documentContentRef,
    documentGoal,
    docContentBeforeEditRef,
    exportProfile,
    hasSentGreetingRef,
    imageGenerationEnabled,
    isSuppressingAgentOutputRef,
    lastSpeakerRef,
    latestUserTurnIdRef,
    liveApiModel,
    processedAgentTurnIdRef,
    promptVersionRef,
    setAgentState,
    setConfig,
    scribeMode,
    systemInstructionTextRef,
    turnCounterRef,
    useSearch,
    user,
    workspaceInstruction,
  });
  const handleDocumentChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setDocumentContent(prevContent => {
      pushToHistory(prevContent);
      return e.target.value;
    });
  };
  const handleUndo = () => {
    if (documentHistory.length > 0) {
      const lastVersion = documentHistory[documentHistory.length - 1];
      setRedoHistory(prev => [documentContentRef.current, ...prev]);
      setDocumentHistory(prev => prev.slice(0, -1));
      setDocumentContent(lastVersion);
    }
  };
  const handleRedo = () => {
    if (redoHistory.length > 0) {
      const nextVersion = redoHistory[0];
      pushToHistory(documentContentRef.current);
      setRedoHistory(prev => prev.slice(1));
      setDocumentContent(nextVersion);
    }
  };
  const { clearWorkspaceRuntime, restoreWorkspaceRuntime } = useWorkspaceRuntimeRestore({
    documentContentRef, docContentBeforeEditRef, transcriptRef, unidexLogRef,
    setAccurateTranscript, setCorrectedTranscript, setDocumentContent,
    setDocumentHistory, setRedoHistory, setTranscript, setUnidexLog,
  });
  useLiveEventHandlers({
    addPerfLog,
    addUnidexLog,
    activeSources,
    agentAudioPlaybackEndTimeRef,
    agentAudioPlaybackStartTimeRef,
    agentRef,
    ai,
    audioStreamerRef,
    client,
    current,
    currentAgentAudioChunks,
    currentAgentTurnStartTimeRef,
    currentModelText,
    currentUserAudioChunks,
    currentUserText,
    currentUserTurnStartTimeRef,
    clearWorkspaceRuntime,
    docContentBeforeEditRef,
    documentContent,
    documentContentRef,
    documentGoal,
    exportProfile,
    hasFlushedThisTurnRef,
    hasLoggedFirstAgentAudioThisTurnRef,
    hasLoggedFirstAgentTextThisTurnRef,
    hasLoggedFirstUserTextThisTurnRef,
    hasSearchedThisTurnRef,
    incrementChangeCount,
    isAgentSpeakingRef,
    isPostFlushSuppressedThisTurnRef,
    isStaleSuppressedThisTurnRef,
    isSuppressingAgentOutputRef,
    lastSpeakerRef,
    lastTurnCompleteTimestampRef,
    lastUserRequestRef,
    latestUserTurnIdRef,
    outputModality, processedAgentTurnIdRef, promptVersionRef, pushToHistory,
    restoreWorkspaceRuntime, runWorkspaceCommand: runCommand,
    selfInterruptionDetectedRef, scribeMode, setAgentState, setAudioLog,
    setDocumentContent, setSpeechBubbleText, setDocumentGoal, setExportProfile,
    setScribeMode, setWorkspaceInstruction, setTranscript, stopAudio,
    suppressPostFlushAudio, suppressStaleAgentResponses, transcriptRef,
    typedUserCommittedRef, turnCounterRef, user, userRef,
  });
  const handleClear = () => {
    if (documentContentRef.current && documentContentRef.current !== PLACEHOLDER_DOC) {
      addVersion({
        title: 'Before clear',
        content: documentContentRef.current,
        reason: 'Automatic safety snapshot',
      });
    }
    setDocumentContent(PLACEHOLDER_DOC); setDocumentHistory([]); setRedoHistory([]);
    setTranscript([]); setUnidexLog([]); setCorrectedTranscript(''); setAccurateTranscript('');
  };
  const handleLoadVersion = (content: string) => {
    pushToHistory(documentContentRef.current);
    setDocumentContent(content);
    addUnidexLog({
      kind: 'document',
      source: 'Document Versions',
      title: 'Version loaded',
      detail: `Loaded ${content.length.toLocaleString()} characters into the working document.`,
    });
  };
  const { handleGetAccurateTranscript, handleReplaceTranscript } = useTranscriptActions({
    accurateTranscript,
    ai,
    audioLog,
    current,
    mainTab,
    setAccurateTranscript,
    setCorrectedTranscript,
    setIsCorrectingTranscript,
    setIsGeneratingAccurateTranscript,
    setTranscript,
    transcript,
    user,
  });
  const handleCopyToClipboard = (content: string) => {
    navigator.clipboard.writeText(content).then(() => {
      setCopyButtonText('Copied!');
      setTimeout(() => setCopyButtonText('Copy'), 2000);
    });
  };
  const { handleUploadDocument } = useDocumentLoadActions({
    addPerfLog,
    client,
    connected,
    docContentBeforeEditRef,
    documentContentRef,
    promptVersionRef,
    pushToHistory,
    setDocumentContent,
    addUnidexLog,
    turnCounterRef,
    user,
  });
  const { handleDownloadAs, handleDownloadPDF } = useDownloadActions({
    documentContent,
    inserts,
    setDownloadMenuOpen,
    setPdfStatus,
    topic: user.topic,
  });
  const { handleSaveAudioLog, toggleAudioPlayback } = useAudioLogActions({
    audioLog,
    playingAudio,
    setPlayingAudio,
  });
  return (
    <div className="keynote-companion">
      <KeynoteContentView
        mainTab={mainTab}
        documentTab={documentTab}
        documentViewProps={{
          isMobile, showMobileToolbar, setShowMobileToolbar,
          documentHistoryLength: documentHistory.length,
          redoHistoryLength: redoHistory.length,
          handleUndo, handleRedo, handleClear, handleStartConversation,
          handleEnableSearchShortcut, handlePdfContextShortcut,
          handleInsertGraphShortcut, handleInsertIllustrationShortcut,
          handleEditDocumentShortcut, handleUploadDocument,
          openStorage: () => setShowStorageModal(true),
          handleDownloadAs, documentContent, font, setFont,
          downloadMenuOpen, setDownloadMenuOpen, handleDocumentChange,
          renderedViewRef, pdfStatus, handleDownloadPDF, topic: user.topic,
          handleCopyToClipboard, handleRenderedContentMouseDown, inserts,
          imageGenerationEnabled, handleElementResize,
          selection: documentSelection,
          setSelection: setDocumentSelection,
          onRunCommandOnSelection: (command: ScribeCommandId) => {
            if (!documentSelection) return;
            void runCommand(command, '', documentSelection)
              .then(() => setDocumentSelection(null))
              .catch(err => console.error('Selection command failed:', err));
          },
          runningCommand,
          onCitationClick: (sourceId: string) => {
            setPendingSourceFocus(sourceId);
            setMainTab('workspace');
          },
          openExportPackage: () => setShowExportPackageModal(true),
        }}
        workspaceViewProps={{
          documentContent, transcript, onLoadVersion: handleLoadVersion,
          onRunCommand: runCommand, runningCommand, commandLabel,
        }}
        transcriptViewProps={{
          handleGetAccurateTranscript, isGeneratingAccurateTranscript,
          audioLogLength: audioLog.length, accurateTranscript,
          handleCopyToClipboard, handleReplaceTranscript,
          setAccurateTranscript, transcript,
        }}
        unidexLog={unidexLog}
        setUnidexLog={setUnidexLog}
        minutesViewProps={{
          minutesViewRef, handleDownloadPDF, topic: user.topic, pdfStatus,
          handleCopyToClipboard, correctedTranscript, isCorrectingTranscript,
        }}
        audioLogViewProps={{
          handleSaveAudioLog, audioLog, getAudioDuration, toggleAudioPlayback,
          playingAudioIndex: playingAudio?.index ?? null,
        }}
      />
    </div>
  );
}
