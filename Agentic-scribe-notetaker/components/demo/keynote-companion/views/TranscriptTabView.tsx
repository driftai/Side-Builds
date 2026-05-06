/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { marked } from 'marked';
import { sanitizeHtml } from '../../../../lib/safe-html';
import { MinutesLoadingAnimation } from '../../../MinutesLoadingAnimation';
import { TranscriptEntry } from '../types';

export type TranscriptTabViewProps = {
  handleGetAccurateTranscript: () => void;
  isGeneratingAccurateTranscript: boolean;
  audioLogLength: number;
  accurateTranscript: string;
  handleCopyToClipboard: (content: string) => void;
  handleReplaceTranscript: () => void;
  setAccurateTranscript: (content: string) => void;
  transcript: TranscriptEntry[];
};

export function TranscriptTabView({
  handleGetAccurateTranscript,
  isGeneratingAccurateTranscript,
  audioLogLength,
  accurateTranscript,
  handleCopyToClipboard,
  handleReplaceTranscript,
  setAccurateTranscript,
  transcript,
}: TranscriptTabViewProps) {
  return (
    <div className="transcript-content">
      <div className="document-actions exclude-from-pdf mb-4">
        <button
          className="pdf-button flex items-center gap-2"
          onClick={handleGetAccurateTranscript}
          disabled={isGeneratingAccurateTranscript || audioLogLength === 0}
          title="Generate a more accurate transcript from audio"
        >
          <span className="icon">auto_fix_high</span>
          <span>{isGeneratingAccurateTranscript ? 'Analyzing Audio...' : 'Accurate Transcript'}</span>
        </button>
        {accurateTranscript && (
          <button
            className="copy-button"
            onClick={() => handleCopyToClipboard(accurateTranscript)}
            title="Copy accurate transcript"
          >
            <span className="icon">content_copy</span>
          </button>
        )}
      </div>

      {isGeneratingAccurateTranscript ? (
        <MinutesLoadingAnimation />
      ) : accurateTranscript ? (
        <div className="accurate-transcript-view prose-view">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-black/5">
            <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Accurate Version</h4>
            <button
              className="flex items-center gap-2 px-3 py-1.5 bg-blue-500 text-white text-xs font-medium rounded-lg hover:bg-blue-600 transition-colors shadow-sm"
              onClick={handleReplaceTranscript}
            >
              <span className="icon text-sm">swap_horiz</span>
              Replace Live Transcript
            </button>
          </div>
          <div
            className="accurate-content-body"
            dangerouslySetInnerHTML={{
              __html: sanitizeHtml(marked.parse(accurateTranscript) as string),
            }}
          />
          <button
            className="text-xs text-blue-500 mt-8 hover:underline flex items-center gap-1"
            onClick={() => setAccurateTranscript('')}
          >
            <span className="icon text-sm">arrow_back</span>
            Back to live transcript
          </button>
        </div>
      ) : transcript.length > 0 ? (
        transcript.map((entry, index) => (
          <p key={index} className="transcript-entry">
            <strong>{entry.speaker}:</strong> {entry.text}
          </p>
        ))
      ) : (
        <div className="flex flex-col items-center justify-center h-full text-gray-400 opacity-50">
          <span className="icon text-4xl mb-2">forum</span>
          <p>No transcript available yet.</p>
        </div>
      )}
    </div>
  );
}
