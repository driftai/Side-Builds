/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { create } from 'zustand';

export type SourceKind =
  | 'document'
  | 'pdf'
  | 'upload'
  | 'storage'
  | 'search'
  | 'transcript'
  | 'note'
  | 'version';

export type ScribeSource = {
  id: string;
  kind: SourceKind;
  title: string;
  content: string;
  summary?: string;
  tags: string[];
  active: boolean;
  createdAt: number;
  updatedAt: number;
  meta?: Record<string, string | number | boolean>;
};

const SOURCES_KEY = 'scribe_sources';

const readSources = (): ScribeSource[] => {
  try {
    const raw = localStorage.getItem(SOURCES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const writeSources = (sources: ScribeSource[]) => {
  try {
    localStorage.setItem(SOURCES_KEY, JSON.stringify(sources));
  } catch (error) {
    console.error('Failed to persist source cabinet:', error);
  }
};

const summarize = (content: string) =>
  content.replace(/\s+/g, ' ').trim().slice(0, 240);

export const useSourceStore = create<{
  sources: ScribeSource[];
  addSource: (
    input: Omit<ScribeSource, 'id' | 'createdAt' | 'updatedAt' | 'summary'> &
      { id?: string; summary?: string },
  ) => ScribeSource;
  upsertSource: (
    id: string,
    input: Partial<Omit<ScribeSource, 'id' | 'createdAt' | 'updatedAt'>>,
  ) => void;
  updateSource: (id: string, patch: Partial<Omit<ScribeSource, 'id' | 'createdAt'>>) => void;
  toggleSource: (id: string) => void;
  deleteSource: (id: string) => void;
  replaceSources: (sources: ScribeSource[]) => void;
  clearSources: () => void;
}>(set => ({
  sources: readSources(),
  addSource: input => {
    const now = Date.now();
    const source: ScribeSource = {
      ...input,
      id: input.id || `src_${now}_${Math.random().toString(36).slice(2, 8)}`,
      summary: input.summary || summarize(input.content),
      createdAt: now,
      updatedAt: now,
    };
    set(state => {
      const next = [source, ...state.sources.filter(item => item.id !== source.id)];
      writeSources(next);
      return { sources: next };
    });
    return source;
  },
  upsertSource: (id, input) => {
    set(state => {
      const existing = state.sources.find(source => source.id === id);
      const now = Date.now();
      const nextSource: ScribeSource = existing
        ? {
            ...existing,
            ...input,
            summary: input.summary || existing.summary || summarize(input.content || existing.content),
            updatedAt: now,
          }
        : {
            id,
            kind: input.kind || 'note',
            title: input.title || 'Untitled source',
            content: input.content || '',
            summary: input.summary || summarize(input.content || ''),
            tags: input.tags || [],
            active: input.active ?? false,
            meta: input.meta,
            createdAt: now,
            updatedAt: now,
          };
      const next = [nextSource, ...state.sources.filter(source => source.id !== id)];
      writeSources(next);
      return { sources: next };
    });
  },
  updateSource: (id, patch) => {
    set(state => {
      const next = state.sources.map(source =>
        source.id === id
          ? {
              ...source,
              ...patch,
              summary: patch.summary || source.summary,
              updatedAt: Date.now(),
            }
          : source,
      );
      writeSources(next);
      return { sources: next };
    });
  },
  toggleSource: id => {
    set(state => {
      const next = state.sources.map(source =>
        source.id === id ? { ...source, active: !source.active, updatedAt: Date.now() } : source,
      );
      writeSources(next);
      return { sources: next };
    });
  },
  deleteSource: id => {
    set(state => {
      const next = state.sources.filter(source => source.id !== id);
      writeSources(next);
      return { sources: next };
    });
  },
  replaceSources: sources => {
    writeSources(sources);
    set({ sources });
  },
  clearSources: () => {
    writeSources([]);
    set({ sources: [] });
  },
}));
