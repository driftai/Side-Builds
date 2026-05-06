/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { create } from 'zustand';

export type LogEntry = {
  timestamp: Date;
  endTimestamp?: Date;
  turn?: number;
  api: string;
  inputSize: number | string;
  outputSize: number | string;
  status: 'success' | 'error';
  error?: string;
  prompt?: string;
  response?: string;
  audioSize?: number;
  audioBlob?: Blob;
  promptVersion?: number;
};

const MAX_LOG_ENTRIES = 50;

export const useLogStore = create<{
  logs: LogEntry[];
  suppressedLogs: LogEntry[];
  suppressedAudioCount: number;
  addLog: (log: Omit<LogEntry, 'timestamp'> & { timestamp?: Date }) => void;
  addSuppressedLog: (log: Omit<LogEntry, 'timestamp'> & { timestamp?: Date }) => void;
  incrementSuppressedAudioCount: () => void;
}>(set => ({
  logs: [],
  suppressedLogs: [],
  suppressedAudioCount: 0,
  addLog: log => {
    set(state => {
      const { timestamp, ...rest } = log;
      const newLog: LogEntry = { ...rest, timestamp: timestamp || new Date() };
      const updatedLogs = [newLog, ...state.logs];
      if (updatedLogs.length > MAX_LOG_ENTRIES) {
        updatedLogs.pop();
      }
      updatedLogs.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
      return { logs: updatedLogs };
    });
  },
  addSuppressedLog: log => {
    set(state => {
      const { timestamp, ...rest } = log;
      const newLog: LogEntry = { ...rest, timestamp: timestamp || new Date() };
      const updatedLogs = [newLog, ...state.suppressedLogs];
      if (updatedLogs.length > MAX_LOG_ENTRIES) {
        updatedLogs.pop();
      }
      updatedLogs.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
      return { suppressedLogs: updatedLogs };
    });
  },
  incrementSuppressedAudioCount: () =>
    set(state => ({ suppressedAudioCount: state.suppressedAudioCount + 1 })),
}));

export type PerfLogEntry = {
  timestamp: number;
  perfTimestamp: number;
  sessionId: string;
  turn: number;
  event: string;
  delta?: number;
  details?: any;
};

const MAX_PERF_LOG_ENTRIES = 200;

export const usePerfLogStore = create<{
  logs: PerfLogEntry[];
  sessionId: string | null;
  startNewSession: () => void;
  addLog: (log: Omit<PerfLogEntry, 'timestamp' | 'perfTimestamp' | 'delta' | 'sessionId'>) => void;
  clearLogs: () => void;
}>(set => ({
  logs: [],
  sessionId: null,
  startNewSession: () => set({ sessionId: `session_${Date.now()}` }),
  addLog: log => {
    set(state => {
      const nowPerf = performance.now();
      const nowReal = Date.now();
      const lastLogThisSession = state.logs.find(l => l.sessionId === state.sessionId);
      const delta = lastLogThisSession ? nowPerf - lastLogThisSession.perfTimestamp : undefined;

      const newLog: PerfLogEntry = {
        ...log,
        timestamp: nowReal,
        perfTimestamp: nowPerf,
        delta,
        sessionId: state.sessionId || 'session_unknown',
      };
      const updatedLogs = [newLog, ...state.logs];
      if (updatedLogs.length > MAX_PERF_LOG_ENTRIES) {
        updatedLogs.pop();
      }
      return { logs: updatedLogs };
    });
  },
  clearLogs: () => set({ logs: [], sessionId: null }),
}));
