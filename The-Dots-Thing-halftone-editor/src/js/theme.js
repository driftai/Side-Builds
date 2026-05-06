(function(ns) {
  const STORAGE_KEY = 'halftoneEditor.theme.v1';
  const THEMES = ['light', 'dark'];

  function initTheme(dom) {
    const savedTheme = readTheme();
    applyTheme(dom, savedTheme);

    dom.themeMode.addEventListener('change', function() {
      applyTheme(dom, dom.themeMode.value);
      localStorage.setItem(STORAGE_KEY, dom.themeMode.value);
    });
  }

  function readTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (THEMES.includes(saved)) {
      return saved;
    }

    return 'light';
  }

  function applyTheme(dom, theme) {
    const cleanTheme = THEMES.includes(theme) ? theme : 'light';
    document.documentElement.dataset.theme = cleanTheme;
    dom.themeMode.value = cleanTheme;
  }

  ns.initTheme = initTheme;
})(window.HalftoneEditor = window.HalftoneEditor || {});
