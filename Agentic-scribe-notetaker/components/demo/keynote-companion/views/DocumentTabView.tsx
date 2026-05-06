/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React, { ChangeEvent, SyntheticEvent, useRef } from 'react';
import c from 'classnames';
import { FONT_OPTIONS, PLACEHOLDER_DOC } from '../../../../lib/constants';
import { Insert } from '../../../../lib/state';
import { DocumentRenderer } from '../components/DocumentRenderer';
import { WelcomePlaceholder } from '../components/WelcomePlaceholder';
import type { DocumentSelection, ScribeCommandId } from '../hooks/useScribeCommands';

const SELECTION_TOOLBAR_COMMANDS: { id: ScribeCommandId; label: string; icon: string }[] = [
  { id: 'rewrite', label: 'Rewrite', icon: 'edit_note' },
  { id: 'expand', label: 'Expand', icon: 'unfold_more' },
  { id: 'summarize', label: 'Summarize', icon: 'compress' },
  { id: 'cite', label: 'Cite', icon: 'format_quote' },
];

type DownloadTarget = 'editor' | 'rendered' | null;

export type DocumentTabViewProps = {
  documentTab: 'editor' | 'rendered';
  isMobile: boolean;
  showMobileToolbar: boolean;
  setShowMobileToolbar: (show: boolean) => void;
  documentHistoryLength: number;
  redoHistoryLength: number;
  handleUndo: () => void;
  handleRedo: () => void;
  handleClear: () => void;
  handleStartConversation: () => void;
  handleEnableSearchShortcut: () => void;
  handlePdfContextShortcut: () => void;
  handleInsertGraphShortcut: () => void;
  handleInsertIllustrationShortcut: () => void;
  handleEditDocumentShortcut: () => void;
  handleUploadDocument: () => void;
  openStorage: () => void;
  handleDownloadAs: (ext: 'md' | 'txt' | 'html') => void;
  documentContent: string;
  font: string;
  setFont: (font: string) => void;
  downloadMenuOpen: DownloadTarget;
  setDownloadMenuOpen: (target: DownloadTarget) => void;
  handleDocumentChange: (e: ChangeEvent<HTMLTextAreaElement>) => void;
  renderedViewRef: React.RefObject<HTMLDivElement>;
  pdfStatus: 'idle' | 'preparing' | 'generating';
  handleDownloadPDF: (
    ref: React.RefObject<HTMLDivElement>,
    defaultFilename: string,
  ) => void;
  topic?: string;
  handleCopyToClipboard: (content: string) => void;
  handleRenderedContentMouseDown: (e: React.MouseEvent<HTMLDivElement>) => void;
  inserts: Insert[];
  imageGenerationEnabled: boolean;
  handleElementResize: (id: string, newWidth: string) => void;
  selection: DocumentSelection | null;
  setSelection: (sel: DocumentSelection | null) => void;
  onRunCommandOnSelection: (command: ScribeCommandId) => void;
  runningCommand: ScribeCommandId | null;
  onCitationClick: (sourceId: string) => void;
  openExportPackage: () => void;
};

