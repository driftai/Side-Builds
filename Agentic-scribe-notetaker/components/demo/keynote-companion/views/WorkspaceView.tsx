/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { diffWords } from 'diff';
import {
  useSourceStore,
  useUI,
  useVersionStore,
} from '../../../../lib/state';
import type { ScribeExportProfile, ScribeMode, ScribeSource } from '../../../../lib/state';
import { PLACEHOLDER_DOC } from '../../../../lib/constants';
import { ScribeCommandId } from '../hooks/useScribeCommands';
import { TranscriptEntry } from '../types';

type WorkspaceViewProps = {
  documentContent: string;
  transcript: TranscriptEntry[];
  onLoadVersion: (content: string) => void;
  onRunCommand: (command: ScribeCommandId, instruction: string) => Promise<void>;
  runningCommand: ScribeCommandId | null;
  commandLabel: Record<ScribeCommandId, string>;
};
type WorkspaceSection = 'commands' | 'sources' | 'versions';

const modeOptions: { value: ScribeMode; label: string }[] = [
  { value: 'general', label: 'General Scribe' },
  { value: 'research', label: 'Research Scribe' },
  { value: 'meeting', label: 'Meeting Scribe' },
  { value: 'creative', label: 'Creative Scribe' },
  { value: 'legal', label: 'Legal-style Drafting' },
  { value: 'academic', label: 'Academic Scribe' },
  { value: 'news', label: 'News Briefing' },
  { value: 'technical', label: 'Technical Docs' },
  { value: 'personal', label: 'Personal Knowledge' },
];

const profileOptions: { value: ScribeExportProfile; label: string }[] = [
  { value: 'note', label: 'Note' },
  { value: 'report', label: 'Report' },
  { value: 'memo', label: 'Memo' },
  { value: 'script', label: 'Script' },
  { value: 'study-guide', label: 'Study Guide' },
  { value: 'brief', label: 'Brief' },
];

const kindIcon = (kind: ScribeSource['kind']) => {
  switch (kind) {
    case 'search': return 'travel_explore';
    case 'pdf': return 'picture_as_pdf';
    case 'transcript': return 'record_voice_over';
    case 'version': return 'history';
    case 'storage': return 'folder_open';
    case 'upload': return 'upload_file';
    default: return 'description';
  }
};

const formatTime = (ms: number) =>
  new Date(ms).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

const normalizeCurrentDoc = (content: string) =>
  content && content !== PLACEHOLDER_DOC ? content : '';

