(function(ns) {
  ns.DEFAULTS = {
    gridSize: 20,
    brightness: 20,
    contrast: 0,
    gamma: 1.0,
    smoothing: 0,
    ditherType: 'None',
    dotShape: 'circle',
    dotColor: '#111111',
    backgroundColor: '#ffffff',
    dotOpacity: 100,
    dotScale: 100,
    dotAngle: 0,
    dotJitter: 0,
    invert: false,
    transparentBackground: false,
    previewMode: 'halftone',
    zoomMode: 'fit',
    exportScale: 2
  };

  ns.PREVIEW_PADDING = 40;
  ns.PRESET_FIELDS = [
    'gridSize',
    'brightness',
    'contrast',
    'gamma',
    'smoothing',
    'ditherType',
    'dotShape',
    'dotColor',
    'backgroundColor',
    'dotOpacity',
    'dotScale',
    'dotAngle',
    'dotJitter',
    'invert',
    'transparentBackground'
  ];

  ns.PRESETS = {
    finePrint: {
      label: 'Fine print',
      settings: {
        gridSize: 8,
        brightness: 5,
        contrast: 25,
        gamma: 1.1,
        smoothing: 0,
        ditherType: 'None',
        dotShape: 'circle',
        dotColor: '#111111',
        backgroundColor: '#ffffff',
        dotOpacity: 100,
        dotScale: 90,
        dotAngle: 0,
        dotJitter: 0,
        invert: false,
        transparentBackground: false
      }
    },
    poster: {
      label: 'Poster',
      settings: {
        gridSize: 28,
        brightness: 20,
        contrast: 45,
        gamma: 0.9,
        smoothing: 1,
        ditherType: 'None',
        dotShape: 'circle',
        dotColor: '#101318',
        backgroundColor: '#f8fafc',
        dotOpacity: 100,
        dotScale: 115,
        dotAngle: 0,
        dotJitter: 0,
        invert: false,
        transparentBackground: false
      }
    },
    newsprint: {
      label: 'Newsprint',
      settings: {
        gridSize: 15,
        brightness: 10,
        contrast: 20,
        gamma: 1.0,
        smoothing: 0.5,
        ditherType: 'Ordered',
        dotShape: 'diamond',
        dotColor: '#171717',
        backgroundColor: '#f4f1e8',
        dotOpacity: 94,
        dotScale: 96,
        dotAngle: 45,
        dotJitter: 3,
        invert: false,
        transparentBackground: false
      }
    },
    highContrast: {
      label: 'High contrast',
      settings: {
        gridSize: 18,
        brightness: 0,
        contrast: 80,
        gamma: 1.0,
        smoothing: 0,
        ditherType: 'FloydSteinberg',
        dotShape: 'square',
        dotColor: '#050505',
        backgroundColor: '#ffffff',
        dotOpacity: 100,
        dotScale: 105,
        dotAngle: 0,
        dotJitter: 0,
        invert: false,
        transparentBackground: false
      }
    },
    softDots: {
      label: 'Soft dots',
      settings: {
        gridSize: 22,
        brightness: 30,
        contrast: -10,
        gamma: 1.3,
        smoothing: 2,
        ditherType: 'None',
        dotShape: 'circle',
        dotColor: '#2d3138',
        backgroundColor: '#fbfbf8',
        dotOpacity: 82,
        dotScale: 88,
        dotAngle: 0,
        dotJitter: 0,
        invert: false,
        transparentBackground: false
      }
    }
  };

})(window.HalftoneEditor = window.HalftoneEditor || {});
