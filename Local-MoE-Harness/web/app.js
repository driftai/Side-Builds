const $ = (id) => document.getElementById(id);
let activeModel = null;
let currentAbortCtrl = null;
let runtimeReady = false;
let statusPollTimer = null;
let statusRefreshPromise = null;
let conversationHistory = [];
let userCancelledGeneration = false;
let modelCatalog = [];
let modelSwitchState = {status: 'idle', stage: 'idle'};
let modelSwitchInProgress = false;

const modelUi = window.LocalMoeModelUi;

const DEFAULT_MAX_TOKENS = 1024;
const AUTO_CONTINUE_MAX_SEGMENTS = 2;
const AUTO_CONTINUE_SEGMENT_TOKENS = 1024;
const CONTINUATION_INSTRUCTION =
  'Continue the previous assistant response exactly where it stopped. ' +
  'Do not restart, summarize, repeat earlier text, or mention that you are continuing.';

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function formatInteger(value) {
  return finiteNumber(value) ? Math.round(value).toLocaleString() : '—';
}

function formatMode(value) {
  if (!value) return 'Unknown';
  return String(value)
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function contextProfileLabel(capacity) {
  if (capacity === 12288) return 'Balanced 12K';
  if (capacity === 8192) return 'Fast 8K';
  if (capacity === 4096) return '4K profile';
  return capacity ? 'Custom' : 'Unknown';
}

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value == null || value === '' ? '—' : String(value);
}

function registryModel(modelId) {
  return modelCatalog.find((model) => model.id === modelId) || null;
}

function updateSwitchInteractionState() {
  const blocked = modelSwitchInProgress;
  const prompt = $('prompt');
  const send = $('send-btn');
  const benchmark = $('benchmark');
  const start = $('start-runtime');
  if (prompt) prompt.disabled = blocked;
  if (send) send.disabled = blocked;
  if (benchmark) benchmark.disabled = blocked;
  if (start && blocked) start.disabled = true;
}

function renderModelRegistry() {
  const list = $('model-list');
  if (!list || !modelUi) return;
  const active = modelCatalog.find((model) => model.active) || null;
  const selected = modelCatalog.find((model) => model.selected) || active;
  setText('selected-model-name', active?.display_name || selected?.display_name || 'No selected model');
  setText(
    'selected-model-note',
    active
      ? `${modelUi.availabilityLabel(active)} · ${modelUi.validationLabel(active.validation)} · ${active.kind.toUpperCase()} · ${active.quantization}`
      : 'Model changes use a controlled FreeToken restart.'
  );

  const progress = $('model-switch-progress');
  if (progress) {
    const target = registryModel(modelSwitchState.target_model_id);
    const previous = registryModel(modelSwitchState.previous_model_id);
    progress.textContent = modelUi.switchStageLabel(
      modelSwitchState.stage,
      target?.display_name,
      previous?.display_name
    );
    progress.classList.toggle('hidden', !modelSwitchInProgress);
  }

  const fragment = document.createDocumentFragment();
  for (const model of modelCatalog) {
    const card = document.createElement('article');
    card.className = `model-card${model.active ? ' active' : ''}`;

    const head = document.createElement('div');
    head.className = 'model-card-head';
    const title = document.createElement('h3');
    title.textContent = model.display_name;
    const badge = document.createElement('span');
    badge.className = 'model-badge';
    badge.textContent = modelUi.availabilityLabel(model);
    head.append(title, badge);

    const meta = document.createElement('div');
    meta.className = 'model-meta';
    meta.textContent = `${modelUi.validationLabel(model.validation)} · ${String(model.kind).toUpperCase()} · ${model.quantization}`;
    const note = document.createElement('p');
    note.className = 'model-note';
    note.textContent = model.notes || '';

    const action = modelUi.actionForModel(model, modelSwitchInProgress);
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = action.label;
    button.disabled = !action.enabled;
    if (action.enabled) button.addEventListener('click', () => switchModel(model));

    card.append(head, meta, note, button);
    fragment.appendChild(card);
  }
  list.replaceChildren(fragment);
  updateSwitchInteractionState();
}

async function switchModel(model) {
  if (modelSwitchInProgress || currentAbortCtrl) return;
  const hasConversation = conversationHistory.length > 0 || $('chat').childElementCount > 0;
  const warning = hasConversation
    ? `Switch to ${model.display_name}? This restarts FreeToken and clears the current conversation.`
    : `Switch to ${model.display_name}? This restarts the local FreeToken runtime.`;
  if (!window.confirm(warning)) return;

  modelSwitchInProgress = true;
  modelSwitchState = {
    status: 'switching',
    stage: 'stopping_previous',
    target_model_id: model.id,
    previous_model_id: modelCatalog.find((item) => item.active)?.id || null
  };
  runtimeReady = false;
  renderModelRegistry();
  scheduleStatusPoll(500);
  try {
    const response = await fetch('/api/models/select', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({model_id: model.id})
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail?.message || data.detail || `HTTP ${response.status}`);
    }
    conversationHistory = [];
    $('chat').replaceChildren();
    $('bench-output')?.classList.add('hidden');
    addMessage('assistant', `${model.display_name} is ready. A new conversation has started.`);
  } catch (error) {
    addMessage('assistant', `Model switch error: ${error.message}`);
  } finally {
    modelSwitchInProgress = false;
    await refreshStatus();
    renderModelRegistry();
  }
}

