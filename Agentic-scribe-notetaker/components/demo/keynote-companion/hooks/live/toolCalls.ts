/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { FunctionResponse, LiveServerToolCall } from '@google/genai';
import { PLACEHOLDER_DOC } from '../../../../../lib/constants';
import { useSourceStore, useVersionStore } from '../../../../../lib/state';
import { cleanDocumentContent, requiresFreshSearchForUserRequest } from '../../utils/documentCleanup';
import { formatGroundedSearchMarkdown, runGroundedGoogleSearch } from '../../utils/groundedSearch';
import {
  clearWorkspaceDataFromTool,
  looksLikeCommandButtonRequest,
  normalizeCommandId,
  restoreWorkspaceDataFromTool,
  runWorkspaceCommandFromTool,
} from './workspaceTools';

const SEARCH_PREVIEW_LENGTH = 380;

const addSearchTranscript = (ctx: any, text: string) => {
  ctx.addUnidexLog?.({
    kind: 'tool',
    source: 'Google Search',
    title: 'Search activity',
    detail: text,
  });
};

const addDocumentTranscript = (ctx: any, text: string) => {
  ctx.addUnidexLog?.({
    kind: 'document',
    source: 'Document',
    title: 'Document updated',
    detail: text,
  });
};

const summarizeSearchSources = (sources: Array<{ title: string }>) => {
  if (!sources.length) return 'No source list was returned.';
  return `Top sources: ${sources
    .slice(0, 3)
    .map(source => source.title)
    .join('; ')}.`;
};

const summarizeSearchQueries = (queries: string[]) =>
  queries.length ? ` Search queries: ${queries.slice(0, 3).join('; ')}.` : '';

const summarizeSearchText = (text: string) => {
  const normalizedText = text.replace(/\s+/g, ' ').trim();
  if (!normalizedText) return '';
  const preview = normalizedText.length > SEARCH_PREVIEW_LENGTH
    ? `${normalizedText.slice(0, SEARCH_PREVIEW_LENGTH)}...`
    : normalizedText;
  return ` Result preview: ${preview}`;
};

const summarizeDocumentUpdate = (content: string) => {
  const normalizedContent = content.replace(/\s+/g, ' ').trim();
  const preview = normalizedContent.length > 220
    ? `${normalizedContent.slice(0, 220)}...`
    : normalizedContent;
  return `Updated the document to ${content.length.toLocaleString()} characters. Preview: ${preview}`;
};

const scribeModes = new Set(['general', 'research', 'meeting', 'creative', 'legal', 'academic', 'news', 'technical', 'personal']);
const exportProfiles = new Set(['note', 'report', 'memo', 'script', 'study-guide', 'brief']);

const currentRequestText = (ctx: any) =>
  ctx.currentUserText?.current?.trim() || ctx.lastUserRequestRef?.current?.trim() || '';

