/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { create } from 'zustand';

export interface Insert {
  id: string;
  type: 'image';
  prompt: string;
  status: 'loading' | 'done' | 'error';
  data?: string | null;
  mimeType?: string;
  error?: string;
  attempts?: { model: string; error: string }[];
}

export const useInsertStore = create<{
  inserts: Insert[];
  addInsert: (insert: Insert) => void;
  updateInsert: (id: string, updates: Partial<Insert>) => void;
  clearInserts: () => void;
}>(set => ({
  inserts: [],
  addInsert: (insert: Insert) =>
    set(state => ({ inserts: [...state.inserts, insert] })),
  updateInsert: (id: string, updates: Partial<Insert>) =>
    set(state => ({
      inserts: state.inserts.map(insert =>
        insert.id === id ? { ...insert, ...updates } : insert
      ),
    })),
  clearInserts: () => set({ inserts: [] }),
}));
