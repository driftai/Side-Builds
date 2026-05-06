/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { create } from 'zustand';
import type { ScribeExportProfile, ScribeMode } from './ui';
import type { ScribeSource } from './sources';
import type { DocumentVersion } from './versions';
import type { SavedDoc } from './storage';

export type WorkspaceSettingsSnapshot = {
  documentGoal: string;
  exportProfile: ScribeExportProfile;
  scribeMode: ScribeMode;
  workspaceInstruction: string;
};

export type WorkspaceRestoreSnapshot = {
  id: string;
  createdAt: number;
  document?: string;
  savedDocs?: SavedDoc[];
  sources?: ScribeSource[];
  transcript?: any[];
  unidexLog?: any[];
  versions?: DocumentVersion[];
  versionSources?: ScribeSource[];
  workspaceSettings?: WorkspaceSettingsSnapshot;
};

type WorkspaceRestoreCategory = keyof Omit<WorkspaceRestoreSnapshot, 'createdAt' | 'id'>;

export const useWorkspaceRestoreStore = create<{
  snapshots: WorkspaceRestoreSnapshot[];
  addSnapshot: (snapshot: Omit<WorkspaceRestoreSnapshot, 'createdAt' | 'id'>) => WorkspaceRestoreSnapshot;
  latestFor: (category: WorkspaceRestoreCategory) => WorkspaceRestoreSnapshot | null;
  clearSnapshots: () => void;
}>(set => ({
  snapshots: [],
  addSnapshot: snapshot => {
    const nextSnapshot: WorkspaceRestoreSnapshot = {
      ...snapshot,
      id: `clear_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      createdAt: Date.now(),
    };
    set(state => ({ snapshots: [nextSnapshot, ...state.snapshots].slice(0, 12) }));
    return nextSnapshot;
  },
  latestFor: category => {
    const state = useWorkspaceRestoreStore.getState();
    return state.snapshots.find(snapshot => snapshot[category] !== undefined) || null;
  },
  clearSnapshots: () => set({ snapshots: [] }),
}));
