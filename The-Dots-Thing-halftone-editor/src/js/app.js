(function(ns) {
  document.addEventListener('DOMContentLoaded', init);

  function init() {
    const dom = ns.getDom();
    const media = ns.createMediaController({ onFrame: () => render(dom, media) });
    const presetManager = ns.createPresetManager();
    const renderDebounced = ns.debounce(() => render(dom, media), 120);

    ns.syncControls(dom, ns.DEFAULTS);
    ns.renderSampleOptions(dom, ns.SAMPLES, ns.DEFAULT_SAMPLE_ID);
    ns.clearCanvas(dom.canvas, ns.DEFAULTS);
    ns.setPreviewState(dom, 'Loading sample...');
    bindControls(dom, media, presetManager, renderDebounced);
    loadSelectedSample(dom, media);
  }

  function bindControls(dom, media, presetManager, renderDebounced) {
    const settlePreviewLayout = createPreviewLayoutSettler(dom, media);
    const controlInputs = [
      dom.gridSize,
      dom.brightness,
      dom.contrast,
      dom.gamma,
      dom.smoothing,
      dom.ditherType,
      dom.dotShape,
      dom.dotColor,
      dom.backgroundColor,
      dom.dotOpacity,
      dom.dotScale,
      dom.dotAngle,
      dom.dotJitter,
      dom.invertOutput,
      dom.transparentBackground
    ];

    ns.initTheme(dom);

    controlInputs.forEach((input) => {
      input.addEventListener('input', function() {
        ns.syncOutputs(dom);
        dom.canvasViewport.classList.toggle('is-transparent', ns.readSettings(dom).transparentBackground);
        renderDebounced();
      });
    });

    dom.zoomMode.addEventListener('change', function() {
      settlePreviewLayout();
    });

    dom.previewModeButtons.forEach((button) => {
      button.addEventListener('click', function() {
        ns.setPreviewMode(dom, button.dataset.previewMode);
        render(dom, media);
      });
    });

    ns.bindPresetControls(dom, presetManager, settlePreviewLayout);

    dom.fileUpload.addEventListener('change', function(event) {
      const file = event.target.files[0];
      if (file) {
        loadMedia(dom, media, file);
      }
    });

    dom.uploadDropzone.addEventListener('dragover', function(event) {
      event.preventDefault();
      dom.uploadDropzone.classList.add('is-dragging');
    });

    dom.uploadDropzone.addEventListener('dragleave', function() {
      dom.uploadDropzone.classList.remove('is-dragging');
    });

    dom.uploadDropzone.addEventListener('drop', function(event) {
      event.preventDefault();
      dom.uploadDropzone.classList.remove('is-dragging');

      const file = event.dataTransfer.files[0];
      if (file) {
        dom.fileUpload.files = event.dataTransfer.files;
        loadMedia(dom, media, file);
      }
    });

    dom.resetButton.addEventListener('click', function() {
      ns.syncControls(dom, ns.DEFAULTS);
      settlePreviewLayout();
    });

    dom.sampleButton.addEventListener('click', function() {
      loadSelectedSample(dom, media);
    });

    dom.saveButton.addEventListener('click', function() {
      exportPng(dom, media);
    });

    window.addEventListener('resize', ns.debounce(function() {
      settlePreviewLayout();
    }, 150));

    if ('ResizeObserver' in window) {
      const observer = new ResizeObserver(settlePreviewLayout);
      observer.observe(dom.canvasViewport);
    }
  }

  function loadMedia(dom, media, file) {
    ns.setStatus(dom, 'Loading ' + file.name + '...');
    ns.setPreviewState(dom, 'Loading media...');

    media.loadFile(file)
      .then(function(source) {
        dom.saveButton.disabled = false;
        ns.setPreviewState(dom, '');
        ns.setStatus(dom, source.name + ' loaded.');
        settlePreviewLayout(dom, media);
      })
      .catch(function(error) {
        dom.saveButton.disabled = true;
        ns.setPreviewState(dom, error.message);
        ns.setStatus(dom, error.message);
      });
  }

  function loadSelectedSample(dom, media) {
    const sample = getSelectedSample(dom);
    if (!sample) {
      ns.setStatus(dom, 'Choose a sample first.');
      return;
    }

    ns.setStatus(dom, 'Loading ' + sample.label + '...');
    ns.setPreviewState(dom, 'Loading sample...');

    media.loadSample(sample)
      .then(function(source) {
        dom.saveButton.disabled = false;
        ns.setPreviewState(dom, '');
        ns.setStatus(dom, source.name + ' loaded.');
        settlePreviewLayout(dom, media);
      })
      .catch(function(error) {
        dom.saveButton.disabled = true;
        ns.setPreviewState(dom, 'Sample unavailable. Choose media to begin.');
        ns.setStatus(dom, 'Sample unavailable. ' + error.message);
      });
  }

  function render(dom, media) {
    const source = media.getCurrent();
    const settings = ns.readSettings(dom);
    dom.canvasViewport.classList.toggle('is-transparent', settings.transparentBackground);

    if (!source) {
      ns.clearCanvas(dom.canvas, settings);
      return;
    }

    if (settings.previewMode === 'original') {
      ns.drawOriginal(source, dom.canvas);
    } else {
      ns.generateHalftone(source, dom.canvas, settings);
    }
  }

  function exportPng(dom, media) {
    const source = media.getCurrent();
    if (!source) {
      return;
    }

    const settings = ns.readSettings(dom);
    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = Math.max(1, Math.round(source.width * settings.exportScale));
    exportCanvas.height = Math.max(1, Math.round(source.height * settings.exportScale));

    ns.generateHalftone(source, exportCanvas, settings);

    const link = document.createElement('a');
    link.href = exportCanvas.toDataURL('image/png');
    link.download = 'halftone.png';
    link.click();
  }

  function resizePreview(dom, media) {
    const source = media.getCurrent();
    if (!source) {
      return;
    }

    ns.resizeCanvasToMedia(dom.canvas, source.width, source.height, dom.zoomMode.value, dom.canvasViewport);
  }

  function getSelectedSample(dom) {
    return ns.SAMPLES.find((sample) => sample.id === dom.sampleSelect.value) || ns.SAMPLES[0];
  }

  function settlePreviewLayout(dom, media) {
    resizePreview(dom, media);
    render(dom, media);

    requestAnimationFrame(function() {
      resizePreview(dom, media);
      render(dom, media);
    });
  }

  function createPreviewLayoutSettler(dom, media) {
    let timerId = 0;

    return function() {
      settlePreviewLayout(dom, media);
      clearTimeout(timerId);
      timerId = setTimeout(function() {
        settlePreviewLayout(dom, media);
      }, 120);
    };
  }
})(window.HalftoneEditor = window.HalftoneEditor || {});
