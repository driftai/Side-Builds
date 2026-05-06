/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import {
  FunctionDeclaration,
  LiveConnectConfig,
  Modality,
  Type,
} from '@google/genai';
import { diffChars } from 'diff';
import React, { useEffect } from 'react';
import { PLACEHOLDER_DOC } from '../../../../lib/constants';
import { createSystemInstructions } from '../../../../lib/prompts';
import { useLogStore } from '../../../../lib/state';
import type { ScribeExportProfile, ScribeMode, ScribeSource } from '../../../../lib/state';
import type { UnidexLogEntry } from '../types';

type UseLiveConfigEffectsArgs = {
  addPerfLog: (entry: any) => void;
  addUnidexLog: (entry: Omit<UnidexLogEntry, 'id' | 'timestamp'>) => void;
  activeSources: ScribeSource[];
  client: any;
  connected: boolean;
  current: any;
  documentContent: string;
  documentContentRef: React.MutableRefObject<string>;
  documentGoal: string;
  docContentBeforeEditRef: React.MutableRefObject<string>;
  exportProfile: ScribeExportProfile;
  isSuppressingAgentOutputRef: React.MutableRefObject<boolean>;
  hasSentGreetingRef: React.MutableRefObject<boolean>;
  imageGenerationEnabled: boolean;
  lastSpeakerRef: React.MutableRefObject<'user' | 'agent' | null>;
  latestUserTurnIdRef: React.MutableRefObject<number>;
  liveApiModel: string;
  processedAgentTurnIdRef: React.MutableRefObject<number>;
  promptVersionRef: React.MutableRefObject<number>;
  setAgentState: (state: string | null) => void;
  setConfig: (config: LiveConnectConfig) => void;
  scribeMode: ScribeMode;
  systemInstructionTextRef: React.MutableRefObject<string>;
  turnCounterRef: React.MutableRefObject<number>;
  useSearch: boolean;
  user: any;
  workspaceInstruction: string;
};