export function createToolCallHandler(ctx: any, controls: any) {
  return async (toolCall: LiveServerToolCall) => {
    controls.updateSuppressionState();
    const isStale =
      ctx.suppressStaleAgentResponses &&
      ctx.processedAgentTurnIdRef.current < ctx.latestUserTurnIdRef.current - 1;

    if (isStale) {
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: 'Agent Action: Suppressed Stale Tool Call',
        details: {
          functionNames: toolCall.functionCalls.map(fc => fc.name),
          latestUserTurnId: ctx.latestUserTurnIdRef.current,
          processedAgentTurnId: ctx.processedAgentTurnIdRef.current,
        },
      });
      const functionResponses: FunctionResponse[] =
        toolCall.functionCalls.map(fc => ({
          id: fc.id,
          name: fc.name,
          response: { result: { status: 'OK - Suppressed by client' } },
        }));
      ctx.client.sendToolResponse({ functionResponses });
      ctx.log({
        api: 'Function Call (Response - Suppressed)',
        inputSize: 'N/A',
        outputSize: JSON.stringify(functionResponses).length,
        status: 'success',
        response: JSON.stringify(functionResponses),
        promptVersion: ctx.promptVersionRef.current,
        turn: ctx.turnCounterRef.current,
      });
      return;
    }

    ctx.log({
      api: 'Function Call (Received)',
      inputSize: 'N/A',
      outputSize: 'N/A',
      status: 'success',
      prompt: JSON.stringify(toolCall.functionCalls),
      promptVersion: ctx.promptVersionRef.current,
      turn: ctx.turnCounterRef.current,
    });
    ctx.addPerfLog({
      turn: ctx.turnCounterRef.current,
      event: 'Agent Action: Tool Call Received',
      details: { functionNames: toolCall.functionCalls.map(fc => fc.name) },
    });
    controls.flushModelTextBuffer();
    const functionResponses: FunctionResponse[] = [];

    for (const fc of toolCall.functionCalls) {
      let result: Record<string, any> = { status: 'OK' };

      switch (fc.name) {
        case 'getContext': {
          ctx.setAgentState('Processing Context');
          const currentDoc = ctx.documentContentRef.current;
          const documentContext =
            currentDoc === PLACEHOLDER_DOC
              ? '(The document is currently empty.)'
              : currentDoc;
          const recentTranscript = ctx.transcriptRef.current
            .slice(-10)
            .map((t: any) => `${t.speaker}: ${t.text}`)
            .join('\n');
          const activeSources = (ctx.activeSources || [])
            .slice(0, 8)
            .map((source: any, index: number) =>
              `--- ACTIVE SOURCE ${index + 1}: ${source.title} (${source.kind}) ---\nSource ID for citations: ${source.id}\n${source.content.slice(0, 1200)}`,
            )
            .join('\n\n');
          const activeSourceCount = (ctx.activeSources || []).length;
          const fullContext = `
User: "${ctx.userRef.current.name}"
Writing Topic: "${ctx.userRef.current.topic}"
Output Format: ${ctx.userRef.current.format}
Document Goal: ${ctx.documentGoal || '(No explicit goal set.)'}
Output Profile: ${ctx.exportProfile || 'note'}
Scribe Mode: ${ctx.scribeMode || 'general'}
Workspace Command Instruction: ${ctx.workspaceInstruction || '(No standing command instruction set.)'}
User's Background Info: "${ctx.userRef.current.info}"
Here is the current state of the document we are working on:
---
${documentContext}
---
Here is the recent conversation history:
${recentTranscript}
Here are active Source Cabinet items:
${activeSources || '(No active sources selected.)'}`;
          result = { text: fullContext };
          ctx.addUnidexLog?.({
            kind: 'tool',
            source: 'Live Tool',
            title: 'Context requested',
            detail: `Returned current document context (${documentContext.length.toLocaleString()} characters), recent transcript, and ${activeSourceCount} active Source Cabinet item(s) to ${ctx.agentRef?.current?.name || 'the live agent'}.`,
          });
          break;
        }
        case 'updateDocument': {
          ctx.setAgentState(ctx.hasSearchedThisTurnRef.current ? 'Search based update' : 'Updating Document');
          const { content } = fc.args;
          if (typeof content === 'string') {
            const requestText = currentRequestText(ctx);
            if (requiresFreshSearchForUserRequest(requestText) && !ctx.hasSearchedThisTurnRef.current) {
              result = {
                status: 'ERROR',
                message: 'This user request asks for quotes, citations, sources, or verification. Call searchGoogle in this same turn before updateDocument.',
              };
              ctx.setAgentState('Search required');
              ctx.addUnidexLog?.({
                kind: 'tool',
                source: 'Document Guard',
                title: 'Document update blocked',
                detail: 'Quote/source-sensitive update blocked until a fresh Google Search runs in this turn.',
              });
              break;
            }
            const cleaned = cleanDocumentContent(content);
            const version = useVersionStore.getState().addVersion({
              title: `Before agent edit ${new Date().toLocaleTimeString()}`,
              content: ctx.documentContentRef.current,
              reason: 'Pre-agent edit snapshot',
            });
            useSourceStore.getState().addSource({
              id: `version_${version.id}`,
              kind: 'version',
              title: version.title,
              content: ctx.documentContentRef.current,
              tags: ['cold', 'version'],
              active: false,
            });
            ctx.pushToHistory(ctx.documentContentRef.current);
            ctx.setDocumentContent(cleaned.content);
            ctx.incrementChangeCount();
            ctx.docContentBeforeEditRef.current = cleaned.content;
            addDocumentTranscript(
              ctx,
              `${summarizeDocumentUpdate(cleaned.content)}${
                cleaned.removedConversationalBlocks
                  ? ` Removed ${cleaned.removedConversationalBlocks} conversational block(s).`
                  : ''
              }`,
            );
          }
          break;
        }
        case 'updateWorkspaceSettings': {
          ctx.setAgentState('Updating Workspace');
          const args = (fc.args ?? {}) as Record<string, unknown>;
          const changed: string[] = [];
          const nextMode = typeof args.scribeMode === 'string' ? args.scribeMode : '';
          const nextProfile = typeof args.exportProfile === 'string' ? args.exportProfile : '';
          let blocked = false;

          if (nextMode && scribeModes.has(nextMode)) {
            ctx.setScribeMode?.(nextMode);
            changed.push(`mode=${nextMode}`);
          }
          if (nextProfile && exportProfiles.has(nextProfile)) {
            ctx.setExportProfile?.(nextProfile);
            changed.push(`profile=${nextProfile}`);
          }
          if (typeof args.documentGoal === 'string') {
            ctx.setDocumentGoal?.(args.documentGoal);
            changed.push('document goal');
          }
          if (typeof args.commandInstruction === 'string') {
            const command = looksLikeCommandButtonRequest(args.commandInstruction)
              ? normalizeCommandId(args.commandInstruction)
              : '';
            if (command && ctx.runWorkspaceCommand) {
              try {
                await ctx.runWorkspaceCommand(command, ctx.workspaceInstruction || '');
                changed.push(`ran command=${command}`);
              } catch (error) {
                result = { status: 'ERROR', message: error instanceof Error ? error.message : String(error) };
                blocked = true;
              }
            } else if (command) {
              result = {
                status: 'ERROR',
                message: 'This looks like a Workspace command button request. Call runWorkspaceCommand instead.',
              };
              blocked = true;
            } else {
              ctx.setWorkspaceInstruction?.(args.commandInstruction);
              changed.push('command instruction');
            }
          }

          if (!blocked) result = { status: 'OK', changed };
          ctx.addUnidexLog?.({
            kind: 'tool',
            source: 'Workspace',
            title: 'Workspace settings updated',
            detail: changed.length ? changed.join(', ') : 'No valid workspace fields were changed.',
          });
          break;
        }
        case 'runWorkspaceCommand': {
          result = await runWorkspaceCommandFromTool(ctx, (fc.args ?? {}) as Record<string, unknown>);
          break;
        }
        case 'clearWorkspaceData': {
          result = clearWorkspaceDataFromTool(ctx, (fc.args ?? {}) as Record<string, unknown>);
          break;
        }
        case 'restoreWorkspaceData': {
          result = restoreWorkspaceDataFromTool(ctx, (fc.args ?? {}) as Record<string, unknown>);
          break;
        }
        case 'searchGoogle': {
          ctx.setAgentState('SEARCHING');
          ctx.hasSearchedThisTurnRef.current = true;
          const args = (fc.args ?? {}) as Record<string, unknown>;
          const query = typeof args.query === 'string'
            ? args.query
            : ctx.userRef.current.topic || 'current research for this document';
          const originalUserRequest =
            ctx.currentUserText?.current?.trim() ||
            ctx.lastUserRequestRef?.current?.trim();
          addSearchTranscript(ctx, `Searching Google for: "${query}"`);

          try {
            const searchResult = await runGroundedGoogleSearch(ctx.ai?.current, {
              documentContent: ctx.documentContentRef.current,
              originalUserRequest,
              query,
              topic: ctx.userRef.current.topic,
              userContext: ctx.userRef.current.info,
            });

            const searchMarkdown = formatGroundedSearchMarkdown(searchResult);
            const searchSource = useSourceStore.getState().addSource({
              kind: 'search',
              title: `Search: ${query.slice(0, 80)}`,
              content: searchMarkdown,
              summary: summarizeSearchText(searchResult.text).replace(/^ Result preview: /, ''),
              tags: ['hot', 'search'],
              active: true,
              meta: {
                model: searchResult.model,
                sourceCount: searchResult.sources.length,
              },
            });
            result = {
              status: 'OK',
              queries: searchResult.queries,
              sources: searchResult.sources,
              sourceId: searchSource.id,
              sourceCitation: `[${searchSource.title}](#src:${searchSource.id})`,
              text: searchResult.text,
            };
            ctx.addPerfLog({
              turn: ctx.turnCounterRef.current,
              event: 'Agent Action: Google Search Complete',
              details: {
                model: searchResult.model,
                query,
                sourceCount: searchResult.sources.length,
              },
            });
            addSearchTranscript(
              ctx,
              `Returned ${searchResult.sources.length} source-backed results to ${
                ctx.agentRef?.current?.name || 'the live agent'
              } using ${searchResult.model}.${summarizeSearchQueries(searchResult.queries)} ${summarizeSearchSources(searchResult.sources)}${summarizeSearchText(searchResult.text)}`,
            );
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            result = { status: 'ERROR', message };
            ctx.setSpeechBubbleText('Google Search failed. Check API key, quota, or billing.');
            addSearchTranscript(ctx, `Search failed before results could be returned: ${message}`);
            ctx.addPerfLog({
              turn: ctx.turnCounterRef.current,
              event: 'Agent Action: Google Search Failed',
              details: { message },
            });
          }
          break;
        }
      }
      functionResponses.push({
        id: fc.id,
        name: fc.name,
        response: { result },
      });
    }

    if (functionResponses.length > 0) {
      ctx.client.sendToolResponse({ functionResponses });
      ctx.hasFlushedThisTurnRef.current = false;
      controls.updateSuppressionState();

      ctx.log({
        api: 'Function Call (Response)',
        inputSize: 'N/A',
        outputSize: JSON.stringify(functionResponses).length,
        status: 'success',
        response: JSON.stringify(functionResponses),
        promptVersion: ctx.promptVersionRef.current,
        turn: ctx.turnCounterRef.current,
      });
      ctx.addPerfLog({
        turn: ctx.turnCounterRef.current,
        event: 'Agent Action: Tool Response Sent',
        details: { functionResponses },
      });
    }
  };
}
