/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
type Store = Record<string, string>;

const store: Store = {
  scribe_api_key: 'keep-this-key',
  scribe_sources: JSON.stringify([
    {
      id: 'src_one',
      kind: 'note',
      title: 'Source',
      content: 'source content',
      summary: 'source content',
      tags: ['cold'],
      active: true,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    },
  ]),
  scribe_document_versions: JSON.stringify([
    {
      id: 'ver_one',
      title: 'Version',
      content: '# Version',
      reason: 'smoke',
      createdAt: Date.now(),
    },
  ]),
  scribe_saved_docs: JSON.stringify([
    {
      id: 'doc_one',
      name: 'Saved',
      content: '# Saved',
      format: 'Markdown',
      createdAt: Date.now(),
      updatedAt: Date.now(),
    },
  ]),
};

(globalThis as any).localStorage = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => {
    store[key] = String(value);
  },
  removeItem: (key: string) => {
    delete store[key];
  },
  clear: () => {
    Object.keys(store).forEach(key => delete store[key]);
  },
};

const { createToolCallHandler } = await import('../components/demo/keynote-companion/hooks/live/toolCalls');
const { useSourceStore, useStorageStore, useVersionStore, useWorkspaceRestoreStore } =
  await import('../lib/state');

const commands: Array<{ command: string; instruction: string }> = [];
const runtimeClears: any[] = [];
const runtimeRestores: any[] = [];
const setInstructions: string[] = [];
const responses: any[] = [];
const runtime = {
  document: '# Current',
  transcript: [{ speaker: 'User', text: 'hello' }],
  unidexLog: [{ id: 1, kind: 'tool', source: 'Smoke', title: 'Entry', detail: 'entry', timestamp: new Date() }],
};
let documentGoal = 'goal';
let exportProfile = 'brief';
let scribeMode = 'research';
let workspaceInstruction = 'standing instruction';

const ref = (current: any) => ({ current });
const ctx: any = {
  activeSources: [],
  addPerfLog: () => {},
  addUnidexLog: () => {},
  agentRef: ref({ name: 'Alice' }),
  clearWorkspaceRuntime: (options: any) => {
    const snapshot: any = {};
    if (options.document) { snapshot.document = runtime.document; runtime.document = ''; }
    if (options.transcript) { snapshot.transcript = runtime.transcript; runtime.transcript = []; }
    if (options.unidexLog) { snapshot.unidexLog = runtime.unidexLog; runtime.unidexLog = []; }
    runtimeClears.push(options);
    return snapshot;
  },
  client: { sendToolResponse: (payload: any) => responses.push(payload) },
  currentUserText: ref(''),
  documentContentRef: ref(runtime.document),
  documentGoal,
  exportProfile,
  hasFlushedThisTurnRef: ref(false),
  hasSearchedThisTurnRef: ref(false),
  latestUserTurnIdRef: ref(1),
  log: () => {},
  lastUserRequestRef: ref(''),
  processedAgentTurnIdRef: ref(1),
  promptVersionRef: ref(1),
  runWorkspaceCommand: async (command: string, instruction: string) => {
    commands.push({ command, instruction });
  },
  restoreWorkspaceRuntime: (snapshot: any) => {
    if (snapshot.document !== undefined) runtime.document = snapshot.document;
    if (snapshot.transcript) runtime.transcript = snapshot.transcript;
    if (snapshot.unidexLog) runtime.unidexLog = snapshot.unidexLog;
    runtimeRestores.push(snapshot);
  },
  setAgentState: () => {},
  setDocumentGoal: (value: string) => { documentGoal = value; },
  setDocumentContent: () => {},
  setExportProfile: (value: string) => { exportProfile = value; },
  setScribeMode: (value: string) => { scribeMode = value; },
  setWorkspaceInstruction: (value: string) => { workspaceInstruction = value; setInstructions.push(value); },
  scribeMode,
  suppressStaleAgentResponses: false,
  turnCounterRef: ref(1),
  userRef: ref({ name: 'User', topic: '', format: 'Markdown', info: '' }),
  workspaceInstruction,
};

const handler = createToolCallHandler(ctx, {
  flushModelTextBuffer: () => {},
  updateSuppressionState: () => {},
});

await handler({
  functionCalls: [
    { id: 'run', name: 'runWorkspaceCommand', args: { command: 'rewrite this', instruction: 'one-off' } },
  ],
} as any);

await handler({
  functionCalls: [
    { id: 'guard', name: 'updateWorkspaceSettings', args: { commandInstruction: "Queued: Button for 'rewrite this'." } },
  ],
} as any);

await handler({
  functionCalls: [
    { id: 'clear', name: 'clearWorkspaceData', args: { all: true } },
  ],
} as any);

if (!useWorkspaceRestoreStore.getState().snapshots.length) {
  throw new Error('Clear did not create a session restore snapshot.');
}

if (commands.length !== 2 || commands.some(item => item.command !== 'rewrite')) {
  throw new Error(`Workspace command did not run twice as rewrite: ${JSON.stringify(commands)}`);
}
if (setInstructions.some(value => /queued|button/i.test(value))) {
  throw new Error(`Button queue text was saved as instruction: ${JSON.stringify(setInstructions)}`);
}
if (store.scribe_api_key !== 'keep-this-key') throw new Error('API key was not preserved.');
if (useSourceStore.getState().sources.length) throw new Error('Sources were not cleared.');
if (useVersionStore.getState().versions.length) throw new Error('Versions were not cleared.');
if (useStorageStore.getState().savedDocs.length) throw new Error('Saved docs were not cleared.');
if (!runtimeClears.some(item => item.document) || !runtimeClears.some(item => item.transcript)) {
  throw new Error(`Runtime clears missing document/transcript: ${JSON.stringify(runtimeClears)}`);
}
if (!runtimeClears.some(item => item.unidexLog)) {
  throw new Error(`Runtime clears missing Unidex Log: ${JSON.stringify(runtimeClears)}`);
}
if (runtime.document || runtime.transcript.length || runtime.unidexLog.length) {
  throw new Error(`Runtime data was not cleared: ${JSON.stringify(runtime)}`);
}

await handler({
  functionCalls: [
    { id: 'restore', name: 'restoreWorkspaceData', args: { all: true } },
  ],
} as any);

if (useSourceStore.getState().sources.length !== 1) throw new Error('Sources were not restored.');
if (useVersionStore.getState().versions.length !== 1) throw new Error('Versions were not restored.');
if (useStorageStore.getState().savedDocs.length !== 1) throw new Error('Saved docs were not restored.');
if (runtime.document !== '# Current' || runtime.transcript.length !== 1 || runtime.unidexLog.length !== 1) {
  throw new Error(`Runtime data was not restored: ${JSON.stringify({ runtime, runtimeRestores })}`);
}
if (documentGoal !== 'goal' || exportProfile !== 'brief' || scribeMode !== 'research') {
  throw new Error(`Workspace settings were not restored: ${JSON.stringify({ documentGoal, exportProfile, scribeMode })}`);
}
if (workspaceInstruction !== 'standing instruction') {
  throw new Error(`Workspace instruction was not restored: ${workspaceInstruction}`);
}

console.log('workspace tool smoke ok');
