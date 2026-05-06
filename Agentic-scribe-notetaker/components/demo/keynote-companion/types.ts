/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Defines the shape for an entry in the text-based conversation transcript.
export type TranscriptEntry = {
  speaker: string;
  text: string;
};

export type UnidexLogKind =
  | 'transcript'
  | 'tool'
  | 'document'
  | 'system'
  | 'shortcut'
  | 'error';

export type UnidexLogEntry = {
  id: number;
  timestamp: Date;
  kind: UnidexLogKind;
  source: string;
  title: string;
  detail?: string;
};

// Defines the shape for an entry in the audio log, storing the raw audio blob.
export type AudioLogEntry = {
  speaker: string;
  blob: Blob;
  timestamp: Date;
};
