/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { useMemo, useState } from 'react';
import { GoogleGenAI } from '@google/genai';
import { zipSync, strToU8 } from 'fflate';
import Modal from './Modal';
import { useUI, useUser, useSourceStore } from '../lib/state';
import { PLACEHOLDER_DOC } from '../lib/constants';

type ProfileId = 'note' | 'report' | 'memo' | 'script' | 'study-guide' | 'brief';

const PROFILES: { id: ProfileId; label: string; description: string }[] = [
  { id: 'note', label: 'Note', description: 'Concise, scannable, easy to recall later.' },
  { id: 'report', label: 'Report', description: 'Structured sections, findings, support, implications.' },
  { id: 'memo', label: 'Memo', description: 'Decision-ready context, recommendation, action items.' },
  { id: 'script', label: 'Script', description: 'Spoken flow, beats, transitions, clear voice.' },
  { id: 'study-guide', label: 'Study guide', description: 'Terms, explanations, examples, review questions.' },
  { id: 'brief', label: 'Brief', description: 'Short, current, source-aware, oriented around what matters now.' },
];

const FORMAT_OPTIONS: { id: 'md' | 'txt' | 'html'; label: string; ext: string }[] = [
  { id: 'md', label: 'Markdown (.md)', ext: 'md' },
  { id: 'txt', label: 'Plain text (.txt)', ext: 'txt' },
  { id: 'html', label: 'HTML (.html)', ext: 'html' },
];

const DEFAULT_PICKED: Record<ProfileId, boolean> = {
  note: true,
  report: false,
  memo: true,
  script: false,
  'study-guide': false,
  brief: true,
};

type ProfileStatus = 'idle' | 'running' | 'done' | 'error';

const slugify = (raw: string) =>
  (raw || 'scribe-document')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'scribe-document';

const buildProfilePrompt = (
  profile: ProfileId,
  doc: string,
  topic: string,
  activeSources: ReturnType<typeof useSourceStore.getState>['sources'],
) => {
  const profileMeta = PROFILES.find(p => p.id === profile)!;
  const sourceBlock = activeSources
    .filter(s => s.active)
    .slice(0, 8)
    .map(s => `### ${s.title} (${s.kind}) [id: ${s.id}]\n${s.content.slice(0, 1600)}`)
    .join('\n\n');
  return `You are Scribe's export packager.
Reshape the document below into the "${profileMeta.label}" output profile: ${profileMeta.description}

Topic: ${topic || 'Not specified'}

STRICT RULES:
- Return ONLY the reshaped Markdown document.
- No preamble, no commentary, no code fences.
- Keep facts grounded in the document and active sources. Do not invent information.
- Adapt structure, headings, and tone to the "${profileMeta.label}" profile — do not just copy the input.

Source document:
---
${doc}
---

Active sources:
---
${sourceBlock || '(no active sources)'}
---`;
};

