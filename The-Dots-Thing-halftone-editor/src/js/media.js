(function(ns) {
  function createMediaController(options) {
    let current = null;
    let objectUrl = null;
    let frameId = 0;

    function loadFile(file) {
      if (!file.type.startsWith('image/') && !file.type.startsWith('video/')) {
        return Promise.reject(new Error('Unsupported file type.'));
      }

      prepareForNewSource();

      objectUrl = URL.createObjectURL(file);

      if (file.type.startsWith('video/')) {
        return loadVideo(objectUrl, file.name, false);
      }

      if (file.type.startsWith('image/')) {
        return loadImage(objectUrl, file.name, false);
      }
    }

    function loadSample(sample) {
      prepareForNewSource();

      return trySampleSource(sample.sources, 0);
    }

    function trySampleSource(sources, index) {
      const source = sources[index];
      if (!source) {
        return Promise.reject(new Error('No sample source loaded.'));
      }

      return loadSource(source).catch((error) => {
        if (index + 1 < sources.length) {
          return trySampleSource(sources, index + 1);
        }
        return Promise.reject(error);
      });
    }

    function loadSource(source) {
      if (source.type === 'video') {
        return loadVideo(source.url, source.name, source.crossOrigin);
      }

      if (source.type === 'motion') {
        return loadMotion(source.motionId, source.name);
      }

      if (source.type === 'inlineSvg') {
        const svg = ns.SAMPLE_ASSETS && ns.SAMPLE_ASSETS[source.assetId];
        if (!svg) {
          return Promise.reject(new Error('Sample asset is missing.'));
        }

        return loadImage(toSvgDataUrl(svg), source.name, false);
      }

      if (source.type === 'image') {
        return loadImage(source.url, source.name, source.crossOrigin);
      }

      return Promise.reject(new Error('Unsupported sample type.'));
    }

    function prepareForNewSource() {
      cleanupObjectUrl();
      stopVideoLoop();
      pauseCurrentVideo();
    }

    function loadImage(url, name, useCrossOrigin) {
      return new Promise((resolve, reject) => {
        const image = new Image();

        if (useCrossOrigin) {
          image.crossOrigin = 'anonymous';
        }

        image.onload = function() {
          current = {
            element: image,
            type: 'image',
            name,
            width: image.naturalWidth,
            height: image.naturalHeight
          };
          resolve(current);
        };

        image.onerror = function() {
          reject(new Error('Image failed to load.'));
        };

        image.src = url;
      });
    }

    function loadMotion(motionId, name) {
      return new Promise((resolve, reject) => {
        const sample = ns.createMotionSample && ns.createMotionSample(motionId);
        if (!sample) {
          reject(new Error('Motion sample is missing.'));
          return;
        }

        current = {
          element: sample.canvas,
          type: 'motion',
          name,
          width: sample.width,
          height: sample.height,
          renderFrame: sample.renderFrame
        };

        current.renderFrame(performance.now());
        startVideoLoop();
        resolve(current);
      });
    }

    function loadVideo(url, name, useCrossOrigin) {
      return new Promise((resolve, reject) => {
        const video = document.createElement('video');

        if (useCrossOrigin) {
          video.crossOrigin = 'anonymous';
        }

        video.autoplay = true;
        video.loop = true;
        video.muted = true;
        video.playsInline = true;

        video.onloadeddata = function() {
          current = {
            element: video,
            type: 'video',
            name,
            width: video.videoWidth,
            height: video.videoHeight
          };

          video.play();
          startVideoLoop();
          resolve(current);
        };

        video.onerror = function() {
          reject(new Error('Video failed to load.'));
        };

        video.src = url;
      });
    }

    function startVideoLoop() {
      stopVideoLoop();

      function tick() {
        if (current && (current.type === 'video' || current.type === 'motion')) {
          if (current.renderFrame) {
            current.renderFrame(performance.now());
          }
          options.onFrame(current);
          frameId = requestAnimationFrame(tick);
        }
      }

      frameId = requestAnimationFrame(tick);
    }

    function stopVideoLoop() {
      if (frameId) {
        cancelAnimationFrame(frameId);
        frameId = 0;
      }
    }

    function pauseCurrentVideo() {
      if (current && current.type === 'video') {
        current.element.pause();
      }
    }

    function cleanupObjectUrl() {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
    }

    function getCurrent() {
      return current;
    }

    return {
      loadFile,
      loadSample,
      getCurrent,
      stopVideoLoop
    };
  }

  function toSvgDataUrl(svg) {
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }

  ns.createMediaController = createMediaController;
})(window.HalftoneEditor = window.HalftoneEditor || {});
