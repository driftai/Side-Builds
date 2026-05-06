/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * The placeholder component shown when the document is empty.
 * It introduces the key features of the application.
 */
export const WelcomePlaceholder = ({
  onStartConversation,
  onEnableSearch,
  onPdfContext,
  onInsertGraph,
  onInsertIllustration,
  onEditDocument,
  onUpload,
  onOpenStorage,
}: {
  onStartConversation?: () => void;
  onEnableSearch?: () => void;
  onPdfContext?: () => void;
  onInsertGraph?: () => void;
  onInsertIllustration?: () => void;
  onEditDocument?: () => void;
  onUpload?: () => void;
  onOpenStorage?: () => void;
}) => {
  const shortcuts = [
    {
      icon: 'graphic_eq',
      title: 'Conversational Writing',
      description: 'Talk, and the scribe drafts your document in real-time.',
      onClick: onStartConversation,
    },
    {
      icon: 'search',
      title: 'Google Search',
      description: 'Real-time web access for research and fact-checking.',
      onClick: onEnableSearch,
    },
    {
      icon: 'picture_as_pdf',
      title: 'PDF Context',
      description: 'Upload documents to provide deep background information.',
      onClick: onPdfContext,
    },
    {
      icon: 'show_chart',
      title: 'Interactive Graphs',
      description: 'Plot mathematical functions with zoom and pan support.',
      onClick: onInsertGraph,
    },
    ...(onInsertIllustration ? [{
      icon: 'palette',
      title: 'Visual Illustrations',
      description: 'Ask for images and diagrams to visualize your ideas.',
      onClick: onInsertIllustration,
    }] : []),
    {
      icon: 'edit_document',
      title: "You're in Control",
      description: 'Directly edit the document at any time to guide the process.',
      onClick: onEditDocument,
    },
    ...(onUpload ? [{
      icon: 'upload_file',
      title: 'Upload Existing Document',
      description: 'Import a text, Markdown, HTML, or PDF file as the current draft.',
      onClick: onUpload,
    }] : []),
    ...(onOpenStorage ? [{
      icon: 'folder_open',
      title: 'Open From Storage',
      description: 'Resume a saved draft from local storage.',
      onClick: onOpenStorage,
    }] : []),
  ];

  return (
    <div className="welcome-placeholder">
      <h1 className="welcome-placeholder-title">
        <span className="welcome-prefix">Welcome to </span>Scribe
      </h1>
      <p className="welcome-placeholder-subtitle">
        Pick a shortcut to start, or press the{' '}
        <span className="icon">play_arrow</span>
        button below to begin a live session.
      </p>
      <div className="placeholder-features-grid">
        {shortcuts.map(shortcut => (
          <button
            key={shortcut.title}
            type="button"
            className="placeholder-feature placeholder-feature-action"
            onClick={shortcut.onClick}
          >
            <span className="icon">{shortcut.icon}</span>
            <span className="placeholder-feature-copy">
              <span className="placeholder-feature-title">{shortcut.title}</span>
              <span className="feature-desc">{shortcut.description}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
};
