/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React, { useEffect } from 'react';
import { PLACEHOLDER_DOC } from '../../../../lib/constants';
import {
  useLogStore,
  useSourceStore,
  useStorageStore,
  useVersionStore,
} from '../../../../lib/state';
import type { UnidexLogEntry } from '../types';

type UseDocumentLoadActionsArgs = {
  addPerfLog: (entry: any) => void;
  addUnidexLog: (entry: Omit<UnidexLogEntry, 'id' | 'timestamp'>) => void;
  client: any;
  connected: boolean;
  docContentBeforeEditRef: React.MutableRefObject<string>;
  documentContentRef: React.MutableRefObject<string>;
  promptVersionRef: React.MutableRefObject<number>;
  pushToHistory: (content: string) => void;
  setDocumentContent: (content: string | ((prev: string) => string)) => void;
  turnCounterRef: React.MutableRefObject<number>;
  user: any;
};

export function useDocumentLoadActions({
  addPerfLog,
  addUnidexLog,
  client,
  connected,
  docContentBeforeEditRef,
  documentContentRef,
  promptVersionRef,
  pushToHistory,
  setDocumentContent,
  turnCounterRef,
  user,
}: UseDocumentLoadActionsArgs) {
  const applySwapDoc = (text: string, source: { kind: 'upload' | 'storage'; label: string }) => {
    const previousDoc = documentContentRef.current;
    if (previousDoc && previousDoc !== PLACEHOLDER_DOC) {
      useVersionStore.getState().addVersion({
        title: `Before ${source.kind === 'upload' ? 'upload' : 'storage load'}`,
        content: previousDoc,
        reason: 'Pre-replacement snapshot',
      });
    }
    pushToHistory(previousDoc);
    setDocumentContent(text);
    docContentBeforeEditRef.current = text;
    useSourceStore.getState().addSource({
      kind: source.kind,
      title: source.label,
      content: text,
      tags: ['cold', source.kind],
      active: true,
    });

    if (connected && client) {
      const previousDocBlock =
        previousDoc && previousDoc !== PLACEHOLDER_DOC
          ? `

The PREVIOUS document content (kept for your reference only - do NOT put it back into the working document) was:
--- PREVIOUS DOCUMENT START ---
${previousDoc}
--- PREVIOUS DOCUMENT END ---`
          : `

(Note: there was no previous document content - the working doc was empty.)`;
      const sourceDesc =
        source.kind === 'upload'
          ? `uploaded a new document titled "${source.label}"`
          : `loaded a saved draft titled "${source.label}" from storage`;
      const message = `(System: The user has just ${sourceDesc}. The working document has been REPLACED with the file shown below. Read it carefully, then acknowledge briefly that you've received it and give a 1-2 sentence summary of what is ACTUALLY in the file below. Do NOT guess or describe anything that is not in the text below. Do NOT restore the previous content. Then wait for the user's direction.

--- NEW DOCUMENT START ---
${text}
--- NEW DOCUMENT END ---${previousDocBlock})`;
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
    }

    addUnidexLog({
      kind: 'document',
      source: source.kind === 'upload' ? 'Upload' : 'Storage',
      title: source.kind === 'upload' ? 'Document uploaded' : 'Saved draft loaded',
      detail: `${source.label}\nSize: ${text.length.toLocaleString()} characters\nPrevious size: ${previousDoc.length.toLocaleString()} characters`,
    });

    addPerfLog({
      turn: turnCounterRef.current,
      event:
        source.kind === 'upload'
          ? 'User Action: Document Uploaded'
          : 'User Action: Saved Draft Loaded',
      details: { name: source.label, size: text.length, wasConnected: connected },
    });
  };

  const handleUploadDocument = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.txt,.md,.markdown,.html,.htm';
    input.onchange = async (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        applySwapDoc(text, { kind: 'upload', label: file.name });
      } catch (err) {
        console.error('Failed to read uploaded file:', err);
      }
    };
    input.click();
  };

  const pendingLoad = useStorageStore(s => s.pendingLoad);
  const clearPendingLoad = useStorageStore(s => s.clearPendingLoad);
  useEffect(() => {
    if (!pendingLoad) return;
    if (pendingLoad.format && pendingLoad.format !== user.format) {
      user.setFormat(pendingLoad.format);
    }
    if (pendingLoad.topic && pendingLoad.topic !== user.topic) {
      user.setTopic(pendingLoad.topic);
    }
    applySwapDoc(pendingLoad.content, { kind: 'storage', label: pendingLoad.name });
    clearPendingLoad();
  }, [pendingLoad]);

  return {
    applySwapDoc,
    handleUploadDocument,
  };
}
