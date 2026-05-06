/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { useMemo, useState } from 'react';
import Modal from './Modal';
import { useSourceStore, useUI, useUser, useStorageStore, SavedDoc } from '../lib/state';
import { PLACEHOLDER_DOC } from '../lib/constants';

const formatTimestamp = (ms: number) => {
  const d = new Date(ms);
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export default function StorageModal() {
  const { setShowStorageModal } = useUI();
  const user = useUser();
  const { documentContent } = useUI();
  const { savedDocs, saveDoc, updateDoc, deleteDoc, requestLoad } = useStorageStore();
  const { addSource } = useSourceStore();

  const [saveName, setSaveName] = useState(user.topic || '');
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const [feedback, setFeedback] = useState<string | null>(null);

  const docHasContent =
    documentContent && documentContent !== PLACEHOLDER_DOC && documentContent.trim().length > 0;

  // Newest first.
  const sortedDocs = useMemo(
    () => [...savedDocs].sort((a, b) => b.updatedAt - a.updatedAt),
    [savedDocs],
  );

  const handleSaveCurrent = () => {
    if (!docHasContent) {
      setFeedback('Nothing to save — the document is empty.');
      return;
    }
    const name = saveName.trim() || 'Untitled draft';
    const result = saveDoc({
      name,
      content: documentContent,
      format: user.format,
      topic: user.topic,
    });
    if (!result) {
      setFeedback('Save failed — localStorage may be full.');
      return;
    }
    addSource({
      id: `saved_${result.id}`,
      kind: 'storage',
      title: name,
      content: documentContent,
      tags: ['cold', 'saved-draft'],
      active: false,
    });
    setFeedback(`Saved as "${name}".`);
    setSaveName('');
  };

  const handleLoad = (doc: SavedDoc) => {
    requestLoad(doc);
    setShowStorageModal(false);
  };

  const beginRename = (doc: SavedDoc) => {
    setRenamingId(doc.id);
    setRenameDraft(doc.name);
  };

  const commitRename = () => {
    if (!renamingId) return;
    const name = renameDraft.trim();
    if (name) updateDoc(renamingId, { name });
    setRenamingId(null);
    setRenameDraft('');
  };

  const handleDelete = (doc: SavedDoc) => {
    if (confirm(`Delete "${doc.name}"? This cannot be undone.`)) {
      deleteDoc(doc.id);
    }
  };

  return (
    <Modal onClose={() => setShowStorageModal(false)} className="storage-modal-container">
      <div className="storage-modal-content">
        <h2>Saved Documents</h2>
        <p className="storage-modal-subtitle">
          Drafts are stored in this browser only. They are not synced to any account.
        </p>

        <div className="storage-save-row">
          <input
            type="text"
            className="storage-save-input"
            placeholder="Name this draft (defaults to your topic)"
            value={saveName}
            onChange={e => setSaveName(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') handleSaveCurrent();
            }}
          />
          <button
            className="storage-save-button"
            onClick={handleSaveCurrent}
            disabled={!docHasContent}
            title={
              docHasContent
                ? 'Save the current working document'
                : 'The document is empty — nothing to save'
            }
          >
            <span className="icon">save</span>
            Save current
          </button>
        </div>

        {feedback && <div className="storage-feedback">{feedback}</div>}

        <div className="storage-list">
          {sortedDocs.length === 0 ? (
            <div className="storage-empty">
              No saved drafts yet. Save the current document above to get started.
            </div>
          ) : (
            sortedDocs.map(doc => (
              <div className="storage-item" key={doc.id}>
                <div className="storage-item-main">
                  {renamingId === doc.id ? (
                    <input
                      type="text"
                      className="storage-rename-input"
                      value={renameDraft}
                      autoFocus
                      onChange={e => setRenameDraft(e.target.value)}
                      onBlur={commitRename}
                      onKeyDown={e => {
                        if (e.key === 'Enter') commitRename();
                        else if (e.key === 'Escape') {
                          setRenamingId(null);
                          setRenameDraft('');
                        }
                      }}
                    />
                  ) : (
                    <button
                      className="storage-item-name"
                      onClick={() => handleLoad(doc)}
                      title="Load this document into the editor"
                    >
                      {doc.name}
                    </button>
                  )}
                  <div className="storage-item-meta">
                    <span>{doc.format}</span>
                    <span>·</span>
                    <span>{formatTimestamp(doc.updatedAt)}</span>
                    <span>·</span>
                    <span>{doc.content.length.toLocaleString()} chars</span>
                  </div>
                </div>
                <div className="storage-item-actions">
                  <button
                    className="storage-action"
                    onClick={() => handleLoad(doc)}
                    title="Load into editor"
                  >
                    <span className="icon">file_open</span>
                  </button>
                  <button
                    className="storage-action"
                    onClick={() => beginRename(doc)}
                    title="Rename"
                  >
                    <span className="icon">edit</span>
                  </button>
                  <button
                    className="storage-action storage-action-danger"
                    onClick={() => handleDelete(doc)}
                    title="Delete"
                  >
                    <span className="icon">delete</span>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </Modal>
  );
}
