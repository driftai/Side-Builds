/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { create } from 'zustand';

export type SavedDoc = {
  id: string;
  name: string;
  content: string;
  format: 'Markdown' | 'HTML';
  topic?: string;
  createdAt: number;
  updatedAt: number;
};

const SAVED_DOCS_KEY = 'scribe_saved_docs';

const _loadSavedDocs = (): SavedDoc[] => {
  try {
    const raw = localStorage.getItem(SAVED_DOCS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed as SavedDoc[];
  } catch (e) {
    console.error('Failed to read saved docs from localStorage:', e);
  }
  return [];
};

const _writeSavedDocs = (docs: SavedDoc[]): boolean => {
  try {
    localStorage.setItem(SAVED_DOCS_KEY, JSON.stringify(docs));
    return true;
  } catch (e) {
    console.error('Failed to write saved docs to localStorage:', e);
    return false;
  }
};

export const useStorageStore = create<{
  savedDocs: SavedDoc[];
  pendingLoad: SavedDoc | null;
  saveDoc: (input: Omit<SavedDoc, 'id' | 'createdAt' | 'updatedAt'>) => SavedDoc | null;
  updateDoc: (id: string, patch: Partial<Omit<SavedDoc, 'id' | 'createdAt'>>) => void;
  deleteDoc: (id: string) => void;
  replaceSavedDocs: (docs: SavedDoc[]) => void;
  clearSavedDocs: () => void;
  requestLoad: (doc: SavedDoc) => void;
  clearPendingLoad: () => void;
}>(set => ({
  savedDocs: _loadSavedDocs(),
  pendingLoad: null,
  saveDoc: (input) => {
    const now = Date.now();
    const newDoc: SavedDoc = {
      ...input,
      id: `doc_${now}_${Math.random().toString(36).slice(2, 8)}`,
      createdAt: now,
      updatedAt: now,
    };
    let nextDocs: SavedDoc[] = [];
    set(state => {
      nextDocs = [newDoc, ...state.savedDocs];
      return { savedDocs: nextDocs };
    });
    if (!_writeSavedDocs(nextDocs)) return null;
    return newDoc;
  },
  updateDoc: (id, patch) => {
    set(state => {
      const next = state.savedDocs.map(d =>
        d.id === id ? { ...d, ...patch, updatedAt: Date.now() } : d
      );
      _writeSavedDocs(next);
      return { savedDocs: next };
    });
  },
  deleteDoc: (id) => {
    set(state => {
      const next = state.savedDocs.filter(d => d.id !== id);
      _writeSavedDocs(next);
      return { savedDocs: next };
    });
  },
  replaceSavedDocs: docs => {
    _writeSavedDocs(docs);
    set({ savedDocs: docs, pendingLoad: null });
  },
  clearSavedDocs: () => {
    _writeSavedDocs([]);
    set({ savedDocs: [], pendingLoad: null });
  },
  requestLoad: (doc) => set({ pendingLoad: doc }),
  clearPendingLoad: () => set({ pendingLoad: null }),
}));
