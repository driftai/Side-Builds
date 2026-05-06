/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

const getVisibleUserText = (text: string) =>
  text
    .replace(
      /^\s*Use Google Search if available to research and fact-check\. Add concise findings to the document\.\s*/i,
      '',
    );

export function createAudioTranscriptionHandlers(ctx: any, controls: any) {
  const handleUserAudio = (data: ArrayBuffer) => {
    ctx.currentUserAudioChunks.current.push(data);
  };

  const handleAgentAudio = (data: ArrayBuffer) => {
    controls.updateSuppressionState();
    ctx.currentAgentAudioChunks.current.push(data);

    if (ctx.isSuppressingAgentOutputRef.current) {
      return;
    }
    if (!ctx.currentAgentTurnStartTimeRef.current) {
      ctx.currentAgentTurnStartTimeRef.current = new Date();
    }
    if (!ctx.hasLoggedFirstAgentAudioThisTurnRef.current) {
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: 'Agent Response: First Audio Chunk Received',
        details: { size: data.byteLength },
      });
      ctx.log({
        api: 'Agent Response (Audio)',
        inputSize: 'N/A',
        outputSize: 'N/A',
        audioSize: data.byteLength,
        status: 'success',
        response: `[Audio Data: ${data.byteLength} bytes]`,
        promptVersion: ctx.promptVersionRef.current,
        timestamp: ctx.currentAgentTurnStartTimeRef.current,
        turn: ctx.turnCounterRef.current,
      });
      ctx.hasLoggedFirstAgentAudioThisTurnRef.current = true;
    }
  };

  const handleInputTranscription = (text: string, source?: 'client' | 'server') => {
    const visibleText = getVisibleUserText(text);
    if (!visibleText.trim()) {
      return;
    }
    if (
      source === 'server' &&
      ctx.typedUserCommittedRef?.current &&
      ctx.currentUserText.current.trim() === visibleText.trim()
    ) {
      return;
    }

    if (!ctx.currentUserTurnStartTimeRef.current) {
      ctx.currentUserTurnStartTimeRef.current = new Date();
    }
    ctx.setAgentState('Listening');
    if (!ctx.hasLoggedFirstUserTextThisTurnRef.current) {
      ctx.turnCounterRef.current += 1;
      ctx.hasFlushedThisTurnRef.current = false;
      ctx.isStaleSuppressedThisTurnRef.current = false;
      ctx.isPostFlushSuppressedThisTurnRef.current = false;
      ctx.hasSearchedThisTurnRef.current = false;
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: 'User Speech: First Text Chunk Received',
        details: { text: visibleText.trim() },
      });
      ctx.hasLoggedFirstUserTextThisTurnRef.current = true;
    }
    if (ctx.isAgentSpeakingRef.current) {
      ctx.selfInterruptionDetectedRef.current = true;
    }
    ctx.currentUserText.current += visibleText;

    if (source === 'client') {
      const userText = ctx.currentUserText.current.trim();
      if (userText) {
        ctx.setTranscript((prev: any[]) => [
          ...prev,
          { speaker: ctx.userRef.current.name || 'User', text: userText },
        ]);
        ctx.addUnidexLog?.({
          kind: 'transcript',
          source: ctx.userRef.current.name || 'User',
          title: 'User message',
          detail: userText,
        });
        ctx.lastUserRequestRef.current = userText;
        if (ctx.typedUserCommittedRef) {
          ctx.typedUserCommittedRef.current = true;
        }
      }
    }
  };

  const handleOutputTranscription = (text: string) => {
    controls.updateSuppressionState();

    const isSuppressed = ctx.isSuppressingAgentOutputRef.current;

    if (isSuppressed) {
      const isStale =
        ctx.suppressStaleAgentResponses &&
        ctx.processedAgentTurnIdRef.current < ctx.latestUserTurnIdRef.current - 1;
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: isStale
          ? 'Agent Response: Suppressed Stale Text'
          : 'Agent Response: Suppressed Post-Flush Text',
        details: {
          text,
          latestUserTurnId: ctx.latestUserTurnIdRef.current,
          processedAgentTurnId: ctx.processedAgentTurnIdRef.current,
          hasFlushed: ctx.hasFlushedThisTurnRef.current,
        },
      });
    }

    if (!ctx.hasLoggedFirstAgentTextThisTurnRef.current && text.trim()) {
      if (!ctx.currentAgentTurnStartTimeRef.current) {
        ctx.currentAgentTurnStartTimeRef.current = new Date();
      }
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: isSuppressed
          ? 'Agent Response: First Text Chunk Received (Suppressed)'
          : 'Agent Response: First Text Chunk Received',
        details: { text },
      });
      ctx.log({
        api: isSuppressed ? 'Agent Response (Text - Suppressed)' : 'Agent Response (Text)',
        inputSize: 'N/A',
        outputSize: text.length,
        status: 'success',
        response: text,
        promptVersion: ctx.promptVersionRef.current,
        timestamp: ctx.currentAgentTurnStartTimeRef.current,
        turn: ctx.turnCounterRef.current,
      });
      ctx.hasLoggedFirstAgentTextThisTurnRef.current = true;
    }

    if (!ctx.isAgentSpeakingRef.current) {
      ctx.isAgentSpeakingRef.current = true;
      ctx.setAgentState(null);
    }
    ctx.currentModelText.current += text;
    if (!isSuppressed && (ctx.outputModality === 'text' || ctx.outputModality === 'both')) {
      ctx.setSpeechBubbleText(ctx.currentModelText.current);
    }
  };

  return {
    handleAgentAudio,
    handleInputTranscription,
    handleOutputTranscription,
    handleUserAudio,
  };
}
