(async () => {
  const status = document.querySelector('#status');
  const frame = document.querySelector('#app');

  function setStatus(text) {
    status.textContent = text || '';
    status.classList.toggle('is-visible', Boolean(text));
  }

  frame.setAttribute('allow', 'autoplay; encrypted-media; fullscreen; picture-in-picture; web-share');
  frame.setAttribute('allowfullscreen', '');

  let compatObserver = null;

  function installBrowserCompatibility() {
    try {
      const doc = frame.contentDocument;
      if (!doc) return;

      if (!doc.getElementById('__nuvio_wrapper_compat')) {
        const style = doc.createElement('style');
        style.id = '__nuvio_wrapper_compat';
        style.textContent = `
          /* Browser mode: disable the TV-only trailer control surface completely. */
          .detail-trailer-controls-overlay,
          .detail-trailer-controls-gradient,
          .detail-trailer-controls-gradient-top,
          .detail-trailer-controls-gradient-bottom,
          .detail-trailer-controls-top,
          .detail-trailer-controls-bottom {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
            outline: none !important;
            box-shadow: none !important;
            border: 0 !important;
            transform: none !important;
          }

          /* Ensure detail screen content and action buttons sit above the background */
          .series-detail-content {
            position: relative !important;
            z-index: 10 !important;
            pointer-events: auto !important;
          }

          .series-detail-actions,
          .series-primary-btn,
          .series-circle-btn,
          .series-season-btn,
          .series-episode-card,
          .detail-morelike-card,
          .series-cast-card,
          .series-insight-tab,
          .focusable,
          button,
          a,
          [data-action] {
            cursor: pointer !important;
            pointer-events: auto !important;
          }

          /* Trailer layer stays below content by default, only elevated when playing manually */
          .detail-trailer-layer,
          .detail-trailer-media,
          .detail-trailer-youtube,
          .detail-trailer-frame,
          .detail-trailer-video {
            pointer-events: none !important;
            z-index: 0 !important;
          }

          .detail-trailer-active.detail-trailer-manual .detail-trailer-layer,
          .detail-trailer-active.detail-trailer-manual .detail-trailer-media,
          .detail-trailer-active.detail-trailer-manual .detail-trailer-youtube,
          .detail-trailer-active.detail-trailer-manual .detail-trailer-frame,
          .detail-trailer-active.detail-trailer-manual .detail-trailer-video {
            pointer-events: auto !important;
            z-index: 30 !important;
          }

          /* Nuvio's TV focus engine can leave a focus ring/class on the trailer
             surface. Never draw one in browser mode. */
          .detail-trailer-layer .focused,
          .detail-trailer-layer :focus,
          .detail-trailer-layer :focus-visible {
            outline: none !important;
            box-shadow: none !important;
            border-color: transparent !important;
          }

          .detail-trailer-manual .series-detail-content {
            pointer-events: none !important;
          }
        `;
        doc.head.appendChild(style);
      }

      const neutralize = () => {
        try { doc.documentElement.classList.add("nuvio-browser-wrapper"); } catch (_) {}
        const overlays = doc.querySelectorAll(
          '.detail-trailer-controls-overlay, .detail-trailer-controls-gradient, .detail-trailer-controls-top, .detail-trailer-controls-bottom'
        );
        overlays.forEach((el) => {
          el.style.setProperty('display', 'none', 'important');
          el.style.setProperty('visibility', 'hidden', 'important');
          el.style.setProperty('pointer-events', 'none', 'important');
          el.setAttribute('tabindex', '-1');
          if (doc.activeElement === el) {
            try { el.blur(); } catch (_) {}
          }
        });

        const isManualTrailer = Boolean(doc.querySelector('.detail-trailer-active.detail-trailer-manual'));
        const mediaFrames = doc.querySelectorAll('.detail-trailer-frame, .detail-trailer-video');
        mediaFrames.forEach((el) => {
          if (isManualTrailer) {
            el.style.setProperty('pointer-events', 'auto', 'important');
            el.style.setProperty('z-index', '30', 'important');
            el.setAttribute('tabindex', '0');
            el.removeAttribute('aria-hidden');
          } else {
            el.style.setProperty('pointer-events', 'none', 'important');
            el.style.setProperty('z-index', '0', 'important');
            el.setAttribute('tabindex', '-1');
            el.setAttribute('aria-hidden', 'true');
          }
        });
      };

      neutralize();

      if (!compatObserver) {
        compatObserver = new MutationObserver(() => neutralize());
        compatObserver.observe(doc.documentElement, { childList: true, subtree: true });
      }
      window.__nuvioCompatInstalled = true;
    } catch (_) {
      // Inner app can be rebuilding its DOM; the iframe load/mutation observer will retry.
    }
  }

  function installBrowserClickBridge() {
    try {
      const doc = frame.contentDocument;
      if (!doc || doc.__nuvioWrapperClickBridge) return;

      const onPointerDown = () => {
        try { frame.contentWindow?.focus(); } catch (_) {}
      };

      doc.addEventListener('pointerdown', onPointerDown, true);
      doc.addEventListener('mousedown', onPointerDown, true);
      doc.__nuvioWrapperClickBridge = true;
    } catch (_) {}
  }

  async function load() {
    try {
      setStatus('Starting…');
      const response = await fetch('/__wrapper__/nuvio-entry', { cache: 'no-store' });
      const info = await response.json();
      if (!info.path) {
        setStatus(info.message || 'Nuvio browser build is missing. Run START_WRAPPER.bat to build it.');
        frame.removeAttribute('src');
        return;
      }

      frame.onload = () => {
        setStatus('');
        installBrowserCompatibility();
        installBrowserClickBridge();
        let count = 0;
        const timer = setInterval(() => {
          installBrowserCompatibility();
          if (++count > 40) clearInterval(timer);
        }, 250);
      };

      frame.src = info.path;
    } catch (error) {
      setStatus(`Wrapper error: ${error.message}`);
    }
  }

  const triggerAppBack = () => {
    try {
      const win = frame.contentWindow;
      const doc = frame.contentDocument;
      if (win?.NuvioRouter && typeof win.NuvioRouter.back === 'function') {
        win.NuvioRouter.back();
        return;
      }
      if (doc) {
        const escEvent = new KeyboardEvent('keydown', {
          key: 'Escape',
          code: 'Escape',
          keyCode: 27,
          which: 27,
          bubbles: true,
          cancelable: true
        });
        doc.dispatchEvent(escEvent);
        doc.body?.dispatchEvent(escEvent);
      }
    } catch (_) {}
  };

  const triggerAppHome = () => {
    try {
      const win = frame.contentWindow;
      if (win?.NuvioRouter && typeof win.NuvioRouter.navigate === 'function') {
        win.NuvioRouter.navigate('home');
      }
    } catch (_) {}
  };

  document.querySelector('#backNav')?.addEventListener('click', triggerAppBack);
  document.querySelector('#homeNav')?.addEventListener('click', triggerAppHome);

  document.querySelector('#reload')?.addEventListener('click', () => {
    try { frame.contentWindow.location.reload(); }
    catch (_) { frame.src = frame.src; }
  });

  document.querySelector('#full')?.addEventListener('click', () => frame.requestFullscreen?.());

  // Mouse Back Button (Button 3 / 4) support
  const handleMouseNav = (event) => {
    if (event.button === 3 || event.button === 4) {
      event.preventDefault();
      triggerAppBack();
    }
  };
  window.addEventListener('mouseup', handleMouseNav);

  window.addEventListener('message', (event) => {
    if (event.data === 'nuvio-ready') setStatus('');
  });

  load();
})();
