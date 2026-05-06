/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React from 'react';
import { marked } from 'marked';
import { sanitizeHtml } from '../../../../lib/safe-html';
import { MinutesLoadingAnimation } from '../../../MinutesLoadingAnimation';

export type MinutesTabViewProps = {
  minutesViewRef: React.RefObject<HTMLDivElement>;
  handleDownloadPDF: (
    ref: React.RefObject<HTMLDivElement>,
    defaultFilename: string,
  ) => void;
  topic?: string;
  pdfStatus: 'idle' | 'preparing' | 'generating';
  handleCopyToClipboard: (content: string) => void;
  correctedTranscript: string;
  isCorrectingTranscript: boolean;
};

export function MinutesTabView({
  minutesViewRef,
  handleDownloadPDF,
  topic,
  pdfStatus,
  handleCopyToClipboard,
  correctedTranscript,
  isCorrectingTranscript,
}: MinutesTabViewProps) {
  return (
    <div className="document-editor-container">
      <div className="document-actions exclude-from-pdf">
        <button
          className="pdf-button"
          onClick={() => handleDownloadPDF(minutesViewRef, `${topic || 'scribe'}_minutes`)}
          disabled={pdfStatus !== 'idle'}
          title="Download PDF"
        >
          <span className="icon">picture_as_pdf</span>
        </button>
        <button
          className="copy-button"
          onClick={() => handleCopyToClipboard(correctedTranscript)}
          title="Copy to clipboard"
        >
          <span className="icon">content_copy</span>
        </button>
      </div>
      <div ref={minutesViewRef} className="document-content prose-view">
        {isCorrectingTranscript ? (
          <MinutesLoadingAnimation />
        ) : (
          <div
            dangerouslySetInnerHTML={{
              __html: sanitizeHtml(
                marked.parse(correctedTranscript, { breaks: true }) as string,
              ),
            }}
          />
        )}
      </div>
    </div>
  );
}