export function useLiveConfigEffects({
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
}: UseLiveConfigEffectsArgs) {
  useEffect(() => {
    if (!connected) {
      lastSpeakerRef.current = null;
      latestUserTurnIdRef.current = 0;
      processedAgentTurnIdRef.current = 0;
      isSuppressingAgentOutputRef.current = false;
      setAgentState(null);
    } else {
      setAgentState('Waiting');
    }
  }, [
    connected,
    isSuppressingAgentOutputRef,
    lastSpeakerRef,
    latestUserTurnIdRef,
    processedAgentTurnIdRef,
    setAgentState,
  ]);

  useEffect(() => {
    if (connected && !hasSentGreetingRef.current) {
      const isWarmStart = documentContentRef.current !== PLACEHOLDER_DOC;
      const message = isWarmStart
        ? `(System message: The session has been resumed. You already have the current document in your context. Please welcome the user back and ask how to continue.)`
        : `(System message: The conversation has just begun. Please greet the user now based on your instructions.)`;

      setAgentState('Thinking');
      client.send([{ text: message }]);

      useLogStore.getState().addLog({
        api: 'System Message',
        inputSize: message.length,
        outputSize: 'N/A',
        status: 'success',
        prompt: message,
        promptVersion: promptVersionRef.current,
        turn: turnCounterRef.current,
      });

      hasSentGreetingRef.current = true;
    } else if (!connected) {
      hasSentGreetingRef.current = false;
    }
  }, [
    client,
    connected,
    documentContentRef,
    hasSentGreetingRef,
    promptVersionRef,
    setAgentState,
    turnCounterRef,
  ]);

  useEffect(() => {
    const getContextDeclaration: FunctionDeclaration = {
      name: 'getContext',
      description:
        "Gets the absolute source of truth for the current document state. You MUST call this before every edit to see what the user has changed or deleted. If the document is empty or sections are missing, it means the user has intentionally removed them. Do NOT restore them.",
      parameters: {
        type: Type.OBJECT,
        properties: {},
      },
    };

    const updateDocumentDeclaration: FunctionDeclaration = {
      name: 'updateDocument',
      description:
        'Replaces the entire content of the document with new text. This is the primary way to edit the document.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          content: {
            type: Type.STRING,
            description: 'The full, new content of the document.',
          },
        },
        required: ['content'],
      },
    };

    const searchGoogleDeclaration: FunctionDeclaration = {
      name: 'searchGoogle',
      description:
        'Runs a Google-grounded search for fresh, factual, or current information and returns concise notes with sources. Call this before using recent web facts, current events, or claims that need fact-checking.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          query: {
            type: Type.STRING,
            description: 'The exact research question or search topic.',
          },
        },
        required: ['query'],
      },
    };

    const updateWorkspaceSettingsDeclaration: FunctionDeclaration = {
      name: 'updateWorkspaceSettings',
      description:
        'Updates the Scribe Workspace controls: mode lens, output profile, document goal, or command instruction.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          scribeMode: {
            type: Type.STRING,
            description: 'One of: general, research, meeting, creative, legal, academic, news, technical, personal.',
          },
          exportProfile: {
            type: Type.STRING,
            description: 'One of: note, report, memo, script, study-guide, brief.',
          },
          documentGoal: {
            type: Type.STRING,
            description: 'The document goal, audience, success criteria, or constraints.',
          },
          commandInstruction: {
            type: Type.STRING,
            description: 'Standing instruction for the Workspace command engine.',
          },
        },
      },
    };

    const runWorkspaceCommandDeclaration: FunctionDeclaration = {
      name: 'runWorkspaceCommand',
      description:
        'Executes a Scribe Command Engine button such as research, expand, rewrite, summarize, compare, contradictions, outline, final, cite, or version. Use this when the user asks to press, play, run, queue, or trigger one of those buttons.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          command: {
            type: Type.STRING,
            description: 'One of: research, expand, rewrite, summarize, compare, contradictions, outline, final, cite, version.',
          },
          instruction: {
            type: Type.STRING,
            description: 'Optional one-time instruction for this command run.',
          },
        },
        required: ['command'],
      },
    };

    const clearWorkspaceDataDeclaration: FunctionDeclaration = {
      name: 'clearWorkspaceData',
      description:
        'Clears workspace data when the user asks to delete old cache, source cabinet items, document versions, transcript, Unidex Log, current document, or workspace settings.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          all: { type: Type.BOOLEAN, description: 'Clear all workspace data this tool controls while preserving the Gemini API key.' },
          sources: { type: Type.BOOLEAN, description: 'Clear all Source Cabinet items.' },
          versions: { type: Type.BOOLEAN, description: 'Clear all Document Versions and version source cards.' },
          savedDocs: { type: Type.BOOLEAN, description: 'Clear saved documents from browser storage.' },
          document: { type: Type.BOOLEAN, description: 'Clear the current working document only if explicitly requested.' },
          transcript: { type: Type.BOOLEAN, description: 'Clear the visible transcript.' },
          unidexLog: { type: Type.BOOLEAN, description: 'Clear the visible Unidex Log.' },
          workspaceSettings: { type: Type.BOOLEAN, description: 'Reset workspace mode, profile, goal, and command instruction.' },
        },
      },
    };

    const restoreWorkspaceDataDeclaration: FunctionDeclaration = {
      name: 'restoreWorkspaceData',
      description:
        'Restores data cleared earlier in the current app session. Use when the user asks to put back, undo clear, restore removed data, or recover cached workspace data. Restore points are session-only and disappear after reload/new session.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          all: { type: Type.BOOLEAN, description: 'Restore every available cleared category from the current session.' },
          sources: { type: Type.BOOLEAN, description: 'Restore the Source Cabinet from the latest session clear snapshot.' },
          versions: { type: Type.BOOLEAN, description: 'Restore Document Versions from the latest session clear snapshot.' },
          savedDocs: { type: Type.BOOLEAN, description: 'Restore saved documents from the latest session clear snapshot.' },
          document: { type: Type.BOOLEAN, description: 'Restore the current working document from the latest session clear snapshot.' },
          transcript: { type: Type.BOOLEAN, description: 'Restore the transcript from the latest session clear snapshot.' },
          unidexLog: { type: Type.BOOLEAN, description: 'Restore the Unidex Log from the latest session clear snapshot.' },
          workspaceSettings: { type: Type.BOOLEAN, description: 'Restore workspace mode, profile, goal, and command instruction.' },
        },
      },
    };

    if (connected) return;

    promptVersionRef.current += 1;
    const isGemini31Live = liveApiModel.toLowerCase().includes('gemini-3.1-flash-live');
    const enableSearchTool = useSearch;
    const systemInstructionText = createSystemInstructions(
      current,
      user,
      documentContentRef.current,
      promptVersionRef.current,
      enableSearchTool,
      imageGenerationEnabled,
      activeSources,
      scribeMode,
      documentGoal,
      exportProfile,
      workspaceInstruction,
    );
    systemInstructionTextRef.current = systemInstructionText;

    const liveConfig: LiveConnectConfig = {
      responseModalities: [Modality.AUDIO],
      inputAudioTranscription: {},
      outputAudioTranscription: {},
      speechConfig: {
        voiceConfig: {
          prebuiltVoiceConfig: { voiceName: current.voice },
        },
      },
      systemInstruction: systemInstructionText,
      tools: [
        {
          functionDeclarations: [
            getContextDeclaration,
            updateDocumentDeclaration,
            searchGoogleDeclaration,
            updateWorkspaceSettingsDeclaration,
            runWorkspaceCommandDeclaration,
            clearWorkspaceDataDeclaration,
            restoreWorkspaceDataDeclaration,
          ],
        },
      ],
    };

    if (!isGemini31Live) {
      liveConfig.thinkingConfig = { thinkingBudget: 0 };
    }

    setConfig(liveConfig);
  }, [
    connected,
    current,
    activeSources,
    documentContentRef,
    documentGoal,
    exportProfile,
    imageGenerationEnabled,
    liveApiModel,
    promptVersionRef,
    setConfig,
    scribeMode,
    systemInstructionTextRef,
    useSearch,
    user,
    workspaceInstruction,
  ]);

  useEffect(() => {
    if (!client) return;
    const handleOpen = () => {
      useLogStore.getState().addLog({
        api: 'System Prompt',
        inputSize: systemInstructionTextRef.current.length,
        outputSize: 'N/A',
        status: 'success',
        prompt: systemInstructionTextRef.current,
        promptVersion: promptVersionRef.current,
        turn: turnCounterRef.current,
      });
    };
    client.on('open', handleOpen);
    return () => {
      client.off('open', handleOpen);
    };
  }, [client, promptVersionRef, systemInstructionTextRef, turnCounterRef]);

  useEffect(() => {
    if (!connected || !client) return;

    const timeoutId = setTimeout(() => {
      const currentDoc = documentContent;
      const lastAgentDoc = docContentBeforeEditRef.current;

      if (currentDoc !== lastAgentDoc) {
        const isSignificantChange =
          Math.abs(currentDoc.length - lastAgentDoc.length) > 10 || currentDoc === '';

        if (isSignificantChange) {
          const isDeletion = currentDoc.length < lastAgentDoc.length * 0.5 || currentDoc === '';
          const message = isDeletion
            ? `(System: The user has manually deleted or significantly reduced the document content. The document is now: "${currentDoc || '[Empty]'}". Respect this deletion and do not restore the old content.)`
            : `(System: The user has manually edited the document. Please take these changes into account for future edits.)`;

          const changes = diffChars(lastAgentDoc, currentDoc);
          const added = changes.filter(c => c.added).map(c => c.value).join('');
          const removed = changes.filter(c => c.removed).map(c => c.value).join('');

          let transcriptText = '';
          if (isDeletion) {
            transcriptText = '[User manually deleted significant content]';
          } else if (added.length > 0 && added.length < 100 && removed.length === 0) {
            transcriptText = `[User manually added: "${added}"]`;
          } else if (removed.length > 0 && removed.length < 100 && added.length === 0) {
            transcriptText = `[User manually removed: "${removed}"]`;
          } else {
            transcriptText = '[User manually edited the document]';
          }

          addUnidexLog({
            kind: 'document',
            source: 'User Edit',
            title: 'Manual document edit detected',
            detail: `${transcriptText}\nCurrent size: ${currentDoc.length.toLocaleString()} characters`,
          });

          client.send([{ text: message }]);

          useLogStore.getState().addLog({
            api: 'System Message',
            inputSize: message.length,
            outputSize: 'N/A',
            status: 'success',
            prompt: message,
            promptVersion: promptVersionRef.current,
            turn: turnCounterRef.current,
          });

          addPerfLog({
            turn: turnCounterRef.current,
            event: 'System Action: Notified Agent of User Edit',
            details: { isDeletion, contentLength: currentDoc.length },
          });
        }
        docContentBeforeEditRef.current = currentDoc;
      }
    }, 3000);

    return () => clearTimeout(timeoutId);
  }, [
    addPerfLog,
    addUnidexLog,
    client,
    connected,
    documentContent,
    docContentBeforeEditRef,
    promptVersionRef,
    turnCounterRef,
    user.name,
  ]);
}