export default function ExportPackageModal() {
  const { setShowExportPackageModal, apiKey, documentContent } = useUI();
  const user = useUser();
  const { sources } = useSourceStore();

  const [picked, setPicked] = useState<Record<ProfileId, boolean>>({ ...DEFAULT_PICKED });
  const [includeOriginal, setIncludeOriginal] = useState(true);
  const [format, setFormat] = useState<'md' | 'txt' | 'html'>('md');
  const [statuses, setStatuses] = useState<Record<ProfileId, ProfileStatus>>({
    note: 'idle', report: 'idle', memo: 'idle', script: 'idle', 'study-guide': 'idle', brief: 'idle',
  });
  const [errors, setErrors] = useState<Record<ProfileId, string | undefined>>({} as any);
  const [running, setRunning] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const docHasContent =
    documentContent && documentContent !== PLACEHOLDER_DOC && documentContent.trim().length > 0;
  const pickedCount = useMemo(
    () => Object.values(picked).filter(Boolean).length,
    [picked],
  );
  const canRun = docHasContent && apiKey && pickedCount > 0 && !running;

  const togglePick = (id: ProfileId) =>
    setPicked(prev => ({ ...prev, [id]: !prev[id] }));

  const handleGenerate = async () => {
    if (!canRun) return;
    setRunning(true);
    setFeedback(null);
    setErrors({} as any);
    setStatuses(prev => {
      const next = { ...prev };
      PROFILES.forEach(p => { next[p.id] = picked[p.id] ? 'running' : 'idle'; });
      return next;
    });

    const ai = new GoogleGenAI({ apiKey });
    const targets = PROFILES.filter(p => picked[p.id]);
    const fmt = FORMAT_OPTIONS.find(f => f.id === format)!;
    const slug = slugify(user.topic || 'scribe-document');

    const results = await Promise.all(targets.map(async target => {
      try {
        const response = await ai.models.generateContent({
          model: 'gemini-2.5-flash',
          contents: buildProfilePrompt(target.id, documentContent, user.topic || '', sources),
        });
        const text = response.text?.trim();
        if (!text) throw new Error('Empty response from model.');
        setStatuses(prev => ({ ...prev, [target.id]: 'done' }));
        return { id: target.id, ok: true as const, content: text };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setStatuses(prev => ({ ...prev, [target.id]: 'error' }));
        setErrors(prev => ({ ...prev, [target.id]: message }));
        return { id: target.id, ok: false as const, error: message };
      }
    }));

    const successful = results.filter(r => r.ok) as Extract<typeof results[number], { ok: true }>[];
    if (successful.length === 0) {
      setRunning(false);
      setFeedback('All profile generations failed. Check the per-profile errors.');
      return;
    }

    // Build the zip.
    const files: Record<string, Uint8Array> = {};
    successful.forEach(r => {
      const filename = `${slug}-${r.id}.${fmt.ext}`;
      files[filename] = strToU8(r.content);
    });
    if (includeOriginal) {
      files[`${slug}-original.${fmt.ext}`] = strToU8(documentContent);
    }
    // README listing what's inside.
    const manifest = [
      `# Scribe Export Package`,
      `Topic: ${user.topic || '(none)'}`,
      `Generated: ${new Date().toISOString()}`,
      `Format: ${fmt.label}`,
      ``,
      `## Files`,
      ...successful.map(r => `- ${slug}-${r.id}.${fmt.ext}  (${PROFILES.find(p => p.id === r.id)?.label})`),
      ...(includeOriginal ? [`- ${slug}-original.${fmt.ext}  (Original working document)`] : []),
    ].join('\n');
    files['README.md'] = strToU8(manifest);

    const zipped = zipSync(files);
    const blob = new Blob([zipped as BlobPart], { type: 'application/zip' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${slug}-package.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    const failedCount = results.length - successful.length;
    setFeedback(
      failedCount > 0
        ? `Downloaded package with ${successful.length} profile(s). ${failedCount} failed — see errors below.`
        : `Downloaded package with ${successful.length} profile(s).`,
    );
    setRunning(false);
  };

  const renderStatus = (id: ProfileId) => {
    const s = statuses[id];
    if (s === 'running') return <span className="export-status running">Generating…</span>;
    if (s === 'done') return <span className="export-status done">Done</span>;
    if (s === 'error') return <span className="export-status error">Failed</span>;
    return null;
  };

  return (
    <Modal onClose={() => setShowExportPackageModal(false)} className="export-package-modal-container">
      <div className="export-package-content">
        <h2>Export Package</h2>
        <p className="export-package-subtitle">
          Reshape the current document into multiple output profiles in one shot. Each selected profile is generated by Gemini in parallel and bundled into a single zip download.
        </p>

        {!docHasContent && (
          <div className="export-package-warning">
            The working document is empty — nothing to package.
          </div>
        )}
        {!apiKey && (
          <div className="export-package-warning">
            No Gemini API key set. Open Configuration to add one.
          </div>
        )}

        <div className="export-profile-list">
          {PROFILES.map(p => (
            <label key={p.id} className="export-profile-row">
              <input
                type="checkbox"
                checked={picked[p.id]}
                onChange={() => togglePick(p.id)}
                disabled={running}
              />
              <div className="export-profile-text">
                <div className="export-profile-label">{p.label}</div>
                <div className="export-profile-description">{p.description}</div>
                {errors[p.id] && (
                  <div className="export-profile-error">{errors[p.id]}</div>
                )}
              </div>
              {renderStatus(p.id)}
            </label>
          ))}
        </div>

        <div className="export-package-options">
          <label className="export-option-row">
            <input
              type="checkbox"
              checked={includeOriginal}
              onChange={() => setIncludeOriginal(v => !v)}
              disabled={running}
            />
            <span>Include the original working document</span>
          </label>
          <label className="export-option-row">
            <span>Format:</span>
            <select
              value={format}
              onChange={e => setFormat(e.target.value as 'md' | 'txt' | 'html')}
              disabled={running}
            >
              {FORMAT_OPTIONS.map(f => (
                <option key={f.id} value={f.id}>{f.label}</option>
              ))}
            </select>
          </label>
        </div>

        {feedback && <div className="export-package-feedback">{feedback}</div>}

        <div className="export-package-actions">
          <button
            className="export-package-generate"
            onClick={handleGenerate}
            disabled={!canRun}
            title={
              !docHasContent ? 'Document is empty' :
              !apiKey ? 'No API key' :
              pickedCount === 0 ? 'Select at least one profile' :
              running ? 'Generating…' : 'Generate and download'
            }
          >
            <span className="icon">inventory_2</span>
            {running ? `Generating ${pickedCount}…` : `Generate ${pickedCount} profile${pickedCount === 1 ? '' : 's'}`}
          </button>
        </div>
      </div>
    </Modal>
  );
}
