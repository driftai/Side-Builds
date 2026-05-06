(function(ns) {
  function getDom() {
    return {
      fileUpload: document.getElementById('fileUpload'),
      uploadDropzone: document.getElementById('uploadDropzone'),
      gridSize: document.getElementById('gridSize'),
      brightness: document.getElementById('brightness'),
      contrast: document.getElementById('contrast'),
      gamma: document.getElementById('gamma'),
      smoothing: document.getElementById('smoothing'),
      ditherType: document.getElementById('ditherType'),
      dotShape: document.getElementById('dotShape'),
      dotColor: document.getElementById('dotColor'),
      backgroundColor: document.getElementById('backgroundColor'),
      dotOpacity: document.getElementById('dotOpacity'),
      dotScale: document.getElementById('dotScale'),
      dotAngle: document.getElementById('dotAngle'),
      dotJitter: document.getElementById('dotJitter'),
      invertOutput: document.getElementById('invertOutput'),
      transparentBackground: document.getElementById('transparentBackground'),
      presetSelect: document.getElementById('presetSelect'),
      presetApplyButton: document.getElementById('presetApplyButton'),
      presetSaveButton: document.getElementById('presetSaveButton'),
      presetNewButton: document.getElementById('presetNewButton'),
      presetResetButton: document.getElementById('presetResetButton'),
      sampleSelect: document.getElementById('sampleSelect'),
      themeMode: document.getElementById('themeMode'),
      exportScale: document.getElementById('exportScale'),
      zoomMode: document.getElementById('zoomMode'),
      canvasViewport: document.getElementById('canvasViewport'),
      previewState: document.getElementById('previewState'),
      previewModeButtons: Array.from(document.querySelectorAll('[data-preview-mode]')),
      sampleButton: document.getElementById('sampleButton'),
      resetButton: document.getElementById('resetButton'),
      saveButton: document.getElementById('saveButton'),
      statusText: document.getElementById('statusText'),
      canvas: document.getElementById('halftoneCanvas'),
      values: {
        gridSize: document.getElementById('gridSizeVal'),
        brightness: document.getElementById('brightnessVal'),
        contrast: document.getElementById('contrastVal'),
        gamma: document.getElementById('gammaVal'),
        smoothing: document.getElementById('smoothingVal'),
        dotOpacity: document.getElementById('dotOpacityVal'),
        dotScale: document.getElementById('dotScaleVal'),
        dotAngle: document.getElementById('dotAngleVal'),
        dotJitter: document.getElementById('dotJitterVal')
      }
    };
  }

  function readSettings(dom) {
    return {
      gridSize: Number(dom.gridSize.value),
      brightness: Number(dom.brightness.value),
      contrast: Number(dom.contrast.value),
      gamma: Number(dom.gamma.value),
      smoothing: Number(dom.smoothing.value),
      ditherType: dom.ditherType.value,
      dotShape: dom.dotShape.value,
      dotColor: dom.dotColor.value,
      backgroundColor: dom.backgroundColor.value,
      dotOpacity: Number(dom.dotOpacity.value),
      dotScale: Number(dom.dotScale.value),
      dotAngle: Number(dom.dotAngle.value),
      dotJitter: Number(dom.dotJitter.value),
      invert: dom.invertOutput.checked,
      transparentBackground: dom.transparentBackground.checked,
      previewMode: dom.previewMode || 'halftone',
      zoomMode: dom.zoomMode.value,
      exportScale: Number(dom.exportScale.value)
    };
  }

  function syncControls(dom, settings) {
    setControlValue(dom.gridSize, settings.gridSize);
    setControlValue(dom.brightness, settings.brightness);
    setControlValue(dom.contrast, settings.contrast);
    setControlValue(dom.gamma, settings.gamma);
    setControlValue(dom.smoothing, settings.smoothing);
    setControlValue(dom.ditherType, settings.ditherType);
    setControlValue(dom.dotShape, settings.dotShape);
    setControlValue(dom.dotColor, settings.dotColor);
    setControlValue(dom.backgroundColor, settings.backgroundColor);
    setControlValue(dom.dotOpacity, settings.dotOpacity);
    setControlValue(dom.dotScale, settings.dotScale);
    setControlValue(dom.dotAngle, settings.dotAngle);
    setControlValue(dom.dotJitter, settings.dotJitter);
    setControlValue(dom.zoomMode, settings.zoomMode);
    setControlValue(dom.exportScale, settings.exportScale);

    if (settings.invert !== undefined) {
      dom.invertOutput.checked = settings.invert;
    }

    if (settings.transparentBackground !== undefined) {
      dom.transparentBackground.checked = settings.transparentBackground;
    }

    if (settings.previewMode) {
      setPreviewMode(dom, settings.previewMode);
    }

    syncOutputs(dom);
  }

  function syncOutputs(dom) {
    dom.values.gridSize.value = dom.gridSize.value;
    dom.values.brightness.value = dom.brightness.value;
    dom.values.contrast.value = dom.contrast.value;
    dom.values.gamma.value = dom.gamma.value;
    dom.values.smoothing.value = dom.smoothing.value;
    dom.values.dotOpacity.value = dom.dotOpacity.value;
    dom.values.dotScale.value = dom.dotScale.value;
    dom.values.dotAngle.value = dom.dotAngle.value;
    dom.values.dotJitter.value = dom.dotJitter.value;
  }

  function setStatus(dom, message) {
    dom.statusText.textContent = message;
  }

  function setPreviewMode(dom, mode) {
    dom.previewMode = mode;
    dom.previewModeButtons.forEach((button) => {
      const isActive = button.dataset.previewMode === mode;
      button.classList.toggle('is-active', isActive);
      button.setAttribute('aria-pressed', String(isActive));
    });
  }

  function setPreviewState(dom, message) {
    if (!message) {
      dom.previewState.hidden = true;
      dom.previewState.textContent = '';
      return;
    }

    dom.previewState.textContent = message;
    dom.previewState.hidden = false;
  }

  function renderPresetOptions(dom, presets, selectedId) {
    dom.presetSelect.replaceChildren();

    presets.forEach((preset) => {
      const option = document.createElement('option');
      option.value = preset.id;
      option.textContent = preset.label + getPresetSuffix(preset);
      dom.presetSelect.append(option);
    });

    if (selectedId && presets.some((preset) => preset.id === selectedId)) {
      dom.presetSelect.value = selectedId;
    }

    syncPresetActionLabel(dom, presets);
  }

  function syncPresetActionLabel(dom, presets) {
    const selected = presets.find((preset) => preset.id === dom.presetSelect.value);
    dom.presetResetButton.textContent = selected && selected.kind === 'custom' ? 'Delete preset' : 'Reset preset';
    dom.presetSaveButton.disabled = !selected;
    dom.presetApplyButton.disabled = !selected;
    dom.presetResetButton.disabled = !selected;
  }

  function renderSampleOptions(dom, samples, selectedId) {
    dom.sampleSelect.replaceChildren();

    samples.forEach((sample) => {
      const option = document.createElement('option');
      option.value = sample.id;
      option.textContent = sample.label;
      dom.sampleSelect.append(option);
    });

    if (selectedId && samples.some((sample) => sample.id === selectedId)) {
      dom.sampleSelect.value = selectedId;
    }
  }

  function getPresetSuffix(preset) {
    if (preset.kind === 'custom') {
      return ' (custom)';
    }

    if (preset.isEdited) {
      return ' (edited)';
    }

    return '';
  }

  function setControlValue(control, value) {
    if (value !== undefined) {
      control.value = value;
    }
  }

  function debounce(callback, delay) {
    let timerId;
    return function(...args) {
      clearTimeout(timerId);
      timerId = setTimeout(() => callback.apply(this, args), delay);
    };
  }

  ns.getDom = getDom;
  ns.readSettings = readSettings;
  ns.syncControls = syncControls;
  ns.syncOutputs = syncOutputs;
  ns.setStatus = setStatus;
  ns.setPreviewMode = setPreviewMode;
  ns.setPreviewState = setPreviewState;
  ns.renderPresetOptions = renderPresetOptions;
  ns.syncPresetActionLabel = syncPresetActionLabel;
  ns.renderSampleOptions = renderSampleOptions;
  ns.debounce = debounce;
})(window.HalftoneEditor = window.HalftoneEditor || {});