function scheduleStatusPoll(delayMs = 8000) {
  if (statusPollTimer) clearTimeout(statusPollTimer);
  statusPollTimer = setTimeout(() => {
    statusPollTimer = null;
    if (currentAbortCtrl) {
      scheduleStatusPoll(3000);
      return;
    }
    refreshStatus();
  }, delayMs);
}

function renderStatusDetails(data) {
  const runtime = data.runtime || {};
  const settings = data.settings || {};
  const coexistence = data.gpu_coexistence || {};
  const gpu = coexistence.gpu || {};

  const capacity = settings.conversation_kv_floor_tokens;
  const capacityText = finiteNumber(capacity)
    ? `${contextProfileLabel(capacity)} · ${formatInteger(capacity)} tokens`
    : 'Unknown';
  setText('context-state', capacityText);

  if (finiteNumber(gpu.util_pct)) {
    const memory = finiteNumber(gpu.memory_used_mb) && finiteNumber(gpu.memory_total_mb)
      ? ` · ${formatInteger(gpu.memory_used_mb)} / ${formatInteger(gpu.memory_total_mb)} MiB`
      : '';
    setText('gpu-state', `${Math.round(gpu.util_pct)}%${memory}`);
  } else {
    setText('gpu-state', coexistence.telemetry_error ? 'Telemetry unavailable' : 'Unknown');
  }

  setText('gpu-mode', formatMode(coexistence.mode));

  const activeSlots = coexistence.active_moe_slots;
  const normalSlots = coexistence.normal_moe_slots;
  if (finiteNumber(activeSlots) && finiteNumber(normalSlots)) {
    setText(
      'moe-state',
      activeSlots === normalSlots
        ? `${formatInteger(activeSlots)} slots`
        : `${formatInteger(activeSlots)} / ${formatInteger(normalSlots)} slots`
    );
  } else if (finiteNumber(activeSlots)) {
    setText('moe-state', `${formatInteger(activeSlots)} slots`);
  } else if (finiteNumber(normalSlots)) {
    setText('moe-state', `${formatInteger(normalSlots)} target`);
  } else {
    setText('moe-state', 'Unknown');
  }

  const activeRequests = finiteNumber(coexistence.active_requests) ? coexistence.active_requests : 0;
  const timeout = coexistence.request_timeout_seconds;
  const requestLabel = activeRequests > 0
    ? `Active (${formatInteger(activeRequests)})`
    : 'Idle';
  setText(
    'request-state',
    finiteNumber(timeout) ? `${requestLabel} · ${formatInteger(timeout)}s` : requestLabel
  );

  setText(
    'runtime-latency',
    finiteNumber(runtime.latency_ms) ? `${runtime.latency_ms.toFixed(1)} ms` : '—'
  );
  setText('startup-mode', formatMode(coexistence.startup_gpu_mode));
  setText(
    'telemetry-source',
    coexistence.telemetry_error
      ? `Error: ${coexistence.telemetry_error}`
      : (gpu.source || '—')
  );
  setText(
    'request-timeout',
    finiteNumber(timeout) ? `${formatInteger(timeout)} seconds` : '—'
  );
  setText(
    'context-margin',
    finiteNumber(settings.conversation_context_margin_tokens)
      ? `${formatInteger(settings.conversation_context_margin_tokens)} tokens`
      : '—'
  );
  setText(
    'history-limit',
    finiteNumber(settings.conversation_raw_history_max_messages)
      ? `${formatInteger(settings.conversation_raw_history_max_messages)} messages`
      : '—'
  );

  const memoryItems = settings.conversation_memory_max_items;
  const memoryChars = settings.conversation_memory_max_chars;
  if (finiteNumber(memoryItems) || finiteNumber(memoryChars)) {
    const parts = [];
    if (finiteNumber(memoryItems)) parts.push(`${formatInteger(memoryItems)} items`);
    if (finiteNumber(memoryChars)) parts.push(`${formatInteger(memoryChars)} chars`);
    setText('memory-limit', parts.join(' · '));
  } else {
    setText('memory-limit', '—');
  }

  const totalAutoTokens = DEFAULT_MAX_TOKENS + (AUTO_CONTINUE_MAX_SEGMENTS * AUTO_CONTINUE_SEGMENT_TOKENS);
  setText(
    'output-policy',
    `${DEFAULT_MAX_TOKENS} + ${AUTO_CONTINUE_MAX_SEGMENTS}×${AUTO_CONTINUE_SEGMENT_TOKENS} · ~${totalAutoTokens} max`
  );

  const transitionParts = [];
  if (coexistence.pending_transition) {
    transitionParts.push(`Pending: ${formatMode(coexistence.pending_transition)}`);
  }
  if (coexistence.last_transition_error) {
    transitionParts.push(`Error: ${coexistence.last_transition_error}`);
  }
  setText('gpu-transition', transitionParts.length ? transitionParts.join(' · ') : 'None');

  const hostStorage = data.system?.host_storage || {};
  const wslVirtual = data.system?.wsl_virtual_disk || {};

  if (hostStorage.volume && finiteNumber(hostStorage.free_gb) && finiteNumber(hostStorage.total_gb)) {
    setText(
      'host-volume',
      `${hostStorage.volume} · ${hostStorage.free_gb.toFixed(2)} GiB free / ${hostStorage.total_gb.toFixed(2)} GiB`
    );
  } else if (hostStorage.volume && finiteNumber(hostStorage.free_gb)) {
    setText('host-volume', `${hostStorage.volume} · ${hostStorage.free_gb.toFixed(2)} GiB free`);
  } else {
    setText('host-volume', hostStorage.error ? 'Unavailable' : '—');
  }

  if (finiteNumber(wslVirtual.free_gb) && finiteNumber(wslVirtual.total_gb)) {
    setText(
      'wsl-virtual-disk',
      `${wslVirtual.free_gb.toFixed(2)} GiB free / ${wslVirtual.total_gb.toFixed(2)} GiB virtual`
    );
  } else {
    setText('wsl-virtual-disk', wslVirtual.error ? 'Unavailable' : '—');
  }

  if (finiteNumber(hostStorage.vhd_file_gb)) {
    setText('wsl-vhdx-size', `${hostStorage.vhd_file_gb.toFixed(2)} GiB`);
  } else {
    setText('wsl-vhdx-size', '—');
  }

  setText(
    'wsl-ram-available',
    finiteNumber(data.system?.ram_available_gb)
      ? `${data.system.ram_available_gb.toFixed(2)} GB`
      : '—'
  );
  const freetokenMemory = data.system?.freetoken_memory || {};
  if (freetokenMemory.running) {
    const parts = [];
    if (finiteNumber(freetokenMemory.rss_gb)) parts.push(`${freetokenMemory.rss_gb.toFixed(2)} GB RSS`);
    if (finiteNumber(freetokenMemory.pss_gb)) parts.push(`${freetokenMemory.pss_gb.toFixed(2)} GB PSS`);
    setText('freetoken-memory', parts.length ? parts.join(' · ') : 'Running');
  } else {
    setText('freetoken-memory', 'Not running');
  }
}