export function WorkspaceView({
  documentContent,
  transcript,
  onLoadVersion,
  onRunCommand,
  runningCommand,
  commandLabel,
}: WorkspaceViewProps) {
  const {
    scribeMode,
    setScribeMode,
    documentGoal,
    setDocumentGoal,
    exportProfile,
    setExportProfile,
    workspaceInstruction,
    setWorkspaceInstruction,
    pendingSourceFocus,
    setPendingSourceFocus,
  } = useUI();
  const sourceRefs = useRef<Map<string, HTMLElement>>(new Map());
  const { sources, addSource, toggleSource, deleteSource, clearSources } = useSourceStore();
  const { versions, addVersion, deleteVersion, clearVersions } = useVersionStore();
  const [sourceFilter, setSourceFilter] = useState('');
  const [noteTitle, setNoteTitle] = useState('');
  const [noteContent, setNoteContent] = useState('');
  const [collapsed, setCollapsed] = useState<Record<WorkspaceSection, boolean>>({
    commands: false,
    sources: false,
    versions: false,
  });
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const currentDoc = normalizeCurrentDoc(documentContent);
  const activeSources = sources.filter(source => source.active);
  const selectedVersion = versions.find(version => version.id === selectedVersionId) || versions[0];

  // When a citation chip is clicked in the rendered view, useUI.pendingSourceFocus
  // is set. Scroll the matching source card into view, briefly highlight it, then
  // clear the pending focus. Also expand the Sources section if it's collapsed.
  useEffect(() => {
    if (!pendingSourceFocus) return;
    setCollapsed(prev => (prev.sources ? { ...prev, sources: false } : prev));
    const el = sourceRefs.current.get(pendingSourceFocus);
    if (el) {
      // Defer one frame so the card is in the DOM if the section just expanded.
      requestAnimationFrame(() => {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('source-focus-pulse');
      });
      const removePulse = setTimeout(() => el.classList.remove('source-focus-pulse'), 2200);
      const clearFocus = setTimeout(() => setPendingSourceFocus(null), 200);
      return () => {
        clearTimeout(removePulse);
        clearTimeout(clearFocus);
      };
    }
    // Source ID didn't match anything (deleted? model hallucinated?). Just clear.
    setPendingSourceFocus(null);
  }, [pendingSourceFocus, setPendingSourceFocus]);

  const filteredSources = useMemo(() => {
    const needle = sourceFilter.toLowerCase().trim();
    if (!needle) return sources;
    return sources.filter(source =>
      `${source.title} ${source.kind} ${source.tags.join(' ')} ${source.summary}`
        .toLowerCase()
        .includes(needle),
    );
  }, [sourceFilter, sources]);

  const diffParts = useMemo(() => {
    if (!selectedVersion) return [];
    return diffWords(selectedVersion.content, currentDoc);
  }, [currentDoc, selectedVersion]);

  const captureDocument = () => {
    addSource({
      kind: 'document',
      title: `Current document ${formatTime(Date.now())}`,
      content: currentDoc,
      tags: ['cold', 'document'],
      active: true,
    });
  };

  const captureTranscript = () => {
    const content = transcript.map(entry => `${entry.speaker}: ${entry.text}`).join('\n');
    addSource({
      kind: 'transcript',
      title: `Transcript ${formatTime(Date.now())}`,
      content,
      tags: ['cold', 'transcript'],
      active: true,
    });
  };

  const captureVersion = () => {
    const version = addVersion({
      title: `Manual snapshot ${formatTime(Date.now())}`,
      content: currentDoc,
      reason: 'Manual workspace snapshot',
    });
    addSource({
      id: `version_${version.id}`,
      kind: 'version',
      title: version.title,
      content: currentDoc,
      tags: ['cold', 'version'],
      active: false,
    });
  };

  const addNoteSource = () => {
    const content = noteContent.trim();
    if (!content) return;
    addSource({
      kind: 'note',
      title: noteTitle.trim() || `Pasted note ${formatTime(Date.now())}`,
      content,
      tags: ['cold', 'note'],
      active: true,
    });
    setNoteTitle('');
    setNoteContent('');
  };

  const clearAllVersions = () => {
    clearVersions();
    sources.filter(source => source.kind === 'version').forEach(source => deleteSource(source.id));
    setSelectedVersionId(null);
  };

  const run = async (command: ScribeCommandId) => {
    setError(null);
    try {
      await onRunCommand(command, workspaceInstruction);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const togglePanel = (panel: WorkspaceSection) =>
    setCollapsed(prev => ({ ...prev, [panel]: !prev[panel] }));

  return (
    <div className="workspace-view">
      <section className={`workspace-panel workspace-command-panel ${collapsed.commands ? 'collapsed' : ''}`}>
        <div className="workspace-section-header">
          <div>
            <h2>Scribe Command Engine</h2>
            <p>Universal document operations over the current draft and active sources.</p>
          </div>
          <div className="workspace-control-row">
            <select
              className="workspace-select"
              value={scribeMode}
              onChange={event => setScribeMode(event.target.value as ScribeMode)}
            >
              {modeOptions.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <select
              className="workspace-select"
              value={exportProfile}
              onChange={event => setExportProfile(event.target.value as ScribeExportProfile)}
            >
              {profileOptions.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          <button
            className="workspace-collapse-button"
            onClick={() => togglePanel('commands')}
            title={collapsed.commands ? 'Expand section' : 'Collapse section'}
          >
            <span className="icon">{collapsed.commands ? 'expand_more' : 'expand_less'}</span>
          </button>
        </div>
        <div className="workspace-panel-body">
          <textarea
            className="workspace-goal"
            value={documentGoal}
            onChange={event => setDocumentGoal(event.target.value)}
            placeholder="Document goal, audience, success criteria, or constraints..."
          />
          <textarea
            className="workspace-instruction"
            value={workspaceInstruction}
            onChange={event => setWorkspaceInstruction(event.target.value)}
            placeholder="Optional instruction, target section, tone, audience, or research query..."
          />
          <div className="workspace-command-grid">
            {(Object.keys(commandLabel) as ScribeCommandId[]).map(command => (
              <button
                key={command}
                className="workspace-action"
                disabled={Boolean(runningCommand)}
                onClick={() => run(command)}
              >
                <span className="icon">{command === 'research' ? 'travel_explore' : 'auto_fix_high'}</span>
                <span>{runningCommand === command ? 'Running...' : commandLabel[command]}</span>
              </button>
            ))}
          </div>
          {error && <div className="workspace-error">{error}</div>}
        </div>
      </section>

      <section className={`workspace-panel ${collapsed.sources ? 'collapsed' : ''}`}>
        <div className="workspace-section-header">
          <div>
            <h2>Source Cabinet</h2>
            <p>{activeSources.length} active of {sources.length} total sources.</p>
          </div>
          <div className="workspace-actions">
            <button onClick={captureDocument} disabled={!currentDoc}>Capture doc</button>
            <button onClick={captureTranscript} disabled={!transcript.length}>Capture transcript</button>
            <button onClick={clearSources} disabled={!sources.length}>Clear sources</button>
          </div>
          <button
            className="workspace-collapse-button"
            onClick={() => togglePanel('sources')}
            title={collapsed.sources ? 'Expand section' : 'Collapse section'}
          >
            <span className="icon">{collapsed.sources ? 'expand_more' : 'expand_less'}</span>
          </button>
        </div>
        <div className="workspace-panel-body">
          <input
            className="workspace-filter"
            value={sourceFilter}
            onChange={event => setSourceFilter(event.target.value)}
            placeholder="Filter sources..."
          />
          <div className="workspace-note-capture">
            <input
              value={noteTitle}
              onChange={event => setNoteTitle(event.target.value)}
              placeholder="Pasted note title..."
            />
            <textarea
              value={noteContent}
              onChange={event => setNoteContent(event.target.value)}
              placeholder="Paste text, notes, snippets, or source material..."
            />
            <button onClick={addNoteSource} disabled={!noteContent.trim()}>Add source note</button>
          </div>
          <div className="source-list">
            {filteredSources.length ? filteredSources.map(source => (
              <article
                key={source.id}
                className="source-card"
                ref={(el) => {
                  if (el) sourceRefs.current.set(source.id, el);
                  else sourceRefs.current.delete(source.id);
                }}
              >
                <button
                  className={`source-active-toggle ${source.active ? 'active' : ''}`}
                  onClick={() => toggleSource(source.id)}
                  title={source.active ? 'Active in context' : 'Inactive'}
                >
                  {source.active ? 'Active' : 'Inactive'}
                </button>
                <div className="source-card-main">
                  <div className="source-title-row">
                    <span className="icon">{kindIcon(source.kind)}</span>
                    <strong>{source.title}</strong>
                  </div>
                  <p>{source.summary || source.content.slice(0, 220)}</p>
                  <div className="source-meta">
                    <span>{source.kind}</span>
                    <span>ID: {source.id}</span>
                    <span>{formatTime(source.updatedAt)}</span>
                    <span>{source.content.length.toLocaleString()} chars</span>
                    {source.tags.map(tag => <span key={tag}>#{tag}</span>)}
                  </div>
                </div>
                <button className="source-delete" onClick={() => deleteSource(source.id)} title="Delete source">
                  <span className="icon">delete</span>
                </button>
              </article>
            )) : <div className="workspace-empty">No sources yet.</div>}
          </div>
        </div>
      </section>

      <section className={`workspace-panel ${collapsed.versions ? 'collapsed' : ''}`}>
        <div className="workspace-section-header">
          <div>
            <h2>Document Versions</h2>
            <p>Named snapshots and diff review against the current draft.</p>
          </div>
          <div className="workspace-actions">
            <button onClick={captureVersion} disabled={!currentDoc}>Save snapshot</button>
            <button onClick={clearAllVersions} disabled={!versions.length}>Clear versions</button>
          </div>
          <button
            className="workspace-collapse-button"
            onClick={() => togglePanel('versions')}
            title={collapsed.versions ? 'Expand section' : 'Collapse section'}
          >
            <span className="icon">{collapsed.versions ? 'expand_more' : 'expand_less'}</span>
          </button>
        </div>
        <div className="workspace-panel-body">
          <div className="version-layout">
            <div className="version-list">
              {versions.map(version => (
                <button
                  key={version.id}
                  className={`version-item ${selectedVersion?.id === version.id ? 'active' : ''}`}
                  onClick={() => setSelectedVersionId(version.id)}
                >
                  <strong>{version.title}</strong>
                  <span>{version.reason} - {formatTime(version.createdAt)}</span>
                </button>
              ))}
              {!versions.length && <div className="workspace-empty">No versions captured yet.</div>}
            </div>
            <div className="version-preview">
              {selectedVersion ? (
                <>
                  <div className="workspace-actions">
                    <button onClick={() => onLoadVersion(selectedVersion.content)}>Load version</button>
                    <button onClick={() => deleteVersion(selectedVersion.id)}>Delete</button>
                  </div>
                  <div className="version-diff">
                    {diffParts.map((part, index) => (
                      <span
                        key={index}
                        className={part.added ? 'diff-added' : part.removed ? 'diff-removed' : undefined}
                      >
                        {part.value}
                      </span>
                    ))}
                  </div>
                </>
              ) : <div className="workspace-empty">Select a version to compare.</div>}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
