/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { MutableRefObject, useCallback } from 'react';
import type { GoogleGenAI } from '@google/genai';
import { PLACEHOLDER_DOC } from '../../../../lib/constants';
import { GenAILiveClient } from '../../../../lib/genai-live-client';
import { useSourceStore, type MainTab } from '../../../../lib/state';
import type { UnidexLogEntry } from '../types';
import {
  formatGroundedSearchMarkdown,
  runGroundedGoogleSearch,
} from '../utils/groundedSearch';

type UseWelcomeShortcutsArgs = {
  addPerfLog: (log: any) => void;
  ai: MutableRefObject<GoogleGenAI | null>;
  client: GenAILiveClient;
  connect: () => Promise<void>;
  connected: boolean;
  documentContentRef: MutableRefObject<string>;
  isConnecting: boolean;
  pushToHistory: (content: string) => void;
  setDocumentContent: (content: string | ((prev: string) => string)) => void;
  setDocumentTab: (tab: 'editor' | 'rendered') => void;
  setMainTab: (tab: MainTab) => void;
  setShowUserConfig: (show: boolean) => void;
  setSpeechBubbleText: (text: string | null) => void;
  addUnidexLog: (entry: Omit<UnidexLogEntry, 'id' | 'timestamp'>) => void;
  setUseSearch: (useSearch: boolean) => void;
  startNewSession: () => void;
  topic?: string;
  userContext?: string;
};

export function useWelcomeShortcuts({
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
  topic,
  userContext,
}: UseWelcomeShortcutsArgs) {
  const appendShortcutContent = useCallback((content: string) => {
    setMainTab('document');
    setDocumentTab('rendered');
    pushToHistory(documentContentRef.current);
    setDocumentContent(prevContent => {
      if (!prevContent || prevContent === PLACEHOLDER_DOC) return content;
      return `${prevContent.trimEnd()}\n\n${content}`;
    });
  }, [documentContentRef, pushToHistory, setDocumentContent, setDocumentTab, setMainTab]);

  const handleStartConversation = useCallback(() => {
    setMainTab('document');
    setDocumentTab('rendered');
    if (connected || isConnecting) {
      setSpeechBubbleText('Scribe is already listening.');
      return;
    }
    startNewSession();
    addPerfLog({ turn: 0, event: 'Shortcut: Conversational Writing' });
    connect();
  }, [
    addPerfLog,
    connect,
    connected,
    isConnecting,
    setDocumentTab,
    setMainTab,
    setSpeechBubbleText,
    startNewSession,
  ]);

  const handleEnableSearchShortcut = useCallback(async () => {
    setUseSearch(true);
    setMainTab('document');
    setDocumentTab('rendered');
    setSpeechBubbleText('Searching Google...');
    addPerfLog({ turn: 0, event: 'Shortcut: Google Search' });

    const currentDocument = documentContentRef.current;
    const fallbackQuery =
      currentDocument && currentDocument !== PLACEHOLDER_DOC
        ? currentDocument.slice(0, 900)
        : '';
    const query = topic || fallbackQuery || 'current research for this Scribe document';
    addUnidexLog({
      kind: 'tool',
      source: 'Google Search',
      title: 'Shortcut search started',
      detail: `Query: ${query}`,
    });

    try {
      const result = await runGroundedGoogleSearch(ai.current, {
        documentContent: currentDocument,
        query,
        topic,
        userContext,
      });
      const markdown = formatGroundedSearchMarkdown(result);
      appendShortcutContent(markdown);
      useSourceStore.getState().addSource({
        kind: 'search',
        title: `Shortcut search: ${query.slice(0, 80)}`,
        content: markdown,
        tags: ['hot', 'search'],
        active: true,
        meta: { model: result.model, sources: result.sources.length },
      });
      addUnidexLog({
        kind: 'tool',
        source: 'Google Search',
        title: 'Shortcut search completed',
        detail: `Model: ${result.model}\nSources: ${result.sources.length}\nQueries: ${result.queries.join('; ') || 'N/A'}`,
      });
      addUnidexLog({
        kind: 'document',
        source: 'Scribe',
        title: 'Search notes inserted',
        detail: `Added ${markdown.length.toLocaleString()} characters of grounded notes to the document.`,
      });
      setSpeechBubbleText('Google Search notes added to the document.');

      if (connected) {
        client.send([{
          text: `(System: Google Search returned these grounded notes. Use them as current research context for future edits.)\n\n${markdown}`,
        }]);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const quotaHit = /quota|resource_exhausted|billing|exceeded/i.test(message);
      setSpeechBubbleText(
        quotaHit
          ? 'Google Search quota or billing blocked this request.'
          : 'Google Search failed. Check the API key and try again.',
      );
      addPerfLog({
        turn: 0,
        event: 'Shortcut Error: Google Search',
        details: { message },
      });
      addUnidexLog({
        kind: 'error',
        source: 'Google Search',
        title: 'Shortcut search failed',
        detail: message,
      });

      if (connected) {
        const topicText = topic ? ` about "${topic}"` : '';
        client.send([{
          text: `Google Search could not run${topicText}. Continue without claiming fresh web results unless the user provides source material.`,
        }]);
      }
    }
  }, [
    addPerfLog,
    ai,
    appendShortcutContent,
    client,
    connected,
    documentContentRef,
    setDocumentTab,
    setMainTab,
    setSpeechBubbleText,
    addUnidexLog,
    setUseSearch,
    topic,
    userContext,
  ]);

  const handlePdfContextShortcut = useCallback(() => {
    setShowUserConfig(true);
  }, [setShowUserConfig]);

  const handleInsertGraphShortcut = useCallback(() => {
    const graphId = `graph_shortcut_${Date.now()}`;
    appendShortcutContent(
      `## Interactive Graph\n\n[graph id="${graphId}" title="Sine and Cosine" functions="['sin(x)', 'cos(x)']" labels="['sin(x)', 'cos(x)']" xDomain="[-2*pi, 2*pi]" yDomain="[-1.5, 1.5]" xLabel="x" yLabel="y" colors="['#4285f4', '#34a853']" width="90%"]`,
    );
    addUnidexLog({
      kind: 'shortcut',
      source: 'Shortcut',
      title: 'Inserted graph template',
      detail: `Graph id: ${graphId}`,
    });
  }, [addUnidexLog, appendShortcutContent]);

  const handleInsertIllustrationShortcut = useCallback(() => {
    const imageId = `img_shortcut_${Date.now()}`;
    appendShortcutContent(
      `## Visual Illustration\n\n[illustration id="${imageId}" prompt="A clean educational diagram showing a collaborative AI scribe turning a spoken conversation into structured notes, with subtle labels and a bright professional style" width="80%"]\n\n<p align="center"><i>Generated visual reference.</i></p>`,
    );
    addUnidexLog({
      kind: 'shortcut',
      source: 'Shortcut',
      title: 'Inserted illustration prompt',
      detail: `Illustration id: ${imageId}`,
    });
  }, [addUnidexLog, appendShortcutContent]);

  const handleEditDocumentShortcut = useCallback(() => {
    setMainTab('document');
    setDocumentTab('editor');
    window.setTimeout(() => {
      const textarea = document.querySelector<HTMLTextAreaElement>('.document-textarea');
      textarea?.focus();
      if (textarea?.value === PLACEHOLDER_DOC) textarea.select();
    }, 0);
  }, [setDocumentTab, setMainTab]);

  return {
    handleStartConversation,
    handleEnableSearchShortcut,
    handlePdfContextShortcut,
    handleInsertGraphShortcut,
    handleInsertIllustrationShortcut,
    handleEditDocumentShortcut,
  };
}
