(function(ns) {
  const STORAGE_KEY = 'halftoneEditor.presets.v2';
  const LEGACY_STORAGE_KEY = 'halftoneEditor.presets.v1';
  const SCHEMA_VERSION = 2;
  const DITHER_TYPES = ['None', 'FloydSteinberg', 'Ordered', 'Noise'];
  const DOT_SHAPES = ['circle', 'square', 'diamond', 'triangle', 'hexagon', 'cross', 'horizontal', 'vertical'];

  function createPresetManager() {
    let store = loadStore();

    function list() {
      const builtIns = Object.keys(ns.PRESETS).map((id) => {
        const base = ns.PRESETS[id];
        const override = store.overrides[id];

        return {
          id,
          kind: 'builtIn',
          label: base.label,
          isEdited: Boolean(override),
          settings: Object.assign({}, base.settings, override && override.settings)
        };
      });

      return builtIns.concat(store.custom.map((preset) => Object.assign({ kind: 'custom' }, preset)));
    }

    function get(id) {
      return list().find((preset) => preset.id === id) || null;
    }

    function saveSelected(id, settings) {
      const selected = get(id);
      if (!selected) {
        return null;
      }

      const cleanSettings = sanitizeSettings(settings);
      const timestamp = new Date().toISOString();

      if (selected.kind === 'custom') {
        store.custom = store.custom.map((preset) => {
          if (preset.id !== id) {
            return preset;
          }

          return Object.assign({}, preset, {
            settings: cleanSettings,
            updatedAt: timestamp
          });
        });
      } else {
        store.overrides[id] = {
          settings: cleanSettings,
          updatedAt: timestamp
        };
      }

      persist();
      return get(id);
    }

    function create(label, settings) {
      const cleanLabel = sanitizeLabel(label);
      if (!cleanLabel) {
        return null;
      }

      const timestamp = new Date().toISOString();
      const preset = {
        id: createId(cleanLabel),
        label: cleanLabel,
        settings: sanitizeSettings(settings),
        createdAt: timestamp,
        updatedAt: timestamp
      };

      store.custom.push(preset);
      persist();
      return Object.assign({ kind: 'custom' }, preset);
    }

    function resetOrDelete(id) {
      const selected = get(id);
      if (!selected) {
        return false;
      }

      if (selected.kind === 'custom') {
        store.custom = store.custom.filter((preset) => preset.id !== id);
      } else {
        delete store.overrides[id];
      }

      persist();
      return true;
    }

    function persist() {
      store = sanitizeStore(store);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    }

    return {
      list,
      get,
      saveSelected,
      create,
      resetOrDelete
    };
  }

  function loadStore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY);
      if (!raw) {
        return getEmptyStore();
      }

      const parsed = JSON.parse(raw);
      return sanitizeStore(parsed);
    } catch (error) {
      return getEmptyStore();
    }
  }

  function getEmptyStore() {
    return {
      version: SCHEMA_VERSION,
      overrides: {},
      custom: []
    };
  }

  function sanitizeStore(value) {
    const store = getEmptyStore();
    const source = value && typeof value === 'object' ? value : {};
    const overrides = source.overrides && typeof source.overrides === 'object' ? source.overrides : {};
    const custom = Array.isArray(source.custom) ? source.custom : [];

    Object.keys(overrides).forEach((id) => {
      if (ns.PRESETS[id] && overrides[id] && typeof overrides[id] === 'object') {
        store.overrides[id] = {
          settings: sanitizeSettings(overrides[id].settings),
          updatedAt: String(overrides[id].updatedAt || '')
        };
      }
    });

    custom.forEach((preset) => {
      if (!preset || typeof preset !== 'object') {
        return;
      }

      const label = sanitizeLabel(preset.label);
      if (!label) {
        return;
      }

      store.custom.push({
        id: sanitizeId(preset.id || createId(label)),
        label,
        settings: sanitizeSettings(preset.settings),
        createdAt: String(preset.createdAt || ''),
        updatedAt: String(preset.updatedAt || '')
      });
    });

    return store;
  }

  function sanitizeSettings(settings) {
    const source = Object.assign({}, ns.DEFAULTS, settings || {});

    return {
      gridSize: clampNumber(source.gridSize, 5, 50, ns.DEFAULTS.gridSize),
      brightness: clampNumber(source.brightness, -100, 100, ns.DEFAULTS.brightness),
      contrast: clampNumber(source.contrast, -100, 100, ns.DEFAULTS.contrast),
      gamma: clampNumber(source.gamma, 0.1, 3, ns.DEFAULTS.gamma),
      smoothing: clampNumber(source.smoothing, 0, 5, ns.DEFAULTS.smoothing),
      ditherType: DITHER_TYPES.includes(source.ditherType) ? source.ditherType : ns.DEFAULTS.ditherType,
      dotShape: DOT_SHAPES.includes(source.dotShape) ? source.dotShape : ns.DEFAULTS.dotShape,
      dotColor: sanitizeColor(source.dotColor, ns.DEFAULTS.dotColor),
      backgroundColor: sanitizeColor(source.backgroundColor, ns.DEFAULTS.backgroundColor),
      dotOpacity: clampNumber(source.dotOpacity, 10, 100, ns.DEFAULTS.dotOpacity),
      dotScale: clampNumber(source.dotScale, 50, 140, ns.DEFAULTS.dotScale),
      dotAngle: clampNumber(source.dotAngle, -90, 90, ns.DEFAULTS.dotAngle),
      dotJitter: clampNumber(source.dotJitter, 0, 50, ns.DEFAULTS.dotJitter),
      invert: Boolean(source.invert),
      transparentBackground: Boolean(source.transparentBackground)
    };
  }

  function sanitizeColor(value, fallback) {
    const color = String(value || '').trim();
    return /^#[0-9a-fA-F]{6}$/.test(color) ? color.toLowerCase() : fallback;
  }

  function sanitizeLabel(label) {
    return String(label || '').trim().replace(/\s+/g, ' ').slice(0, 40);
  }

  function sanitizeId(id) {
    const clean = String(id || '').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 60);
    return clean || createId('preset');
  }

  function createId(label) {
    return 'custom-' + label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 30) + '-' + Date.now();
  }

  function clampNumber(value, min, max, fallback) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return fallback;
    }

    return Math.max(min, Math.min(max, number));
  }

  ns.createPresetManager = createPresetManager;
})(window.HalftoneEditor = window.HalftoneEditor || {});
