/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { create } from 'zustand';

export type PdfFile = {
  name: string;
  text: string;
};

export type User = {
  name?: string;
  info?: string;
  topic?: string;
  format: 'Markdown' | 'HTML';
  pdfFiles: PdfFile[];
};

export const useUser = create<
  {
    setName: (name: string) => void;
    setInfo: (info: string) => void;
    setTopic: (topic: string) => void;
    setFormat: (format: 'Markdown' | 'HTML') => void;
    addPdfFile: (file: PdfFile) => void;
    removePdfFile: (name: string) => void;
    clearPdfFiles: () => void;
  } & User
>(set => ({
  name: '',
  info: '',
  topic: '',
  format: 'Markdown',
  pdfFiles: [],
  setName: name => set({ name }),
  setInfo: info => set({ info }),
  setTopic: topic => set({ topic }),
  setFormat: format => set({ format }),
  addPdfFile: file => set(state => ({ pdfFiles: [...state.pdfFiles, file] })),
  removePdfFile: name => set(state => ({ pdfFiles: state.pdfFiles.filter(f => f.name !== name) })),
  clearPdfFiles: () => set({ pdfFiles: [] }),
}));