export function DocumentTabView({
  documentTab,
  isMobile,
  showMobileToolbar,
  setShowMobileToolbar,
  documentHistoryLength,
  redoHistoryLength,
  handleUndo,
  handleRedo,
  handleClear,
  handleStartConversation,
  handleEnableSearchShortcut,
  handlePdfContextShortcut,
  handleInsertGraphShortcut,
  handleInsertIllustrationShortcut,
  handleEditDocumentShortcut,
  handleUploadDocument,
  openStorage,
  handleDownloadAs,
  documentContent,
  font,
  setFont,
  downloadMenuOpen,
  setDownloadMenuOpen,
  handleDocumentChange,
  renderedViewRef,
  pdfStatus,
  handleDownloadPDF,
  topic,
  handleCopyToClipboard,
  handleRenderedContentMouseDown,
  inserts,
  imageGenerationEnabled,
  handleElementResize,
  selection,
  setSelection,
  onRunCommandOnSelection,
  runningCommand,
  onCitationClick,
  openExportPackage,
}: DocumentTabViewProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleRenderedClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = (e.target as HTMLElement).closest<HTMLElement>('.citation-chip');
    if (target?.dataset.sourceId) {
      e.preventDefault();
      onCitationClick(target.dataset.sourceId);
    }
  };

  const captureSelection = (e: SyntheticEvent<HTMLTextAreaElement>) => {
    const el = e.currentTarget;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    if (start !== end) {
      setSelection({ start, end, text: el.value.slice(start, end) });
    } else if (selection) {
      setSelection(null);
    }
  };

  return (
    <div className="document-editor-container">
      {documentTab === 'editor' && (
        <>
          <div className="document-toolbar">
            {isMobile ? (
              <div className="mobile-toolbar-container">
                <span style={{ fontWeight: 500, opacity: 0.7 }}>Actions</span>
                <button
                  className="mobile-menu-trigger"
                  onClick={() => setShowMobileToolbar(!showMobileToolbar)}
                  title="Document Actions"
                >
                  <span className="material-symbols-outlined">more_vert</span>
                </button>
                {showMobileToolbar && (
                  <>
                    <div className="mobile-menu-overlay" onClick={() => setShowMobileToolbar(false)} />
                    <div className="mobile-menu-dropdown">
                      <button onClick={() => { handleUndo(); setShowMobileToolbar(false); }} disabled={documentHistoryLength === 0}>
                        <span className="material-symbols-outlined">undo</span> Undo
                      </button>
                      <button onClick={() => { handleRedo(); setShowMobileToolbar(false); }} disabled={redoHistoryLength === 0}>
                        <span className="material-symbols-outlined">redo</span> Redo
                      </button>
                      <button onClick={() => { handleClear(); setShowMobileToolbar(false); }}>
                        <span className="material-symbols-outlined">delete</span> Clear
                      </button>
                      <button onClick={() => { handleUploadDocument(); setShowMobileToolbar(false); }}>
                        <span className="material-symbols-outlined">upload_file</span> Upload
                      </button>
                      <button onClick={() => { openStorage(); setShowMobileToolbar(false); }}>
                        <span className="material-symbols-outlined">folder_open</span> Storage
                      </button>
                      <button
                        onClick={() => { handleDownloadAs('md'); setShowMobileToolbar(false); }}
                        disabled={!documentContent || documentContent === PLACEHOLDER_DOC}
                      >
                        <span className="material-symbols-outlined">download</span> Download .md
                      </button>
                      <button
                        onClick={() => { handleDownloadAs('txt'); setShowMobileToolbar(false); }}
                        disabled={!documentContent || documentContent === PLACEHOLDER_DOC}
                      >
                        <span className="material-symbols-outlined">download</span> Download .txt
                      </button>
                      <button
                        onClick={() => { handleDownloadAs('html'); setShowMobileToolbar(false); }}
                        disabled={!documentContent || documentContent === PLACEHOLDER_DOC}
                      >
                        <span className="material-symbols-outlined">download</span> Download .html
                      </button>
                      <button
                        onClick={() => { openExportPackage(); setShowMobileToolbar(false); }}
                        disabled={!documentContent || documentContent === PLACEHOLDER_DOC}
                      >
                        <span className="material-symbols-outlined">inventory_2</span> Export package…
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <>
                <button onClick={handleUndo} disabled={documentHistoryLength === 0}>Undo</button>
                <button onClick={handleRedo} disabled={redoHistoryLength === 0}>Redo</button>
                <button onClick={handleClear}>Clear</button>
                <button onClick={handleUploadDocument} title="Upload .txt / .md / .html as the new document">
                  Upload
                </button>
                <button onClick={openStorage} title="Open saved drafts">
                  Storage
                </button>
                <div className="download-button-wrapper">
                  <button
                    onClick={() => setDownloadMenuOpen(downloadMenuOpen === 'editor' ? null : 'editor')}
                    disabled={!documentContent || documentContent === PLACEHOLDER_DOC}
                    title="Download document"
                  >
                    Download ▾
                  </button>
                  {downloadMenuOpen === 'editor' && (
                    <>
                      <div className="download-menu-overlay" onClick={() => setDownloadMenuOpen(null)} />
                      <div className="download-menu">
                        <button onClick={() => handleDownloadAs('md')}>Markdown (.md)</button>
                        <button onClick={() => handleDownloadAs('txt')}>Plain text (.txt)</button>
                        <button onClick={() => handleDownloadAs('html')}>HTML (.html)</button>
                        <div className="download-menu-divider" />
                        <button onClick={openExportPackage}>
                          <span className="icon" style={{ verticalAlign: 'bottom' }}>inventory_2</span> Export package…
                        </button>
                      </div>
                    </>
                  )}
                </div>
                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
                  <select
                    className="font-selector"
                    value={font}
                    onChange={e => setFont(e.target.value)}
                    title="Select document font"
                  >
                    {FONT_OPTIONS.map(fontName => (
                      <option key={fontName} value={fontName}>
                        {fontName}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}
          </div>
          {selection && selection.text.trim().length > 0 && (
            <div className="selection-toolbar">
              <span className="selection-toolbar-label">
                <span className="icon">format_ink_highlighter</span>
                Selected: {selection.text.length.toLocaleString()} chars
              </span>
              <div className="selection-toolbar-actions">
                {SELECTION_TOOLBAR_COMMANDS.map(cmd => (
                  <button
                    key={cmd.id}
                    type="button"
                    className="selection-toolbar-button"
                    onClick={() => onRunCommandOnSelection(cmd.id)}
                    disabled={runningCommand !== null}
                    title={`${cmd.label} the selected passage`}
                  >
                    <span className="icon">{cmd.icon}</span>
                    {runningCommand === cmd.id ? `${cmd.label}…` : cmd.label}
                  </button>
                ))}
                <button
                  type="button"
                  className="selection-toolbar-close"
                  onClick={() => setSelection(null)}
                  title="Dismiss selection toolbar"
                >
                  <span className="icon">close</span>
                </button>
              </div>
            </div>
          )}
          <textarea
            ref={textareaRef}
            className="document-textarea"
            value={documentContent}
            onChange={handleDocumentChange}
            onSelect={captureSelection}
            onMouseUp={captureSelection}
            onKeyUp={captureSelection}
            placeholder="Start writing..."
          />
        </>
      )}

      {documentTab === 'rendered' && (
        <>
          <div className="document-actions exclude-from-pdf">
            <button className="upload-button" onClick={handleUploadDocument} title="Upload .txt / .md / .html as the new document">
              <span className="icon">upload_file</span>
            </button>
            <button className="upload-button" onClick={openStorage} title="Open saved drafts">
              <span className="icon">folder_open</span>
            </button>
            {documentContent !== PLACEHOLDER_DOC && (
              <>
                <div className="download-button-wrapper">
                  <button
                    className="download-button"
                    onClick={() => setDownloadMenuOpen(downloadMenuOpen === 'rendered' ? null : 'rendered')}
                    title="Download document"
                  >
                    <span className="icon">download</span>
                  </button>
                  {downloadMenuOpen === 'rendered' && (
                    <>
                      <div className="download-menu-overlay" onClick={() => setDownloadMenuOpen(null)} />
                      <div className="download-menu">
                        <button onClick={() => handleDownloadAs('md')}>Markdown (.md)</button>
                        <button onClick={() => handleDownloadAs('txt')}>Plain text (.txt)</button>
                        <button onClick={() => handleDownloadAs('html')}>HTML (.html)</button>
                        <div className="download-menu-divider" />
                        <button onClick={openExportPackage}>
                          <span className="icon" style={{ verticalAlign: 'bottom' }}>inventory_2</span> Export package…
                        </button>
                      </div>
                    </>
                  )}
                </div>
                <button
                  className="pdf-button"
                  onClick={() => handleDownloadPDF(renderedViewRef, topic || 'scribe-document')}
                  disabled={pdfStatus !== 'idle'}
                  title="Download PDF"
                >
                  <span className="icon">picture_as_pdf</span>
                </button>
                <button
                  className="copy-button"
                  onClick={() => handleCopyToClipboard(documentContent)}
                  title="Copy to clipboard"
                >
                  <span className="icon">content_copy</span>
                </button>
              </>
            )}
          </div>
          <div
            ref={renderedViewRef}
            className={c('document-content prose-view', {
              'placeholder-active': documentContent === PLACEHOLDER_DOC,
            })}
            onMouseDown={handleRenderedContentMouseDown}
            onClick={handleRenderedClick}
          >
            {documentContent === PLACEHOLDER_DOC ? (
              <WelcomePlaceholder
                onStartConversation={handleStartConversation}
                onEnableSearch={handleEnableSearchShortcut}
                onPdfContext={handlePdfContextShortcut}
                onInsertGraph={handleInsertGraphShortcut}
                onInsertIllustration={
                  imageGenerationEnabled ? handleInsertIllustrationShortcut : undefined
                }
                onEditDocument={handleEditDocumentShortcut}
                onUpload={handleUploadDocument}
                onOpenStorage={openStorage}
              />
            ) : (
              <DocumentRenderer
                content={documentContent}
                inserts={inserts}
                imageGenerationEnabled={imageGenerationEnabled}
                onElementResize={handleElementResize}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}
