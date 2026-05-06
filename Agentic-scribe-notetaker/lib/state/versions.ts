/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { create } from 'zustand';

export type DocumentVersion = {
  id: string;
  title: string;
  content: string;
  reason: string;
  createdAt: number;
};

const VERSIONS_KEY = 'scribe_document_versions';

const readVersions = (): DocumentVersion[] => {
  try {
    const raw = localStorage.getItem(VERSIONS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const writeVersions = (versions: DocumentVersion[]) => {
  try {
    localStorage.setItem(VERSIONS_KEY, JSON.stringify(versions.slice(0, 80)));
  } catch (error) {
    console.error('Failed to persist document versions:', error);
  }
};

export const useVersionStore = create<{
  versions: DocumentVersion[];
  addVersion: (input: Omit<DocumentVersion, 'id' | 'createdAt'>) => DocumentVersion;
  renameVersion: (id: string, title: string) => void;
  deleteVersion: (id: string) => void;
  replaceVersions: (versions: DocumentVersion[]) => void;
  clearVersions: () => void;
}>(set => ({
  versions: readVersions(),
  addVersion: input => {
    const version: DocumentVersion = {
      ...input,
      id: `ver_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      createdAt: Date.now(),
    };
    set(state => {
      const next = [version, ...state.versions].slice(0, 80);
      writeVersions(next);
      return { versions: next };
    });
    return version;
  },
  renameVersion: (id, title) => {
    set(state => {
      const next = state.versions.map(version =>
        version.id === id ? { ...version, title } : version,
      );
      writeVersions(next);
      return { versions: next };
    });
  },
  deleteVersion: id => {
    set(state => {
      const next = state.versions.filter(version => version.id !== id);
      writeVersions(next);
      return { versions: next };
    });
  },
  replaceVersions: versions => {
    const next = versions.slice(0, 80);
    writeVersions(next);
    set({ versions: next });
  },
  clearVersions: () => {
    writeVersions([]);
    set({ versions: [] });
  },
}));
