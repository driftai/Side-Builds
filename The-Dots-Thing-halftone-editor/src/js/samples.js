(function(ns) {
  function motion(id, label) {
    return {
      id: id + 'Motion',
      label: 'Motion: ' + label,
      sources: [
        {
          name: label + ' motion sample',
          type: 'motion',
          motionId: id
        }
      ]
    };
  }

  function staticSample(id, label) {
    return {
      id,
      label,
      sources: [
        {
          name: label + ' sample',
          type: 'inlineSvg',
          assetId: id
        }
      ]
    };
  }

  ns.SAMPLES = [
    {
      id: 'horse',
      label: 'Running horse',
      sources: [
        {
          name: 'Running horse sample',
          type: 'video',
          url: 'https://i.imgur.com/5PrJCc2.mp4',
          crossOrigin: true
        },
        {
          name: 'Local horse fallback',
          type: 'inlineSvg',
          assetId: 'horse'
        }
      ]
    },
    motion('orbit', 'Orbit lights'),
    motion('waves', 'Wave bands'),
    motion('scanner', 'Scanner'),
    motion('pulse', 'Pulse field'),
    motion('spiral', 'Spiral tunnel'),
    motion('bounce', 'Bouncing dots'),
    motion('stripes', 'Diagonal stripes'),
    motion('radar', 'Radar sweep'),
    motion('blobs', 'Liquid blobs'),
    motion('checker', 'Checker drift'),
    motion('rain', 'Rain streaks'),
    motion('rings', 'Concentric rings'),
    staticSample('portrait', 'Portrait tones'),
    staticSample('gradient', 'Gradient bars'),
    staticSample('geometry', 'Geometry test'),
    staticSample('landscape', 'Landscape bands'),
    staticSample('radial', 'Radial light'),
    staticSample('type', 'Type test')
  ];

  ns.DEFAULT_SAMPLE_ID = 'horse';
})(window.HalftoneEditor = window.HalftoneEditor || {});
