# Halftone Editor

A small dependency-free browser tool for turning images or videos into black-dot halftone artwork.

This project was cleaned up from a CodePen export and now keeps only the runnable core.

Original CodePen: <https://codepen.io/Mikhail-Bespalov/pen/dPyyZed>

## Run

Open `index.html` in a browser.

## Structure

- `index.html` - app markup and script/style wiring.
- `src/style.css` - app layout and controls styling.
- `src/js/config.js` - shared defaults.
- `src/js/sample-assets.js` - bundled inline sample artwork.
- `src/js/motion-samples.js` - local procedural motion samples.
- `src/js/dom.js` - DOM lookup, control reads, and small UI helpers.
- `src/js/presets.js` - preset validation and local storage.
- `src/js/preset-controls.js` - preset UI actions.
- `src/js/shapes.js` - dot shape drawing.
- `src/js/halftone.js` - canvas halftone generation.
- `src/js/media.js` - image/video loading and video frame loop.
- `src/js/app.js` - event binding and app orchestration.

## Current Features

- Sample picker with running horse, twelve local motion samples, and six static samples.
- Light and dim dark UI themes.
- Original/halftone preview toggle.
- Fit, 100%, 150%, and 200% preview zoom.
- Editable built-in presets and custom presets saved in browser local storage.
- 1x, 2x, and 4x PNG export sizing.
- Dot color, background color, opacity, scale, angle, jitter, transparent background, and inverted output options.
- Eight dot shapes: circle, square, diamond, triangle, hexagon, cross, horizontal line, and vertical line.
- Drag/drop and file picker media loading.

Preset storage reads the old `halftoneEditor.presets.v1` format and writes the expanded dot-style schema to `halftoneEditor.presets.v2`.

There is no build step and no generated `dist/` folder. Keep new behavior in focused files instead of growing one large script.
