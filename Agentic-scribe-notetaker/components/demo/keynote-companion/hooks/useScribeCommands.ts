/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { MutableRefObject, useCallback, useState } from 'react';
import type { GoogleGenAI } from '@google/genai';
import { PLACEHOLDER_DOC } from '../../../../lib/constants';
import type { ScribeExportProfile, ScribeSource } from '../../../../lib/state';
import type { UnidexLogEntry } from '../types';
import { cleanDocumentContent } from '../utils/documentCleanup';
import { formatGroundedSearchMarkdown, runGroundedGoogleSearch } from '../utils/groundedSearch';

export type ScribeCommandId =
  | 'research'
  | 'expand'
  | 'rewrite'
  | 'summarize'
  | 'compare'
  | 'contradictions'
  | 'outline'
  | 'final'
  | 'cite'
  | 'version';

export type DocumentSelection = {
  start: number;
  end: number;
  text: string;
};

// Commands that make sense scoped to a passage rather than the whole doc.
const SELECTION_COMMANDS: ReadonlySet<ScribeCommandId> = new Set([
  'rewrite',
  'expand',
  'summarize',
  'cite',
]);

export const isSelectionCommand = (id: ScribeCommandId) => SELECTION_COMMANDS.has(id);

type Args = {
  ai: MutableRefObject<GoogleGenAI | null>;
  documentContent: string;
  pushToHistory: (content: string) => void;
  setDocumentContent: (content: string | ((prev: string) => string)) => void;
  activeSources: ScribeSource[];
  addSource: (source: any) => void;
  addVersion: (version: { title: string; content: string; reason: string }) => { id: string; title: string };
  addUnidexLog: (entry: Omit<UnidexLogEntry, 'id' | 'timestamp'>) => void;
  topic?: string;
  userContext?: string;
  documentGoal?: string;
  exportProfile?: ScribeExportProfile;
  workspaceInstruction?: string;
};

const commandLabel: Record<ScribeCommandId, string> = {
  research: 'Research this',
  expand: 'Expand this',
  rewrite: 'Rewrite this',
  summarize: 'Summarize this',
  compare: 'Compare sources',
  contradictions: 'Find contradictions',
  outline: 'Make an outline',
  final: 'Turn into final draft',
  cite: 'Cite claims',
  version: 'Create next version',
};

const sourceContext = (sources: ScribeSource[]) =>
  sources
    .slice(0, 8)
    .map(source =>
      `### ${source.title} (${source.kind}) [id: ${source.id}]\n${source.content.slice(0, 1800)}`,
    )
    .join('\n\n');

// Strict instruction block injected into "cite" prompts. The model must emit
// citations as Markdown links pointing at #src:<id> so the renderer can turn
// them into clickable chips that jump to the source card.
const legacyCitationFormatInstructions = `
CITATION FORMAT — STRICT:
- Every cited claim must end with one or more Markdown link citations: [<source title>](#src:<source id>).
- Use ONLY the source IDs from the active sources block. Never invent IDs.
- Do not use footnotes, parentheticals, or "[Source: ...]" plain text — use Markdown links exclusively.
- A claim with multiple supporting sources gets multiple links separated by spaces.
- If no active source supports a claim, leave it uncited rather than fabricating one.`;

const citationFormatInstructions = [
  'CITATION FORMAT - STRICT:',
  '- Every cited claim must end with one or more Markdown link citations: [<source title>](#src:<source id>).',
  '- Use ONLY the source IDs from the active sources block. Never invent IDs.',
  '- Do not use footnotes, parentheticals, or "[Source: ...]" plain text. Use Markdown links exclusively.',
  '- A claim with multiple supporting sources gets multiple links separated by spaces.',
  '- If no active source supports a claim, leave it uncited rather than fabricating one.',
].join('\n');

