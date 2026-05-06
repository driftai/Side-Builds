(function(ns) {
  function bindPresetControls(dom, presetManager, onChange) {
    ns.renderPresetOptions(dom, presetManager.list(), 'finePrint');

    dom.presetSelect.addEventListener('change', function() {
      ns.syncPresetActionLabel(dom, presetManager.list());
    });

    dom.presetApplyButton.addEventListener('click', function() {
      applySelectedPreset(dom, presetManager, onChange);
    });

    dom.presetSaveButton.addEventListener('click', function() {
      const saved = presetManager.saveSelected(dom.presetSelect.value, ns.readSettings(dom));
      if (!saved) {
        ns.setStatus(dom, 'Choose a preset before saving.');
        return;
      }

      ns.renderPresetOptions(dom, presetManager.list(), saved.id);
      ns.setStatus(dom, saved.label + ' saved.');
    });

    dom.presetNewButton.addEventListener('click', function() {
      const label = window.prompt('Name this preset');
      if (label === null) {
        return;
      }

      const created = presetManager.create(label, ns.readSettings(dom));
      if (!created) {
        ns.setStatus(dom, 'Preset name is required.');
        return;
      }

      ns.renderPresetOptions(dom, presetManager.list(), created.id);
      ns.setStatus(dom, created.label + ' created.');
    });

    dom.presetResetButton.addEventListener('click', function() {
      resetSelectedPreset(dom, presetManager, onChange);
    });
  }

  function applySelectedPreset(dom, presetManager, onChange) {
    const preset = presetManager.get(dom.presetSelect.value);
    if (!preset) {
      ns.setStatus(dom, 'Choose a preset first.');
      return;
    }

    ns.syncControls(dom, Object.assign({}, ns.readSettings(dom), preset.settings));
    ns.syncPresetActionLabel(dom, presetManager.list());
    ns.setStatus(dom, preset.label + ' applied.');
    onChange();
  }

  function resetSelectedPreset(dom, presetManager, onChange) {
    const selected = presetManager.get(dom.presetSelect.value);
    if (!selected) {
      ns.setStatus(dom, 'Choose a preset first.');
      return;
    }

    if (selected.kind === 'custom' && !window.confirm('Delete "' + selected.label + '"?')) {
      return;
    }

    presetManager.resetOrDelete(selected.id);

    const presets = presetManager.list();
    const nextId = presets.some((preset) => preset.id === selected.id) ? selected.id : presets[0] && presets[0].id;
    ns.renderPresetOptions(dom, presets, nextId);

    if (nextId) {
      applySelectedPreset(dom, presetManager, onChange);
    }

    ns.setStatus(dom, selected.kind === 'custom' ? selected.label + ' deleted.' : selected.label + ' reset.');
  }

  ns.bindPresetControls = bindPresetControls;
})(window.HalftoneEditor = window.HalftoneEditor || {});