async function refreshStatus() {
  if (statusRefreshPromise) return statusRefreshPromise;

  const pill = $('runtime-pill');
  const startBtn = $('start-runtime');
  if (statusPollTimer) {
    clearTimeout(statusPollTimer);
    statusPollTimer = null;
  }

  statusRefreshPromise = (async () => {
    pill.className = 'pill';
    pill.textContent = 'Checking runtime…';
    try {
      const r = await fetch('/api/status', {cache: 'no-store'});
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
      const runtime = data.runtime || {};
      const lifecycle = data.runtime_lifecycle || {};
      modelCatalog = Array.isArray(data.model_registry) ? data.model_registry : [];
      modelSwitchState = data.model_switch || {status: 'idle', stage: 'idle'};
      modelSwitchInProgress = modelSwitchState.status === 'switching' || Boolean(data.gpu_coexistence?.model_switching);
      activeModel = runtime.models?.[0]?.id || null;
      runtimeReady = Boolean(runtime.ready) && !modelSwitchInProgress;
      $('runtime').textContent = runtime.runtime || 'freetoken';
      const activeRegistryModel = modelCatalog.find((model) => model.active);
      $('model').textContent = activeRegistryModel?.display_name || activeModel || runtime.health_status || 'No model';
      $('ram').textContent = `${data.system.ram_used_gb} / ${data.system.ram_total_gb} GB`;

      const hostStorage = data.system?.host_storage || {};
      if (finiteNumber(hostStorage.free_gb) && hostStorage.volume) {
        $('disk').textContent = `${hostStorage.free_gb.toFixed(2)} GiB free · ${hostStorage.volume}`;
      } else if (finiteNumber(hostStorage.free_gb)) {
        $('disk').textContent = `${hostStorage.free_gb.toFixed(2)} GiB free`;
      } else {
        $('disk').textContent = 'Unavailable';
      }

      renderStatusDetails(data);
      renderModelRegistry();

      if (modelSwitchInProgress) {
        const target = registryModel(modelSwitchState.target_model_id);
        const previous = registryModel(modelSwitchState.previous_model_id);
        pill.textContent = modelUi.switchStageLabel(
          modelSwitchState.stage,
          target?.display_name,
          previous?.display_name
        );
        pill.classList.add('down');
        scheduleStatusPoll(1200);
      } else if (runtimeReady) {
        pill.textContent = 'FreeToken ready';
        pill.classList.add('ready');
        if (startBtn) startBtn.classList.add('hidden');
        scheduleStatusPoll(8000);
      } else if (runtime.health_status === 'loading' || lifecycle.managed_running) {
        const phase = runtime.phase && runtime.phase !== 'unknown' ? ` · ${runtime.phase}` : '';
        pill.textContent = `FreeToken loading${phase}`;
        pill.classList.add('down');
        if (startBtn) {
          startBtn.classList.remove('hidden');
          startBtn.disabled = true;
          startBtn.textContent = 'Model loading…';
        }
        scheduleStatusPoll(3000);
      } else {
        pill.textContent = runtime.reachable ? 'FreeToken not ready' : 'FreeToken offline';
        pill.classList.add('down');
        if (startBtn) {
          startBtn.classList.remove('hidden');
          startBtn.disabled = false;
          startBtn.textContent = 'Start local model';
        }
        if (data.settings?.runtime_autostart) scheduleStatusPoll(5000);
      }
      return runtimeReady;
    } catch (e) {
      runtimeReady = false;
      pill.textContent = 'Harness status error';
      pill.classList.add('down');
      if (startBtn) {
        startBtn.classList.remove('hidden');
        startBtn.disabled = false;
        startBtn.textContent = 'Start local model';
      }
      scheduleStatusPoll(5000);
      updateSwitchInteractionState();
      return false;
    }
  })();

  try {
    return await statusRefreshPromise;
  } finally {
    statusRefreshPromise = null;
  }
}

