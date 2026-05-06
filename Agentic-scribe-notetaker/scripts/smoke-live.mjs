import fs from 'node:fs';
import { GoogleGenAI, Modality, Type } from '@google/genai';

const LIVE_MODELS = [
  'gemini-3.1-flash-live-preview',
  'gemini-2.5-flash-native-audio-preview-12-2025',
];

function readEnvFile(path) {
  if (!fs.existsSync(path)) return {};
  return Object.fromEntries(
    fs.readFileSync(path, 'utf8')
      .split(/\r?\n/)
      .map(line => line.trim())
      .filter(line => line && !line.startsWith('#') && line.includes('='))
      .map(line => {
        const index = line.indexOf('=');
        return [
          line.slice(0, index).trim(),
          line.slice(index + 1).trim().replace(/^['"]|['"]$/g, ''),
        ];
      }),
  );
}

const env = { ...readEnvFile('.env.local'), ...process.env };
const apiKey = env.GEMINI_API_KEY || env.API_KEY;

if (!apiKey) {
  console.error('No GEMINI_API_KEY or API_KEY found in .env.local or process env.');
  process.exit(1);
}

const ai = new GoogleGenAI({ apiKey });
const tools = [{
  functionDeclarations: [
    { name: 'getContext', description: 'Gets context', parameters: { type: Type.OBJECT, properties: {} } },
    {
      name: 'updateDocument',
      description: 'Updates the document',
      parameters: {
        type: Type.OBJECT,
        properties: { content: { type: Type.STRING } },
        required: ['content'],
      },
    },
    {
      name: 'updateWorkspaceSettings',
      description: 'Updates Workspace settings',
      parameters: {
        type: Type.OBJECT,
        properties: {
          scribeMode: { type: Type.STRING },
          exportProfile: { type: Type.STRING },
          documentGoal: { type: Type.STRING },
          commandInstruction: { type: Type.STRING },
        },
      },
    },
    {
      name: 'runWorkspaceCommand',
      description: 'Runs a Workspace command button',
      parameters: {
        type: Type.OBJECT,
        properties: {
          command: { type: Type.STRING },
          instruction: { type: Type.STRING },
        },
        required: ['command'],
      },
    },
    {
      name: 'clearWorkspaceData',
      description: 'Clears workspace data',
      parameters: {
        type: Type.OBJECT,
        properties: {
          all: { type: Type.BOOLEAN },
          sources: { type: Type.BOOLEAN },
          versions: { type: Type.BOOLEAN },
          savedDocs: { type: Type.BOOLEAN },
          document: { type: Type.BOOLEAN },
          transcript: { type: Type.BOOLEAN },
          unidexLog: { type: Type.BOOLEAN },
          workspaceSettings: { type: Type.BOOLEAN },
        },
      },
    },
    {
      name: 'restoreWorkspaceData',
      description: 'Restores workspace data cleared in this session',
      parameters: {
        type: Type.OBJECT,
        properties: {
          all: { type: Type.BOOLEAN },
          sources: { type: Type.BOOLEAN },
          versions: { type: Type.BOOLEAN },
          savedDocs: { type: Type.BOOLEAN },
          document: { type: Type.BOOLEAN },
          transcript: { type: Type.BOOLEAN },
          unidexLog: { type: Type.BOOLEAN },
          workspaceSettings: { type: Type.BOOLEAN },
        },
      },
    },
  ],
}];

const waitFor = (predicate, timeoutMs, label, events) =>
  new Promise((resolve, reject) => {
    const started = Date.now();
    const timer = setInterval(() => {
      if (predicate()) {
        clearInterval(timer);
        resolve();
      } else if (Date.now() - started > timeoutMs) {
        clearInterval(timer);
        reject(new Error(`Timed out waiting for ${label}. Events: ${events.join(', ') || 'none'}`));
      }
    }, 100);
  });

function cleanError(error) {
  return String(error?.message || error?.reason || error).replace(apiKey, '[REDACTED_API_KEY]');
}

async function smokeLiveModel(model) {
  let setupComplete = false;
  let closed = false;
  let error = null;
  let outputText = '';
  let audioBytes = 0;
  let turnComplete = false;
  let toolCall = false;
  const events = [];
  const config = {
    responseModalities: [Modality.AUDIO],
    inputAudioTranscription: {},
    outputAudioTranscription: {},
    speechConfig: {
      voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Kore' } },
    },
    systemInstruction: 'You are a smoke test endpoint. Reply briefly without using tools unless required.',
    tools,
  };

  if (!model.includes('3.1')) {
    config.thinkingConfig = { thinkingBudget: 0 };
  }

  const session = await ai.live.connect({
    model,
    config,
    callbacks: {
      onopen: () => events.push('open'),
      onmessage: message => {
        if (message.setupComplete) {
          setupComplete = true;
          events.push('setup');
          return;
        }
        if (message.toolCall) {
          toolCall = true;
          events.push('toolCall');
        }
        const content = message.serverContent;
        if (content?.outputTranscription?.text) {
          outputText += content.outputTranscription.text;
          events.push('transcript');
        }
        for (const part of content?.modelTurn?.parts || []) {
          if (part.inlineData?.data && !part.thought) {
            audioBytes += Buffer.from(part.inlineData.data, 'base64').byteLength;
            events.push('audio');
          }
          if (part.text && !part.thought) {
            outputText += part.text;
            events.push('text');
          }
        }
        if (content?.turnComplete) {
          turnComplete = true;
          events.push('turnComplete');
        }
      },
      onerror: err => {
        error = err;
        events.push('error');
      },
      onclose: event => {
        closed = true;
        events.push(`close:${event?.reason || ''}`);
      },
    },
  });

  try {
    await waitFor(() => setupComplete || error || closed, 20_000, 'setup', events);
    if (!setupComplete) throw error || new Error(`Connection closed before setup: ${events.join(', ')}`);

    session.sendRealtimeInput({ text: 'Reply exactly pong.' });
    await waitFor(
      () => outputText || audioBytes || toolCall || error || closed || turnComplete,
      30_000,
      'response',
      events,
    );
    await new Promise(resolve => setTimeout(resolve, 2_500));

    return {
      model,
      setupComplete,
      responseSeen: Boolean(outputText.trim() || audioBytes || toolCall),
      outputPreview: outputText.trim().slice(0, 120),
      audioBytes,
      turnComplete,
      toolCall,
      events: events.slice(0, 14),
    };
  } finally {
    session.close();
  }
}

const results = [];
for (const model of LIVE_MODELS) {
  try {
    results.push({ ok: true, ...(await smokeLiveModel(model)) });
  } catch (error) {
    results.push({ ok: false, model, error: cleanError(error) });
  }
}

console.log(JSON.stringify(results, null, 2));
if (!results.every(result => result.ok && result.responseSeen)) {
  process.exit(1);
}
