/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import {
  useSourceStore,
  useStorageStore,
  useVersionStore,
  useWorkspaceRestoreStore,
} from '../../../../../lib/state';

const commandIds = new Set([
  'research',
  'expand',
  'rewrite',
  'summarize',
  'compare',
  'contradictions',
  'outline',
  'final',
  'cite',
  'version',
]);

const commandAliases: Record<string, string> = {
  'research this': 'research',
  'expand this': 'expand',
  'rewrite this': 'rewrite',
  'summarize this': 'summarize',
  'compare sources': 'compare',
  'find contradictions': 'contradictions',
  'make an outline': 'outline',
  'turn into final draft': 'final',
  'cite claims': 'cite',
  'create next version': 'version',
};

export const normalizeCommandId = (value: unknown) => {
  const text = typeof value === 'string' ? value.toLowerCase().trim() : '';
  if (!text) return '';
  if (commandIds.has(text)) return text;
  const alias = commandAliases[text.replace(/["']/g, '')];
  if (alias) return alias;
  if (text.includes('research')) return 'research';
  if (text.includes('expand')) return 'expand';
  if (text.includes('rewrite')) return 'rewrite';
  if (text.includes('summar')) return 'summarize';
  if (text.includes('compare')) return 'compare';
  if (text.includes('contradiction')) return 'contradictions';
  if (text.includes('outline')) return 'outline';
  if (text.includes('final')) return 'final';
  if (text.includes('cite') || text.includes('citation')) return 'cite';
  if (text.includes('version') || text.includes('snapshot')) return 'version';
  return '';
};

export const looksLikeCommandButtonRequest = (text: string) =>
  /\b(queued?|button|press|click|run|play)\b/i.test(text) && Boolean(normalizeCommandId(text));

const clearVersionSources = () => {
  const sourceStore = useSourceStore.getState();
  sourceStore.sources
    .filter(source => source.kind === 'version')
    .forEach(source => sourceStore.deleteSource(source.id));
};

const hasClearTarget = (args: Record<string, unknown>) =>
  ['all', 'sources', 'versions', 'savedDocs', 'document', 'transcript', 'unidexLog', 'workspaceSettings']
    .some(key => args[key] === true);

const shouldHandle = (all: boolean, args: Record<string, unknown>, key: string) =>
  all || args[key] === true;

export async function runWorkspaceCommandFromTool(ctx: any, args: Record<string, unknown>) {
  ctx.setAgentState('Running Workspace Command');
  const command = normalizeCommandId(args.command);
  const instruction = typeof args.instruction === 'string' ? args.instruction : '';

  if (!command) return { status: 'ERROR', message: 'Unknown Workspace command.' };
  if (!ctx.runWorkspaceCommand) {
    return { status: 'ERROR', message: 'Workspace command runner is unavailable.' };
  }

  try {
    await ctx.runWorkspaceCommand(command, instruction);
    ctx.addUnidexLog?.({
      kind: 'tool',
      source: 'Workspace',
      title: 'Workspace command executed',
      detail: `Ran ${command}${instruction ? ` with instruction: ${instruction}` : ''}.`,
    });
    return { status: 'OK', command };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    ctx.addUnidexLog?.({
      kind: 'tool',
      source: 'Workspace',
      title: 'Workspace command failed',
      detail: message,
    });
    return { status: 'ERROR', message };
  }
}

export function clearWorkspaceDataFromTool(ctx: any, args: Record<string, unknown>) {
  ctx.setAgentState('Clearing Workspace');
  const clearAll = args.all === true;
  const changed: string[] = [];
  const snapshot: Record<string, any> = {};
  const sourceStore = useSourceStore.getState();
  const versionStore = useVersionStore.getState();
  const storageStore = useStorageStore.getState();

  if (shouldHandle(clearAll, args, 'sources')) snapshot.sources = sourceStore.sources;
  if (shouldHandle(clearAll, args, 'versions')) {
    snapshot.versions = versionStore.versions;
    snapshot.versionSources = sourceStore.sources.filter(source => source.kind === 'version');
  }
  if (shouldHandle(clearAll, args, 'savedDocs')) snapshot.savedDocs = storageStore.savedDocs;
  if (shouldHandle(clearAll, args, 'workspaceSettings')) {
    snapshot.workspaceSettings = {
      documentGoal: ctx.documentGoal || '',
      exportProfile: ctx.exportProfile || 'note',
      scribeMode: ctx.scribeMode || 'general',
      workspaceInstruction: ctx.workspaceInstruction || '',
    };
  }

  const runtimeSnapshot = ctx.clearWorkspaceRuntime?.({
    document: shouldHandle(clearAll, args, 'document'),
    transcript: shouldHandle(clearAll, args, 'transcript'),
    unidexLog: shouldHandle(clearAll, args, 'unidexLog'),
  });
  Object.assign(snapshot, runtimeSnapshot);

  if (shouldHandle(clearAll, args, 'sources')) {
    sourceStore.clearSources();
    changed.push('source cabinet');
  }
  if (shouldHandle(clearAll, args, 'versions')) {
    versionStore.clearVersions();
    if (!clearAll && args.sources !== true) clearVersionSources();
    changed.push('document versions');
  }
  if (shouldHandle(clearAll, args, 'savedDocs')) {
    storageStore.clearSavedDocs();
    changed.push('saved documents');
  }
  if (shouldHandle(clearAll, args, 'document')) changed.push('current document');
  if (shouldHandle(clearAll, args, 'transcript')) changed.push('transcript');
  if (shouldHandle(clearAll, args, 'unidexLog')) changed.push('Unidex Log');
  if (shouldHandle(clearAll, args, 'workspaceSettings')) {
    ctx.setDocumentGoal?.('');
    ctx.setWorkspaceInstruction?.('');
    ctx.setScribeMode?.('general');
    ctx.setExportProfile?.('note');
    changed.push('workspace settings');
  }

  if (changed.length) useWorkspaceRestoreStore.getState().addSnapshot(snapshot);

  if (!clearAll && args.unidexLog !== true) {
    ctx.addUnidexLog?.({
      kind: 'tool',
      source: 'Workspace',
      title: 'Workspace data cleared',
      detail: changed.length ? changed.join(', ') : 'No workspace data type was selected.',
    });
  }
  return changed.length
    ? { status: 'OK', cleared: changed, apiKeyPreserved: true }
    : { status: 'ERROR', message: 'No workspace data type was selected to clear.' };
}

export function restoreWorkspaceDataFromTool(ctx: any, args: Record<string, unknown>) {
  ctx.setAgentState('Restoring Workspace');
  const restoreAll = args.all === true || !hasClearTarget(args);
  const restoreStore = useWorkspaceRestoreStore.getState();
  const restored: string[] = [];
  const restoreRuntime: Record<string, any> = {};

  if (shouldHandle(restoreAll, args, 'sources')) {
    const snapshot = restoreStore.latestFor('sources');
    if (snapshot?.sources) {
      useSourceStore.getState().replaceSources(snapshot.sources);
      restored.push('source cabinet');
    }
  }
  if (shouldHandle(restoreAll, args, 'versions')) {
    const snapshot = restoreStore.latestFor('versions');
    if (snapshot?.versions) {
      useVersionStore.getState().replaceVersions(snapshot.versions);
      const sourceStore = useSourceStore.getState();
      const current = sourceStore.sources.filter(source => source.kind !== 'version');
      sourceStore.replaceSources([...(snapshot.versionSources || []), ...current]);
      restored.push('document versions');
    }
  }
  if (shouldHandle(restoreAll, args, 'savedDocs')) {
    const snapshot = restoreStore.latestFor('savedDocs');
    if (snapshot?.savedDocs) {
      useStorageStore.getState().replaceSavedDocs(snapshot.savedDocs);
      restored.push('saved documents');
    }
  }
  if (shouldHandle(restoreAll, args, 'document')) {
    const snapshot = restoreStore.latestFor('document');
    if (snapshot?.document !== undefined) {
      restoreRuntime.document = snapshot.document;
      restored.push('current document');
    }
  }
  if (shouldHandle(restoreAll, args, 'transcript')) {
    const snapshot = restoreStore.latestFor('transcript');
    if (snapshot?.transcript) {
      restoreRuntime.transcript = snapshot.transcript;
      restored.push('transcript');
    }
  }
  if (shouldHandle(restoreAll, args, 'unidexLog')) {
    const snapshot = restoreStore.latestFor('unidexLog');
    if (snapshot?.unidexLog) {
      restoreRuntime.unidexLog = snapshot.unidexLog;
      restored.push('Unidex Log');
    }
  }
  if (Object.keys(restoreRuntime).length) ctx.restoreWorkspaceRuntime?.(restoreRuntime);
  if (shouldHandle(restoreAll, args, 'workspaceSettings')) {
    const snapshot = restoreStore.latestFor('workspaceSettings');
    if (snapshot?.workspaceSettings) {
      ctx.setDocumentGoal?.(snapshot.workspaceSettings.documentGoal);
      ctx.setWorkspaceInstruction?.(snapshot.workspaceSettings.workspaceInstruction);
      ctx.setScribeMode?.(snapshot.workspaceSettings.scribeMode);
      ctx.setExportProfile?.(snapshot.workspaceSettings.exportProfile);
      restored.push('workspace settings');
    }
  }

  ctx.addUnidexLog?.({
    kind: 'tool',
    source: 'Workspace',
    title: 'Workspace data restored',
    detail: restored.length ? restored.join(', ') : 'No session restore point was available.',
  });
  return restored.length
    ? { status: 'OK', restored, sessionOnly: true, apiKeyPreserved: true }
    : { status: 'ERROR', message: 'No session restore point is available for the requested data.' };
}
