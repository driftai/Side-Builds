/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { useEffect } from 'react';
import { useLogStore } from '../../../../lib/state';
import { createAudioTranscriptionHandlers } from './live/audioTranscription';
import { createSuppressionControls } from './live/suppression';
import { createToolCallHandler } from './live/toolCalls';
import { createTurnHandlers } from './live/turns';

export function useLiveEventHandlers(args: any) {
  useEffect(() => {
    const ctx = {
      ...args,
      addSuppressedLog: useLogStore.getState().addSuppressedLog,
      log: useLogStore.getState().addLog,
    };

    const controls = createSuppressionControls(ctx);
    controls.updateSuppressionState();

    const handleToolCall = createToolCallHandler(ctx, controls);
    const {
      handleAgentAudio,
      handleInputTranscription,
      handleOutputTranscription,
      handleUserAudio,
    } = createAudioTranscriptionHandlers(ctx, controls);
    const {
      handleGrounding,
      handleInterrupted,
      handleTurnComplete,
    } = createTurnHandlers(ctx, controls);

    if (args.audioStreamerRef.current) {
      args.audioStreamerRef.current.onStart = () => {
        args.agentAudioPlaybackStartTimeRef.current = new Date();
      };
      args.audioStreamerRef.current.onComplete = () => {
        args.agentAudioPlaybackEndTimeRef.current = new Date();
      };
    }

    args.client.on('userAudio', handleUserAudio);
    args.client.on('audio', handleAgentAudio);
    args.client.on('toolcall', handleToolCall);
    args.client.on('inputTranscription', handleInputTranscription);
    args.client.on('outputTranscription', handleOutputTranscription);
    args.client.on('turncomplete', handleTurnComplete);
    args.client.on('interrupted', handleInterrupted);
    args.client.on('grounding', handleGrounding);

    return () => {
      args.client.off('userAudio', handleUserAudio);
      args.client.off('audio', handleAgentAudio);
      args.client.off('toolcall', handleToolCall);
      args.client.off('inputTranscription', handleInputTranscription);
      args.client.off('outputTranscription', handleOutputTranscription);
      args.client.off('turncomplete', handleTurnComplete);
      args.client.off('interrupted', handleInterrupted);
      args.client.off('grounding', handleGrounding);
    };
  }, [
    args.addPerfLog,
    args.addUnidexLog,
    args.activeSources,
    args.clearWorkspaceRuntime,
    args.client,
    args.current.name,
    args.documentGoal,
    args.documentContent,
    args.exportProfile,
    args.incrementChangeCount,
    args.outputModality,
    args.restoreWorkspaceRuntime,
    args.runWorkspaceCommand,
    args.scribeMode,
    args.workspaceInstruction,
    args.setAgentState,
    args.setSpeechBubbleText,
    args.stopAudio,
    args.suppressPostFlushAudio,
    args.suppressStaleAgentResponses,
    args.user.name,
  ]);
}
