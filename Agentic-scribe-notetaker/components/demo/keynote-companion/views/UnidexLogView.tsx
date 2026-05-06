/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { UnidexLogEntry } from '../types';

export type UnidexLogViewProps = {
  entries: UnidexLogEntry[];
  onClear: () => void;
};

const getKindIcon = (kind: UnidexLogEntry['kind']) => {
  switch (kind) {
    case 'transcript': return 'record_voice_over';
    case 'tool': return 'travel_explore';
    case 'document': return 'edit_document';
    case 'system': return 'settings';
    case 'shortcut': return 'bolt';
    case 'error': return 'warning';
    default: return 'notes';
  }
};

const getTimeLabel = (timestamp: Date) =>
  timestamp.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

export function UnidexLogView({ entries, onClear }: UnidexLogViewProps) {
  return (
    <div className="transcript-content">
      <div className="document-actions exclude-from-pdf mb-4">
        <button
          className="copy-button"
          onClick={onClear}
          disabled={entries.length === 0}
          title="Clear Unidex Log"
        >
          <span className="icon">delete_sweep</span>
        </button>
      </div>

      {entries.length > 0 ? (
        entries.map(entry => (
          <div key={entry.id} className="transcript-entry">
            <strong>
              <span className="icon" style={{ fontSize: '1rem', verticalAlign: 'text-bottom' }}>
                {getKindIcon(entry.kind)}
              </span>{' '}
              {entry.source}
            </strong>
            <span style={{ opacity: 0.55 }}> · {getTimeLabel(entry.timestamp)}</span>
            <div style={{ fontWeight: 600 }}>{entry.title}</div>
            {entry.detail && <div style={{ whiteSpace: 'pre-wrap' }}>{entry.detail}</div>}
          </div>
        ))
      ) : (
        <div className="flex flex-col items-center justify-center h-full text-gray-400 opacity-50">
          <span className="icon text-4xl mb-2">list_alt</span>
          <p>No Unidex Log entries yet.</p>
        </div>
      )}
    </div>
  );
}
