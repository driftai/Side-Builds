/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { useLogStore } from '../../../../../lib/state';
import { combineArrayBuffers, pcmToWav } from '../../../../../lib/utils';

export function createSuppressionControls(ctx: any) {
  const updateSuppressionState = () => {
    const isStale =
      ctx.suppressStaleAgentResponses &&
      ctx.processedAgentTurnIdRef.current < ctx.latestUserTurnIdRef.current - 1;
    const isPostFlush = ctx.suppressPostFlushAudio && ctx.hasFlushedThisTurnRef.current;

    const shouldSuppress = isStale || isPostFlush;

    if (isStale && !ctx.isStaleSuppressedThisTurnRef.current) {
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: 'Agent Action: Starting Stale Response Suppression',
        details: {
          latestUserTurnId: ctx.latestUserTurnIdRef.current,
          processedAgentTurnId: ctx.processedAgentTurnIdRef.current,
        },
      });
      ctx.stopAudio();
      ctx.isStaleSuppressedThisTurnRef.current = true;
      useLogStore.getState().incrementSuppressedAudioCount();
    }

    if (isPostFlush && !ctx.isPostFlushSuppressedThisTurnRef.current) {
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: 'Agent Action: Starting Post-Flush Suppression',
        details: {
          hasFlushed: true,
        },
      });
      ctx.isPostFlushSuppressedThisTurnRef.current = true;
      useLogStore.getState().incrementSuppressedAudioCount();
    }

    ctx.isSuppressingAgentOutputRef.current = shouldSuppress;
    if (ctx.client) {
      ctx.client.suppressPlayback = shouldSuppress;
    }
  };

  const flushModelTextBuffer = (forceSuppressed = false) => {
    ctx.hasFlushedThisTurnRef.current = true;
    updateSuppressionState();
    if (ctx.isSuppressingAgentOutputRef.current || forceSuppressed) {
      const suppressedText = ctx.currentModelText.current.trim();
      const suppressedAudioChunks = ctx.currentAgentAudioChunks.current;

      if (suppressedText) {
        ctx.addSuppressedLog({
          api: 'Agent Response (Suppressed)',
          inputSize: 'N/A',
          outputSize: suppressedText.length,
          status: 'success',
          response: suppressedText,
          promptVersion: ctx.promptVersionRef.current,
          turn: ctx.turnCounterRef.current,
        });
      }

      if (suppressedAudioChunks.length > 0) {
        const combinedPCM = combineArrayBuffers(suppressedAudioChunks);
        const wav = pcmToWav(combinedPCM);
        ctx.addSuppressedLog({
          api: 'Agent Response (Audio - Suppressed)',
          inputSize: 'N/A',
          outputSize: 'N/A',
          audioSize: wav.size,
          status: 'success',
          response: `[Suppressed Audio Data: ${wav.size} bytes]`,
          promptVersion: ctx.promptVersionRef.current,
          timestamp: ctx.currentAgentTurnStartTimeRef.current || new Date(),
          endTimestamp: new Date(),
          audioBlob: wav,
          turn: ctx.turnCounterRef.current,
        });
      }

      ctx.currentModelText.current = '';
      ctx.currentAgentAudioChunks.current = [];
      return;
    }

    const pendingText = ctx.currentModelText.current.trim();
    const pendingAudioChunks = ctx.currentAgentAudioChunks.current;

    if (pendingText || pendingAudioChunks.length > 0) {
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: 'Agent Action: Flushing Buffers',
        details: { text: pendingText, audioChunks: pendingAudioChunks.length },
      });

      if (pendingText) {
        ctx.setTranscript((prev: any[]) => {
          const lastEntry = prev[prev.length - 1];
          if (lastEntry && lastEntry.speaker === ctx.agentRef.current.name) {
            return [
              ...prev.slice(0, -1),
              { ...lastEntry, text: lastEntry.text + ' ' + pendingText },
            ];
          }
          return [
            ...prev,
            { speaker: ctx.agentRef.current.name, text: pendingText },
          ];
        });
        ctx.addUnidexLog?.({
          kind: 'transcript',
          source: ctx.agentRef.current.name,
          title: 'Agent message',
          detail: pendingText,
        });
        ctx.log({
          api: 'Agent Response (Flush)',
          inputSize: 'N/A',
          outputSize: pendingText.length,
          status: 'success',
          response: pendingText,
          promptVersion: ctx.promptVersionRef.current,
          turn: ctx.turnCounterRef.current,
        });
      }

      if (pendingAudioChunks.length > 0) {
        const combinedPCM = combineArrayBuffers(pendingAudioChunks);
        const wav = pcmToWav(combinedPCM);
        ctx.log({
          api: 'Agent Response (Audio - Flush)',
          inputSize: 'N/A',
          outputSize: 'N/A',
          audioSize: wav.size,
          status: 'success',
          response: `[Flushed Audio Data: ${wav.size} bytes]`,
          promptVersion: ctx.promptVersionRef.current,
          timestamp: ctx.currentAgentTurnStartTimeRef.current || new Date(),
          endTimestamp: new Date(),
          audioBlob: wav,
          turn: ctx.turnCounterRef.current,
        });
      }

      ctx.currentModelText.current = '';
      ctx.currentAgentAudioChunks.current = [];
      ctx.lastSpeakerRef.current = 'agent';
    }
  };

  return {
    flushModelTextBuffer,
    updateSuppressionState,
  };
}
