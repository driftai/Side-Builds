// Paste into DevTools Console while http://127.0.0.1:8797/ is open.
// Automatically inspects the inner Nuvio iframe or direct app window.
(() => {
  const frame = document.querySelector('#app');
  const targetDoc = frame?.contentDocument || document;
  const targetWin = frame?.contentWindow || window;

  let pluginSources = [];
  let pluginsEnabled = false;
  let installedAddons = [];
  try {
    const rawPlugins = targetWin.localStorage?.getItem('pluginSources');
    pluginSources = rawPlugins ? JSON.parse(rawPlugins) : [];
    pluginsEnabled = targetWin.localStorage?.getItem('pluginsEnabled') === 'true';
    const rawAddons = targetWin.localStorage?.getItem('installedAddonUrls');
    installedAddons = rawAddons ? JSON.parse(rawAddons) : [];
  } catch (_) {}

  const out = {
    location: targetWin.location.href,
    activeElement: targetDoc.activeElement?.outerHTML?.slice(0, 240),
    focusedNodes: [...targetDoc.querySelectorAll('.focusable.focused')].map(x => ({
      tag: x.tagName,
      action: x.dataset.action || x.getAttribute('data-action'),
      text: (x.textContent || '').trim().slice(0, 40),
      className: x.className
    })),
    detailFocusables: [...targetDoc.querySelectorAll('.series-detail-shell .focusable, .screen.is-active .focusable')].slice(0, 30).map(x => {
      const rect = x.getBoundingClientRect();
      const midX = rect.left + rect.width / 2;
      const midY = rect.top + rect.height / 2;
      const hitElement = (midX >= 0 && midY >= 0 && midX <= targetWin.innerWidth && midY <= targetWin.innerHeight)
        ? targetDoc.elementFromPoint(midX, midY)
        : null;
      const isOccluded = hitElement ? !x.contains(hitElement) && !hitElement.contains(x) : false;
      return {
        action: x.dataset.action || x.getAttribute('data-action'),
        text: (x.textContent || '').trim().slice(0, 40),
        cursor: targetWin.getComputedStyle(x).cursor,
        pointerEvents: targetWin.getComputedStyle(x).pointerEvents,
        hitElement: hitElement ? `${hitElement.tagName}.${hitElement.className.split(' ').join('.')}` : null,
        isOccluded,
        rect: rect.toJSON()
      };
    }),
    plugins: {
      enabled: pluginsEnabled,
      count: pluginSources.length,
      sources: pluginSources
    },
    addons: {
      count: Array.isArray(installedAddons) ? installedAddons.length : 0,
      urls: installedAddons
    }
  };

  console.table(out.detailFocusables);
  console.log('Nuvio Wrapper Diagnostic Snapshot:', out);
  return out;
})();