export function useScribeCommands({
  ai,
  documentContent,
  pushToHistory,
  setDocumentContent,
  activeSources,
  addSource,
  addVersion,
  addUnidexLog,
  topic,
  userContext,
  documentGoal,
  exportProfile = 'note',
  workspaceInstruction,
}: Args) {
  const [runningCommand, setRunningCommand] = useState<ScribeCommandId | null>(null);

  const runCommand = useCallback(async (
    command: ScribeCommandId,
    instruction = '',
    selection: DocumentSelection | null = null,
  ) => {
    const currentDoc = documentContent === PLACEHOLDER_DOC ? '' : documentContent;

    // Selection-scoped path: rewrite ONLY the selected passage and splice the
    // result back into the document at the original offsets. Keeps the rest
    // of the document untouched and avoids the model drifting on full rewrites.
    if (selection && isSelectionCommand(command) && selection.text.trim()) {
      if (command === 'cite' && !activeSources.length) {
        addUnidexLog({
          kind: 'error',
          source: 'Command Engine',
          title: 'Citations need active sources',
          detail: 'Activate at least one Source Cabinet item before running Cite on a passage.',
        });
        throw new Error('Cite needs at least one active Source Cabinet item.');
      }
      if (!ai.current) throw new Error('Scribe commands need a Gemini API key.');
      // Validate offsets — the doc may have been edited since selection was captured.
      const liveSlice = documentContent.slice(selection.start, selection.end);
      if (liveSlice !== selection.text) {
        addUnidexLog({
          kind: 'error',
          source: 'Command Engine',
          title: 'Selection no longer matches document',
          detail: 'The selected passage changed before the command ran. Re-select and try again.',
        });
        throw new Error('Selection no longer matches the document. Re-select and try again.');
      }

      setRunningCommand(command);
      const mergedInstruction = instruction || workspaceInstruction || '';
      addUnidexLog({
        kind: 'tool',
        source: 'Command Engine',
        title: `${commandLabel[command]} (passage)`,
        detail: `${selection.text.length.toLocaleString()} chars selected. ${
          mergedInstruction || 'No extra instruction provided.'
        }`,
      });

      try {
        const passagePrompt = `You are Scribe's selection command engine.
Command: ${commandLabel[command]}
Extra instruction: ${mergedInstruction || 'None'}
Topic: ${topic || 'Not specified'}
Document goal: ${documentGoal?.trim() || 'No explicit goal set'}
Output profile: ${exportProfile}

The user has selected ONE passage from a larger document. Apply the command to this passage ONLY.

STRICT RULES:
- Return ONLY the rewritten passage as plain Markdown text.
- Do NOT return the full document.
- Do NOT wrap your answer in code fences or quotes.
- Do NOT add commentary, headings, or framing unless the original passage already had them.
- Preserve the passage's heading level, list nesting, and surrounding tone.
${command === 'cite' ? citationFormatInstructions : ''}

Selected passage:
---
${selection.text}
---

Active sources:
---
${sourceContext(activeSources) || '(no active sources)'}
---`;

        const response = await ai.current.models.generateContent({
          model: 'gemini-2.5-flash',
          contents: passagePrompt,
        });
        const { content: rewritten } = cleanDocumentContent(response.text?.trim() || '');
        if (!rewritten) throw new Error('Selection command returned no text.');

        addVersion({
          title: `Before ${commandLabel[command]} (passage)`,
          content: documentContent,
          reason: 'Pre-selection-command snapshot',
        });
        pushToHistory(documentContent);
        const next =
          documentContent.slice(0, selection.start) +
          rewritten +
          documentContent.slice(selection.end);
        setDocumentContent(next);
        addUnidexLog({
          kind: 'document',
          source: 'Command Engine',
          title: 'Passage transformed',
          detail: `${commandLabel[command]} replaced ${selection.text.length.toLocaleString()} chars with ${rewritten.length.toLocaleString()} chars.`,
        });
      } finally {
        setRunningCommand(null);
      }
      return;
    }

    if (command === 'version') {
      const version = addVersion({
        title: instruction.trim() || `Version ${new Date().toLocaleString()}`,
        content: currentDoc,
        reason: 'Manual version snapshot',
      });
      addSource({
        id: `version_${version.id}`,
        kind: 'version',
        title: version.title,
        content: currentDoc,
        tags: ['cold', 'version'],
        active: false,
      });
      addUnidexLog({
        kind: 'document',
        source: 'Command Engine',
        title: 'Version created',
        detail: `${currentDoc.length.toLocaleString()} characters captured.`,
      });
      return;
    }
    if (command === 'cite' && !activeSources.length) {
      addUnidexLog({
        kind: 'error',
        source: 'Command Engine',
        title: 'Citations need active sources',
        detail: 'Activate at least one Source Cabinet item before running Cite claims.',
      });
      throw new Error('Cite claims needs at least one active Source Cabinet item.');
    }
    if (!ai.current) throw new Error('Scribe commands need a Gemini API key.');

    setRunningCommand(command);
    const mergedInstruction = instruction || workspaceInstruction || '';
    addUnidexLog({
      kind: 'tool',
      source: 'Command Engine',
      title: commandLabel[command],
      detail: mergedInstruction || 'No extra instruction provided.',
    });

    try {
      if (command === 'research') {
        const query = mergedInstruction || topic || currentDoc.slice(0, 500) || 'research this document';
        const result = await runGroundedGoogleSearch(ai.current, {
          documentContent: currentDoc,
          query,
          topic,
          userContext,
        });
        const markdown = formatGroundedSearchMarkdown(result);
        pushToHistory(documentContent);
        setDocumentContent(prev => {
          const base = prev && prev !== PLACEHOLDER_DOC ? `${prev.trimEnd()}\n\n` : '';
          return `${base}${markdown}`;
        });
        addSource({
          kind: 'search',
          title: `Search: ${query.slice(0, 80)}`,
          content: markdown,
          tags: ['hot', 'search'],
          active: true,
          meta: { model: result.model, sources: result.sources.length },
        });
        addUnidexLog({
          kind: 'tool',
          source: 'Google Search',
          title: 'Command research complete',
          detail: `Returned ${result.sources.length} source-backed result(s) using ${result.model}. Queries: ${
            result.queries.slice(0, 3).join('; ') || query
          }.`,
        });
        return;
      }

      const prompt = `You are Scribe's document command engine.
Command: ${commandLabel[command]}
Extra instruction: ${mergedInstruction || 'None'}
Topic: ${topic || 'Not specified'}
Document goal: ${documentGoal?.trim() || 'No explicit goal set'}
Output profile: ${exportProfile}

Current document:
---
${currentDoc || '(empty)'}
---

Active sources:
---
${sourceContext(activeSources) || '(no active sources)'}
---

Return only the complete updated Markdown document. Keep factual claims grounded in the active sources or current document. If the command is comparison or contradictions, create a clear section with findings.${command === 'cite' ? `\n\n${citationFormatInstructions}` : ''}`;

      const response = await ai.current.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: prompt,
      });
      const { content: text, removedConversationalBlocks } =
        cleanDocumentContent(response.text?.trim() || '');
      if (!text) throw new Error('Command returned no document text.');

      addVersion({
        title: `Before ${commandLabel[command]}`,
        content: currentDoc,
        reason: 'Pre-command snapshot',
      });
      pushToHistory(documentContent);
      setDocumentContent(text);
      addUnidexLog({
        kind: 'document',
        source: 'Command Engine',
        title: 'Document transformed',
        detail: `${commandLabel[command]} produced ${text.length.toLocaleString()} characters.${
          removedConversationalBlocks ? ` Removed ${removedConversationalBlocks} conversational block(s).` : ''
        }`,
      });
    } finally {
      setRunningCommand(null);
    }
  }, [
    activeSources,
    addSource,
    addUnidexLog,
    addVersion,
    ai,
    documentContent,
    documentGoal,
    exportProfile,
    pushToHistory,
    setDocumentContent,
    topic,
    userContext,
    workspaceInstruction,
  ]);

  return { commandLabel, runCommand, runningCommand };
}
