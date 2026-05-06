/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { MutableRefObject, useCallback } from 'react';
import { PLACEHOLDER_DOC } from '../../../../lib/constants';
import type { TranscriptEntry, UnidexLogEntry } from '../types';

type Args = {
  documentContentRef: MutableRefObject<string>;
  docContentBeforeEditRef: MutableRefObject<string>;
  transcriptRef: MutableRefObject<TranscriptEntry[]>;
  unidexLogRef: MutableRefObject<UnidexLogEntry[]>;
  setAccurateTranscript: (value: string) => void;
  setCorrectedTranscript: (value: string) => void;
  setDocumentContent: (content: string) => void;
  setDocumentHistory: (value: string[]) => void;
  setRedoHistory: (value: string[]) => void;
  setTranscript: (value: TranscriptEntry[]) => void;
  setUnidexLog: (value: UnidexLogEntry[]) => void;
};

export function useWorkspaceRuntimeRestore({
  documentContentRef,
  docContentBeforeEditRef,
  transcriptRef,
  unidexLogRef,
  setAccurateTranscript,
  setCorrectedTranscript,
  setDocumentContent,
  setDocumentHistory,
  setRedoHistory,
  setTranscript,
  setUnidexLog,
}: Args) {
  const clearWorkspaceRuntime = useCallback((options: any = {}) => {
    const snapshot: any = {};
    if (options.document) {
      snapshot.document = documentContentRef.current;
      setDocumentContent(PLACEHOLDER_DOC);
      documentContentRef.current = PLACEHOLDER_DOC;
      docContentBeforeEditRef.current = PLACEHOLDER_DOC;
      setDocumentHistory([]);
      setRedoHistory([]);
    }
    if (options.transcript) {
      snapshot.transcript = transcriptRef.current;
      setTranscript([]);
      setCorrectedTranscript('');
      setAccurateTranscript('');
    }
    if (options.unidexLog) {
      snapshot.unidexLog = unidexLogRef.current;
      setUnidexLog([]);
    }
    return snapshot;
  }, [
    docContentBeforeEditRef,
    documentContentRef,
    setAccurateTranscript,
    setCorrectedTranscript,
    setDocumentContent,
    setDocumentHistory,
    setRedoHistory,
    setTranscript,
    setUnidexLog,
    transcriptRef,
    unidexLogRef,
  ]);

  const restoreWorkspaceRuntime = useCallback((snapshot: any = {}) => {
    if (snapshot.document !== undefined) {
      setDocumentContent(snapshot.document || PLACEHOLDER_DOC);
      documentContentRef.current = snapshot.document || PLACEHOLDER_DOC;
      docContentBeforeEditRef.current = snapshot.document || PLACEHOLDER_DOC;
    }
    if (snapshot.transcript) setTranscript(snapshot.transcript);
    if (snapshot.unidexLog) setUnidexLog(snapshot.unidexLog);
  }, [
    docContentBeforeEditRef,
    documentContentRef,
    setDocumentContent,
    setTranscript,
    setUnidexLog,
  ]);

  return { clearWorkspaceRuntime, restoreWorkspaceRuntime };
}