async function writeClipboard(text) {
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    await navigator.clipboard.writeText(text);
    return;
  }

  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.left = '-9999px';
  area.style.opacity = '0';
  document.body.appendChild(area);
  try {
    area.focus();
    area.select();
    if (!document.execCommand('copy')) throw new Error('Browser copy command failed.');
  } finally {
    area.remove();
  }
}

function makeCopyButton(label, getText) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'copy-btn';
  button.textContent = label;
  button.title = label;
  button.setAttribute('aria-label', label);
  button.addEventListener('click', async () => {
    const text = getText();
    if (!text) return;
    const original = label;
    try {
      await writeClipboard(text);
      button.textContent = 'Copied';
      button.setAttribute('aria-label', `${label}: copied`);
    } catch (error) {
      console.warn('Clipboard copy failed:', error);
      button.textContent = 'Copy failed';
      button.setAttribute('aria-label', `${label}: copy failed`);
    }
    setTimeout(() => {
      button.textContent = original;
      button.setAttribute('aria-label', original);
    }, 1300);
  });
  return button;
}

function parseFencedBlocks(rawText) {
  const lines = String(rawText).replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  const parts = [];
  let proseLines = [];
  let openFence = null;

  function flushProse() {
    if (!proseLines.length) return;
    parts.push({type: 'prose', text: proseLines.join('\n')});
    proseLines = [];
  }

  for (const line of lines) {
    if (!openFence) {
      const match = line.match(/^( {0,3})(`{3,}|~{3,})(.*)$/);
      if (!match) {
        proseLines.push(line);
        continue;
      }

      const marker = match[2];
      const info = match[3] || '';
      if (marker[0] === '`' && info.includes('`')) {
        proseLines.push(line);
        continue;
      }

      flushProse();
      openFence = {
        char: marker[0],
        length: marker.length,
        info: info.trim(),
        lines: []
      };
      continue;
    }

    const close = line.match(/^( {0,3})(`+|~+)[ \t]*$/);
    if (
      close &&
      close[2][0] === openFence.char &&
      close[2].length >= openFence.length
    ) {
      const language = openFence.info ? openFence.info.split(/\s+/)[0] : '';
      parts.push({
        type: 'code',
        text: openFence.lines.join('\n'),
        language
      });
      openFence = null;
      continue;
    }

    openFence.lines.push(line);
  }

  if (openFence) {
    const language = openFence.info ? openFence.info.split(/\s+/)[0] : '';
    parts.push({
      type: 'code',
      text: openFence.lines.join('\n'),
      language,
      open: true
    });
  }

  flushProse();
  return parts;
}

function renderAssistantContent(contentEl, rawText) {
  const fragment = document.createDocumentFragment();
  const parts = parseFencedBlocks(rawText);

  for (const part of parts) {
    if (part.type === 'prose') {
      const prose = document.createElement('div');
      prose.className = 'prose';
      prose.textContent = part.text;
      fragment.appendChild(prose);
      continue;
    }

    const block = document.createElement('section');
    block.className = 'code-block';

    const head = document.createElement('div');
    head.className = 'code-head';
    const language = document.createElement('span');
    language.className = 'code-language';
    language.textContent = part.language || (part.open ? 'code · streaming' : 'code');
    head.appendChild(language);
    head.appendChild(makeCopyButton('Copy code', () => part.text));

    const pre = document.createElement('pre');
    const code = document.createElement('code');
    code.textContent = part.text;
    pre.appendChild(code);

    block.appendChild(head);
    block.appendChild(pre);
    fragment.appendChild(block);
  }

  contentEl.replaceChildren(fragment);
}

function createAssistantShell({withStats = false} = {}) {
  const el = document.createElement('div');
  el.className = 'message assistant';

  const rawState = {text: ''};
  const toolbar = document.createElement('div');
  toolbar.className = 'message-toolbar';
  const copyReply = makeCopyButton('Copy reply', () => rawState.text);
  copyReply.disabled = true;
  toolbar.appendChild(copyReply);
  el.appendChild(toolbar);

  const contentEl = document.createElement('div');
  contentEl.className = 'message-content';
  el.appendChild(contentEl);

  const noticeEl = document.createElement('div');
  noticeEl.className = 'stream-notice hidden';
  el.appendChild(noticeEl);

  const reasoningDetails = document.createElement('details');
  reasoningDetails.className = 'reasoning-details hidden';
  const reasoningSummary = document.createElement('summary');
  reasoningSummary.textContent = 'Reasoning';
  const reasoningContent = document.createElement('div');
  reasoningContent.className = 'reasoning-content';
  reasoningDetails.append(reasoningSummary, reasoningContent);
  el.appendChild(reasoningDetails);

  let ttftEl = null;
  let tokensEl = null;
  let tpsEl = null;
  let elapsedEl = null;
  let contextEl = null;
  let memoryEl = null;
  let trimmedEl = null;

  if (withStats) {
    const statsEl = document.createElement('div');
    statsEl.className = 'message-stats';
    statsEl.innerHTML = `
      <span class="stat-ttft">TTFT: —</span>
      <span class="stat-tokens">Tokens: —</span>
      <span class="stat-tps">Decode: —</span>
      <span class="stat-elapsed">Elapsed: 0.0s</span>
      <span class="stat-context muted-stat hidden"></span>
      <span class="stat-memory muted-stat hidden"></span>
      <span class="stat-trimmed muted-stat hidden"></span>
    `;
    el.appendChild(statsEl);
    ttftEl = statsEl.querySelector('.stat-ttft');
    tokensEl = statsEl.querySelector('.stat-tokens');
    tpsEl = statsEl.querySelector('.stat-tps');
    elapsedEl = statsEl.querySelector('.stat-elapsed');
    contextEl = statsEl.querySelector('.stat-context');
    memoryEl = statsEl.querySelector('.stat-memory');
    trimmedEl = statsEl.querySelector('.stat-trimmed');
  }

  $('chat').appendChild(el);
  $('chat').scrollTop = $('chat').scrollHeight;

  let renderFrame = null;

  function renderNow() {
    if (renderFrame !== null) {
      cancelAnimationFrame(renderFrame);
      renderFrame = null;
    }
    renderAssistantContent(contentEl, rawState.text);
  }

  function setRawText(text, immediate = false) {
    rawState.text = text || '';
    copyReply.disabled = !rawState.text;
    if (immediate) {
      renderNow();
      return;
    }
    if (renderFrame === null) {
      renderFrame = requestAnimationFrame(() => {
        renderFrame = null;
        renderAssistantContent(contentEl, rawState.text);
      });
    }
  }

  function setNotice(text) {
    noticeEl.textContent = text || '';
    noticeEl.classList.toggle('hidden', !text);
  }

  function setReasoningText(text) {
    reasoningContent.textContent = text || '';
    reasoningDetails.classList.toggle('hidden', !text);
  }

  return {
    el,
    contentEl,
    rawState,
    setRawText,
    renderNow,
    setNotice,
    setReasoningText,
    ttftEl,
    tokensEl,
    tpsEl,
    elapsedEl,
    contextEl,
    memoryEl,
    trimmedEl
  };
}

function addMessage(role, text) {
  if (role === 'assistant') {
    const box = createAssistantShell();
    box.setRawText(text, true);
    return box.el;
  }

  const el = document.createElement('div');
  el.className = `message ${role}`;
  el.textContent = text;
  $('chat').appendChild(el);
  $('chat').scrollTop = $('chat').scrollHeight;
  return el;
}

function createAssistantStreamBox() {
  const box = createAssistantShell({withStats: true});
  box.contentEl.textContent = '…';
  return box;
}

function applyHarnessMetadata(box, chunk) {
  const context = chunk.harness_context || null;
  if (!context) return;

  if (box.contextEl && finiteNumber(context.prompt_tokens) && finiteNumber(context.prompt_budget_tokens)) {
    box.contextEl.textContent = `Prompt: ${formatInteger(context.prompt_tokens)} / ${formatInteger(context.prompt_budget_tokens)}`;
    if (finiteNumber(context.context_capacity_tokens)) {
      box.contextEl.title = `Total context capacity: ${formatInteger(context.context_capacity_tokens)} tokens; requested output: ${formatInteger(context.requested_max_tokens)} tokens`;
    }
    box.contextEl.classList.remove('hidden');
  }

  if (box.memoryEl && finiteNumber(context.conversation_memory_items) && context.conversation_memory_items > 0) {
    box.memoryEl.textContent = `Memory: ${formatInteger(context.conversation_memory_items)}`;
    box.memoryEl.classList.remove('hidden');
  }

  if (box.trimmedEl && finiteNumber(context.trimmed_history_messages) && context.trimmed_history_messages > 0) {
    box.trimmedEl.textContent = `Trimmed: ${formatInteger(context.trimmed_history_messages)}`;
    box.trimmedEl.classList.remove('hidden');
  }
}

$('refresh').addEventListener('click', refreshStatus);

const changeModelBtn = $('change-model');
const closeModelPanelBtn = $('close-model-panel');
if (changeModelBtn) {
  changeModelBtn.addEventListener('click', () => {
    $('model-panel')?.classList.remove('hidden');
    refreshStatus();
  });
}
if (closeModelPanelBtn) {
  closeModelPanelBtn.addEventListener('click', () => {
    $('model-panel')?.classList.add('hidden');
  });
}

const clearConversationBtn = $('clear-conversation');
if (clearConversationBtn) {
  clearConversationBtn.addEventListener('click', () => {
    conversationHistory = [];
    $('chat').replaceChildren();
    $('bench-output')?.classList.add('hidden');
  });
}

const startRuntimeBtn = $('start-runtime');
if (startRuntimeBtn) {
  startRuntimeBtn.addEventListener('click', async () => {
    startRuntimeBtn.disabled = true;
    startRuntimeBtn.textContent = 'Starting…';
    try {
      const r = await fetch('/api/runtime/start', {method: 'POST'});
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
      if (data.lifecycle?.error) throw new Error(data.lifecycle.error);
      await refreshStatus();
      if (!runtimeReady) scheduleStatusPoll(2000);
    } catch (e) {
      startRuntimeBtn.disabled = false;
      startRuntimeBtn.textContent = 'Start local model';
      addMessage('assistant', `Runtime start error: ${e.message}`);
    }
  });
}

const stopBtn = $('stop-btn');
if (stopBtn) {
  stopBtn.addEventListener('click', () => {
    userCancelledGeneration = true;
    if (currentAbortCtrl) currentAbortCtrl.abort();
  });
}

function longestExactOverlap(existing, incoming, maxChars = 400) {
  const max = Math.min(maxChars, existing.length, incoming.length);
  for (let size = max; size > 0; size -= 1) {
    if (existing.endsWith(incoming.slice(0, size))) return size;
  }
  return 0;
}

$('chat-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (modelSwitchInProgress) return;
  const text = $('prompt').value.trim();
  if (!text) return;
  if (!runtimeReady && !(await refreshStatus())) {
    addMessage('assistant', 'The local model is not ready yet. Start it if needed and wait for “FreeToken ready” before sending.');
    return;
  }

  const historyForRequest = conversationHistory.slice(-40);
  addMessage('user', text);
  $('prompt').value = '';
  if (stopBtn) stopBtn.classList.remove('hidden');

  userCancelledGeneration = false;
  currentAbortCtrl = new AbortController();
  const box = createAssistantStreamBox();

  const t0 = performance.now();
  let firstPieceAt = null;
  let totalCompletionTokens = 0;
  let measuredDecodeTokens = 0;
  let measuredDecodeMs = 0;
  let fullText = '';
  let reasoningText = '';
  let streamCompleted = false;
  let segmentCount = 0;
  let continuationCount = 0;
  let continuationStoppedReason = null;

  const timerInterval = setInterval(() => {
    box.elapsedEl.textContent = `Elapsed: ${((performance.now() - t0) / 1000).toFixed(1)}s`;
  }, 150);

  function appendVisible(textPiece) {
    if (!textPiece) return;
    if (firstPieceAt === null) {
      firstPieceAt = performance.now();
      box.ttftEl.textContent = `TTFT: ${((firstPieceAt - t0) / 1000).toFixed(2)}s`;
    }
    fullText += textPiece;
    box.setRawText(fullText);
    $('chat').scrollTop = $('chat').scrollHeight;
  }

  function appendReasoning(textPiece) {
    if (!textPiece) return;
    if (firstPieceAt === null) {
      firstPieceAt = performance.now();
      box.ttftEl.textContent = `TTFT: ${((firstPieceAt - t0) / 1000).toFixed(2)}s`;
    }
    reasoningText += textPiece;
    box.setReasoningText(reasoningText);
  }

  async function runSegment(isContinuation) {
    const requestHistory = isContinuation
      ? [
          ...historyForRequest,
          {role: 'user', content: text},
          {role: 'assistant', content: fullText}
        ].slice(-40)
      : historyForRequest;

    const body = {
      message: isContinuation ? CONTINUATION_INSTRUCTION : text,
      model: activeModel,
      history: requestHistory,
      max_tokens: isContinuation ? AUTO_CONTINUE_SEGMENT_TOKENS : DEFAULT_MAX_TOKENS
    };

    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
      signal: currentAbortCtrl.signal
    });

    if (!resp.ok) {
      let message = `HTTP ${resp.status}`;
      try {
        const err = await resp.json();
        message = err.detail?.message || err.detail || message;
      } catch (_) {
        const errText = await resp.text();
        if (errText) message = `${message}: ${errText}`;
      }
      throw new Error(message);
    }
    if (!resp.body) throw new Error('Streaming response body is unavailable.');

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let doneSignal = false;
    let finishReason = null;
    let segmentCompletionTokens = null;
    let segmentFirstPieceAt = null;
    let segmentLastPieceAt = null;
    let generatedAnyText = false;
    let continuationPrefixPending = '';
    let continuationPrefixResolved = !isContinuation;

    function flushContinuationPrefix() {
      if (continuationPrefixResolved) return;
      const overlap = longestExactOverlap(fullText, continuationPrefixPending);
      appendVisible(continuationPrefixPending.slice(overlap));
      continuationPrefixPending = '';
      continuationPrefixResolved = true;
    }

    function acceptPiece(piece) {
      if (!piece) return;
      const now = performance.now();
      if (segmentFirstPieceAt === null) segmentFirstPieceAt = now;
      segmentLastPieceAt = now;
      generatedAnyText = true;

      if (isContinuation && !continuationPrefixResolved) {
        continuationPrefixPending += piece;
        if (continuationPrefixPending.length >= 400) {
          flushContinuationPrefix();
        }
      } else {
        appendVisible(piece);
      }
    }

    function handleSseLine(line) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.startsWith('data:')) return false;
      const dataStr = trimmed.slice(5).trimStart();
      if (dataStr === '[DONE]') return true;

      let chunk;
      try {
        chunk = JSON.parse(dataStr);
      } catch (_) {
        return false;
      }

      if (chunk.harness_context) applyHarnessMetadata(box, chunk);
      if (chunk.error) throw new Error(chunk.error.message || JSON.stringify(chunk.error));

      if (chunk.usage && Number.isFinite(chunk.usage.completion_tokens)) {
        segmentCompletionTokens = chunk.usage.completion_tokens;
      }

      const choice = chunk.choices?.[0] || {};
      if (typeof choice.finish_reason === 'string' && choice.finish_reason) {
        finishReason = choice.finish_reason;
      }

      const delta = choice.delta || {};
      const channels = modelUi.streamDeltaChannels(delta);
      const contentPiece = channels.content;
      const reasoningPiece = channels.reasoning;
      if (reasoningPiece) {
        const now = performance.now();
        if (segmentFirstPieceAt === null) segmentFirstPieceAt = now;
        segmentLastPieceAt = now;
        generatedAnyText = true;
        appendReasoning(reasoningPiece);
      }
      acceptPiece(contentPiece);
      return false;
    }

    while (!doneSignal) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (handleSseLine(line)) {
          doneSignal = true;
          break;
        }
      }
    }

    buffer += decoder.decode();
    if (!doneSignal && buffer.trim()) handleSseLine(buffer);
    flushContinuationPrefix();

    if (!generatedAnyText) {
      throw new Error(
        isContinuation
          ? 'The continuation stream ended without generated text.'
          : 'The runtime stream ended without generated text.'
      );
    }

    segmentCount += 1;
    if (Number.isFinite(segmentCompletionTokens)) {
      totalCompletionTokens += segmentCompletionTokens;
      if (
        segmentCompletionTokens > 1 &&
        segmentFirstPieceAt !== null &&
        segmentLastPieceAt !== null &&
        segmentLastPieceAt > segmentFirstPieceAt
      ) {
        measuredDecodeTokens += segmentCompletionTokens - 1;
        measuredDecodeMs += segmentLastPieceAt - segmentFirstPieceAt;
      }
    }
    box.tokensEl.textContent = segmentCount > 1
      ? `Tokens: ${totalCompletionTokens} · Segments: ${segmentCount}`
      : `Tokens: ${totalCompletionTokens || '—'}`;

    return finishReason;
  }

  try {
    let isContinuation = false;
    while (true) {
      let finishReason;
      try {
        finishReason = await runSegment(isContinuation);
      } catch (segmentError) {
        if (
          isContinuation &&
          fullText &&
          segmentError.name !== 'AbortError' &&
          !userCancelledGeneration
        ) {
          continuationStoppedReason = segmentError.message;
          break;
        }
        throw segmentError;
      }

      const shouldContinue =
        finishReason === 'length' &&
        !userCancelledGeneration &&
        continuationCount < AUTO_CONTINUE_MAX_SEGMENTS;

      if (!shouldContinue) {
        if (
          finishReason === 'length' &&
          !userCancelledGeneration &&
          continuationCount >= AUTO_CONTINUE_MAX_SEGMENTS
        ) {
          continuationStoppedReason = 'automatic continuation limit reached';
        }
        break;
      }

      continuationCount += 1;
      isContinuation = true;
      box.elapsedEl.textContent = `Continuing… (${continuationCount}/${AUTO_CONTINUE_MAX_SEGMENTS})`;
      await new Promise((resolve) => setTimeout(resolve, 0));
      if (userCancelledGeneration) break;
    }

    if (!fullText && reasoningText) {
      fullText = reasoningText;
      reasoningText = '';
      box.setReasoningText('');
      box.setRawText(fullText, true);
    }
    if (!fullText) throw new Error('The runtime stream ended without generated text.');

    conversationHistory.push(
      {role: 'user', content: text},
      {role: 'assistant', content: fullText}
    );
    conversationHistory = conversationHistory.slice(-40);
    streamCompleted = true;
  } catch (e) {
    if (e.name === 'AbortError') {
      userCancelledGeneration = true;
      box.setNotice('[Cancelled by user]');
    } else {
      box.setNotice(`[Stream error: ${e.message}]`);
    }
  } finally {
    clearInterval(timerInterval);
    box.setRawText(fullText, true);
    const totalSeconds = (performance.now() - t0) / 1000;
    box.elapsedEl.textContent = `Total: ${totalSeconds.toFixed(2)}s`;

    if (totalCompletionTokens > 0) {
      box.tokensEl.textContent = segmentCount > 1
        ? `Tokens: ${totalCompletionTokens} · Segments: ${segmentCount}`
        : `Tokens: ${totalCompletionTokens}`;
      if (measuredDecodeTokens > 0 && measuredDecodeMs > 0) {
        box.tpsEl.textContent = `Decode: ${(measuredDecodeTokens / (measuredDecodeMs / 1000)).toFixed(2)} tok/s`;
      } else if (totalCompletionTokens === 1) {
        box.tpsEl.textContent = `E2E: ${(1 / totalSeconds).toFixed(2)} tok/s`;
      }
    } else {
      box.tokensEl.textContent = 'Tokens: unavailable';
      box.tpsEl.textContent = 'Decode: unavailable';
    }

    if (continuationStoppedReason && !userCancelledGeneration) {
      box.elapsedEl.textContent += ` · Continuation stopped: ${continuationStoppedReason}`;
    }

    if (stopBtn) stopBtn.classList.add('hidden');
    currentAbortCtrl = null;
    if (!streamCompleted) console.debug('Generation was not added to conversation history.');
    refreshStatus();
  }
});

$('benchmark').addEventListener('click', async () => {
  if (!runtimeReady && !(await refreshStatus())) {
    addMessage('assistant', 'The local model must be ready before benchmarking.');
    return;
  }
  const text = $('prompt').value.trim() || 'Explain why mixture-of-experts inference can benefit from hybrid CPU/GPU execution in 200 words.';
  const output = $('bench-output');
  output.classList.remove('hidden');
  output.textContent = 'Running benchmark…';
  try {
    const r = await fetch('/api/benchmark', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        message: text,
        model: activeModel,
        history: conversationHistory.slice(-40),
        max_tokens: 256
      })
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail?.message || data.detail || 'Benchmark failed');
    output.textContent = JSON.stringify({
      elapsed_seconds: data.elapsed_seconds,
      completion_tokens: data.completion_tokens,
      token_count_source: data.token_count_source,
      end_to_end_tps: data.end_to_end_tps,
      saved_to: data.saved_to
    }, null, 2);
  } catch (e) {
    output.textContent = `Error: ${e.message}`;
  }
});

refreshStatus();
