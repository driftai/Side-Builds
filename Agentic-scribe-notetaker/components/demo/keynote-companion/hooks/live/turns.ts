/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { combineArrayBuffers, pcmToWav } from '../../../../../lib/utils';

export function createTurnHandlers(ctx: any, controls: any) {
  const handleTurnComplete = () => {
    const now = Date.now();
    if (now - ctx.lastTurnCompleteTimestampRef.current < 500) {
      return;
    }
    ctx.lastTurnCompleteTimestampRef.current = now;
    const userFinal = ctx.currentUserText.current.trim();
    const agentFinal = ctx.currentModelText.current.trim();
    const userAlreadyCommitted = Boolean(ctx.typedUserCommittedRef?.current);

    ctx.setTranscript((prev: any[]) => {
      const nextTranscript = [...prev];
      if (userFinal && !userAlreadyCommitted) {
        nextTranscript.push({
          speaker: ctx.userRef.current.name || 'User',
          text: userFinal,
        });
      }
      if (agentFinal && !ctx.isSuppressingAgentOutputRef.current) {
        const lastEntry = nextTranscript[nextTranscript.length - 1];
        if (
          lastEntry &&
          lastEntry.speaker === ctx.agentRef.current.name &&
          !userFinal
        ) {
          nextTranscript[nextTranscript.length - 1] = {
            ...lastEntry,
            text: lastEntry.text + ' ' + agentFinal,
          };
        } else {
          nextTranscript.push({
            speaker: ctx.agentRef.current.name,
            text: agentFinal,
          });
        }
      }
      return nextTranscript;
    });

    if (userFinal) {
      if (ctx.lastUserRequestRef) {
        ctx.lastUserRequestRef.current = userFinal;
      }
      if (!userAlreadyCommitted) {
        ctx.addUnidexLog?.({
          kind: 'transcript',
          source: ctx.userRef.current.name || 'User',
          title: 'User message',
          detail: userFinal,
        });
      }
      ctx.latestUserTurnIdRef.current++;
      controls.updateSuppressionState();
      ctx.hasLoggedFirstAgentAudioThisTurnRef.current = false;
      ctx.hasLoggedFirstAgentTextThisTurnRef.current = false;
      ctx.hasLoggedFirstUserTextThisTurnRef.current = false;
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: 'User Turn: End Detected',
        details: { text: userFinal, turnId: ctx.latestUserTurnIdRef.current },
      });
      ctx.setAgentState('Thinking');
      const combinedUserAudioPCM = combineArrayBuffers(ctx.currentUserAudioChunks.current);
      const combinedUserAudioWav = pcmToWav(combinedUserAudioPCM);

      if (combinedUserAudioWav.size > 0) {
        ctx.setAudioLog((prev: any[]) => [
          ...prev,
          {
            speaker: ctx.user.name || 'User',
            blob: combinedUserAudioWav,
            timestamp: new Date(),
          },
        ]);
      }
      ctx.log({
        api: 'User Speech (Final)',
        inputSize: userFinal.length,
        outputSize: 'N/A',
        audioSize: combinedUserAudioWav.size,
        status: 'success',
        prompt: userFinal,
        promptVersion: ctx.promptVersionRef.current,
        timestamp: ctx.currentUserTurnStartTimeRef.current || new Date(),
        endTimestamp: new Date(),
        audioBlob: combinedUserAudioWav,
        turn: ctx.turnCounterRef.current,
      });
      ctx.currentUserTurnStartTimeRef.current = null;
      ctx.lastSpeakerRef.current = 'user';
    }

    if (agentFinal || ctx.isSuppressingAgentOutputRef.current) {
      if (agentFinal && !ctx.isSuppressingAgentOutputRef.current) {
        ctx.addUnidexLog?.({
          kind: 'transcript',
          source: ctx.agentRef.current.name,
          title: 'Agent message',
          detail: agentFinal,
        });
      }
      ctx.processedAgentTurnIdRef.current++;
      controls.updateSuppressionState();
      ctx.setAgentState('Waiting');
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: 'Agent Turn: End Detected',
        details: {
          text: agentFinal,
          processedTurnId: ctx.processedAgentTurnIdRef.current,
          wasSuppressed: ctx.isSuppressingAgentOutputRef.current,
        },
      });
      const combinedAgentAudioPCM = combineArrayBuffers(ctx.currentAgentAudioChunks.current);
      const combinedAgentAudioWav = pcmToWav(combinedAgentAudioPCM);

      const isSuppressed = ctx.isSuppressingAgentOutputRef.current;

      if (combinedAgentAudioWav.size > 0) {
        if (!isSuppressed) {
          ctx.setAudioLog((prev: any[]) => [
            ...prev,
            {
              speaker: ctx.current.name,
              blob: combinedAgentAudioWav,
              timestamp: new Date(),
            },
          ]);
        }

        const logFn = isSuppressed ? ctx.addSuppressedLog : ctx.log;
        logFn({
          api: isSuppressed ? 'Agent Response (Audio - Suppressed)' : 'Agent Response (Audio)',
          inputSize: 'N/A',
          outputSize: 'N/A',
          audioSize: combinedAgentAudioWav.size,
          status: 'success',
          response: `[Full Audio Data: ${combinedAgentAudioWav.size} bytes]${isSuppressed ? ' (Suppressed)' : ''}`,
          promptVersion: ctx.promptVersionRef.current,
          timestamp:
            ctx.agentAudioPlaybackStartTimeRef.current ||
            ctx.currentAgentTurnStartTimeRef.current ||
            new Date(),
          endTimestamp: ctx.agentAudioPlaybackEndTimeRef.current || new Date(),
          audioBlob: combinedAgentAudioWav,
          turn: ctx.turnCounterRef.current,
        });
      }
      if (agentFinal) {
        const logFn = isSuppressed ? ctx.addSuppressedLog : ctx.log;
        logFn({
          api: isSuppressed ? 'Agent Response (Text - Suppressed)' : 'Agent Response (Text)',
          inputSize: 'N/A',
          outputSize: agentFinal.length,
          status: 'success',
          response: agentFinal,
          promptVersion: ctx.promptVersionRef.current,
          timestamp:
            ctx.agentAudioPlaybackStartTimeRef.current ||
            ctx.currentAgentTurnStartTimeRef.current ||
            new Date(),
          endTimestamp: ctx.agentAudioPlaybackEndTimeRef.current || new Date(),
          turn: ctx.turnCounterRef.current,
        });
      }
      ctx.currentAgentTurnStartTimeRef.current = null;
      ctx.agentAudioPlaybackStartTimeRef.current = null;
      ctx.agentAudioPlaybackEndTimeRef.current = null;
      ctx.lastSpeakerRef.current = 'agent';
    }

    ctx.currentUserText.current = '';
    if (ctx.typedUserCommittedRef) {
      ctx.typedUserCommittedRef.current = false;
    }
    ctx.currentModelText.current = '';
    ctx.currentUserAudioChunks.current = [];
    ctx.currentAgentAudioChunks.current = [];
    ctx.selfInterruptionDetectedRef.current = false;
    ctx.isAgentSpeakingRef.current = false;
  };

  const handleGrounding = (metadata: any) => {
    ctx.addPerfLog({
      turn: ctx.turnCounterRef.current,
      event: 'Agent Response: Grounding Metadata Received',
      details: metadata,
    });
    ctx.hasSearchedThisTurnRef.current = true;
  };

  const handleInterrupted = () => {
    ctx.stopAudio();
    controls.flushModelTextBuffer(true);
  };

  return {
    handleGrounding,
    handleInterrupted,
    handleTurnComplete,
  };
}
