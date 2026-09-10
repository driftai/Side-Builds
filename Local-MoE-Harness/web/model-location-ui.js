(function attachModelLocationUi() {
  const $ = (id) => document.getElementById(id);
  let latestRegistry = [];

  function statusText(model) {
    if (model.installed) return 'Checkpoint ready';
    if (model.location_configured && !model.location_available) return 'Linked path offline or missing';
    if (model.location_configured) return 'Linked path found · checkpoint incomplete';
    return 'Using default model folder';
  }

  function sourceText(model) {
    return model.location_source === 'external' ? 'External location' : 'Harness default';
  }

  function decorateSwitchCards(models) {
    const cards = Array.from(document.querySelectorAll('#model-list .model-card'));
    cards.forEach((card, index) => {
      const model = models[index];
      if (!model) return;
      let row = card.querySelector('.model-card-path');
      if (!row) {
        row = document.createElement('code');
        row.className = 'model-card-path';
        const note = card.querySelector('.model-note');
        if (note) card.insertBefore(row, note);
        else card.appendChild(row);
      }
      row.textContent = model.path_visible
        ? `${sourceText(model)} · ${model.model_path || 'Path unavailable'}`
        : `${sourceText(model)} · filesystem path hidden`;
      row.title = model.path_visible ? (model.runtime_path || model.model_path || '') : '';
    });
  }

  async function fetchRegistry() {
    const response = await fetch('/api/models', {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function saveLocation(modelId, path) {
    const response = await fetch('/api/models/location', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({model_id: modelId, path})
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail?.message || data.detail || `HTTP ${response.status}`;
      throw new Error(detail);
    }
    return data;
  }

  function makeButton(label, className) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    if (className) button.className = className;
    return button;
  }

  function renderModel(model, editable) {
    const card = document.createElement('article');
    card.className = 'model-location-card';

    const head = document.createElement('div');
    head.className = 'model-location-head';
    const titleWrap = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = model.display_name;
    const state = document.createElement('span');
    state.className = `model-location-state${model.installed ? ' ready' : ''}`;
    state.textContent = statusText(model);
    titleWrap.append(title, state);
    const source = document.createElement('span');
    source.className = 'model-location-source';
    source.textContent = sourceText(model);
    head.append(titleWrap, source);

    const path = document.createElement('code');
    path.className = 'model-location-path';
    path.textContent = model.path_visible
      ? (model.model_path || 'Path unavailable')
      : 'Filesystem path hidden for non-local clients';

    const form = document.createElement('div');
    form.className = 'model-location-form';
    const input = document.createElement('input');
    input.type = 'text';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.placeholder = model.path_visible
      ? (model.default_model_path || 'Absolute model directory path')
      : 'Location editing is available only from the local machine';
    input.value = model.location_configured && model.path_visible ? (model.model_path || '') : '';
    input.disabled = !editable;
    input.setAttribute('aria-label', `${model.display_name} model location`);

    const link = makeButton(model.location_configured ? 'Update path' : 'Link path');
    const reset = makeButton('Use default', 'secondary');
    link.disabled = !editable;
    reset.disabled = !editable || !model.location_configured;

    const feedback = document.createElement('span');
    feedback.className = 'model-location-feedback';

    link.addEventListener('click', async () => {
      const value = input.value.trim();
      if (!value) {
        feedback.textContent = 'Enter an absolute directory path first.';
        return;
      }
      link.disabled = true;
      reset.disabled = true;
      feedback.textContent = 'Checking path…';
      try {
        await saveLocation(model.id, value);
        feedback.textContent = 'Location linked.';
        await refresh();
        if (typeof window.refreshStatus === 'function') window.refreshStatus();
      } catch (error) {
        feedback.textContent = error.message;
        link.disabled = false;
        reset.disabled = !model.location_configured;
      }
    });

    reset.addEventListener('click', async () => {
      if (!window.confirm(`Return ${model.display_name} to its Harness-default model folder?`)) return;
      link.disabled = true;
      reset.disabled = true;
      feedback.textContent = 'Resetting…';
      try {
        await saveLocation(model.id, null);
        feedback.textContent = 'Default location restored.';
        await refresh();
        if (typeof window.refreshStatus === 'function') window.refreshStatus();
      } catch (error) {
        feedback.textContent = error.message;
        link.disabled = false;
        reset.disabled = false;
      }
    });

    form.append(input, link, reset);

    const hint = document.createElement('p');
    hint.className = 'model-location-hint';
    if (model.active) {
      hint.textContent = 'This model is active. Stop the local runtime before changing its linked location.';
    } else if (model.location_configured && !model.installed) {
      hint.textContent = 'The link is saved. Connect the drive or restore the required checkpoint files, then refresh.';
    } else {
      hint.textContent = 'Paste an absolute directory path. External/removable locations stay machine-local and are never committed.';
    }

    card.append(head, path, form, feedback, hint);
    return card;
  }

  async function refresh() {
    const list = $('model-location-list');
    const notice = $('model-location-notice');
    if (!list) return;
    try {
      const data = await fetchRegistry();
      latestRegistry = data.registry || [];
      const editable = Boolean(data.location_editable);
      if (notice) {
        notice.textContent = editable
          ? 'Paths are visible only on this machine. Link any supported model to an absolute local, WSL-visible, or removable-drive directory.'
          : 'Model paths are hidden because this page is not being accessed from the Harness machine itself.';
      }
      const fragment = document.createDocumentFragment();
      for (const model of latestRegistry) {
        fragment.appendChild(renderModel(model, editable));
      }
      list.replaceChildren(fragment);
      decorateSwitchCards(latestRegistry);
    } catch (error) {
      if (notice) notice.textContent = `Could not load model locations: ${error.message}`;
      list.replaceChildren();
    }
  }

  window.LocalMoeModelLocations = {refresh};
  window.addEventListener('DOMContentLoaded', () => {
    const modelList = $('model-list');
    if (modelList && typeof MutationObserver !== 'undefined') {
      new MutationObserver(() => decorateSwitchCards(latestRegistry)).observe(modelList, {
        childList: true
      });
    }
    refresh();
    $('change-model')?.addEventListener('click', () => setTimeout(refresh, 0));
    $('refresh')?.addEventListener('click', () => setTimeout(refresh, 0));
  });
})();
