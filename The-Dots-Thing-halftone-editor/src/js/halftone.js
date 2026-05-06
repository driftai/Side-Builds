(function(ns) {
  function resizeCanvasToMedia(canvas, width, height, zoomMode, container) {
    const scale = getPreviewScale(width, height, zoomMode, container);

    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
  }

  function getPreviewScale(width, height, zoomMode, container) {
    if (zoomMode !== 'fit') {
      return Number(zoomMode);
    }

    const bounds = getAvailableBounds(container);
    const boundsWidth = Math.max(1, bounds.width);
    const boundsHeight = Math.max(1, bounds.height);
    return Math.min(1, boundsWidth / width, boundsHeight / height);
  }

  function getAvailableBounds(container) {
    const rect = container.getBoundingClientRect();
    const style = window.getComputedStyle(container);
    const paddingX = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
    const paddingY = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    const viewport = window.visualViewport || window;
    const fallbackWidth = Math.max(1, viewport.width || window.innerWidth);
    const fallbackHeight = Math.max(1, viewport.height || window.innerHeight);

    return {
      width: (rect.width || fallbackWidth) - paddingX,
      height: (rect.height || fallbackHeight) - paddingY
    };
  }

  function clearCanvas(canvas, settings) {
    const context = canvas.getContext('2d');
    clearBackground(context, canvas.width, canvas.height, settings || ns.DEFAULTS);
  }

  function drawOriginal(source, targetCanvas) {
    const context = targetCanvas.getContext('2d');
    context.clearRect(0, 0, targetCanvas.width, targetCanvas.height);
    context.drawImage(source.element, 0, 0, targetCanvas.width, targetCanvas.height);
  }

  function generateHalftone(source, targetCanvas, settings) {
    const targetWidth = targetCanvas.width;
    const targetHeight = targetCanvas.height;
    const scale = targetWidth / source.width;
    const renderSettings = Object.assign({}, settings, {
      gridSize: Math.max(1, Math.round(settings.gridSize * scale))
    });

    const sourceCanvas = document.createElement('canvas');
    sourceCanvas.width = targetWidth;
    sourceCanvas.height = targetHeight;

    const sourceContext = sourceCanvas.getContext('2d', { willReadFrequently: true });
    sourceContext.drawImage(source.element, 0, 0, targetWidth, targetHeight);

    const imageData = sourceContext.getImageData(0, 0, targetWidth, targetHeight);
    const grayData = buildGrayscaleData(imageData.data, targetWidth, targetHeight, renderSettings);
    const cellData = buildCellData(grayData, targetWidth, targetHeight, renderSettings);

    drawDots(targetCanvas, cellData, renderSettings);
  }

  function buildGrayscaleData(pixels, width, height, settings) {
    const grayData = new Float32Array(width * height);
    const contrastFactor = (259 * (settings.contrast + 255)) / (255 * (259 - settings.contrast));

    for (let index = 0; index < pixels.length; index += 4) {
      const red = pixels[index];
      const green = pixels[index + 1];
      const blue = pixels[index + 2];
      let gray = 0.299 * red + 0.587 * green + 0.114 * blue;

      gray = contrastFactor * (gray - 128) + 128 + settings.brightness;
      gray = clamp(gray, 0, 255);
      gray = 255 * Math.pow(gray / 255, 1 / settings.gamma);

      grayData[index / 4] = gray;
    }

    return grayData;
  }

  function buildCellData(grayData, width, height, settings) {
    const gridSize = settings.gridSize;
    const columnCount = Math.ceil(width / gridSize);
    const rowCount = Math.ceil(height / gridSize);
    let values = new Float32Array(rowCount * columnCount);

    for (let row = 0; row < rowCount; row++) {
      for (let column = 0; column < columnCount; column++) {
        values[row * columnCount + column] = averageCell(grayData, width, height, gridSize, row, column);
      }
    }

    if (settings.smoothing > 0) {
      values = blurCells(values, rowCount, columnCount, settings.smoothing);
    }

    applyDither(values, rowCount, columnCount, settings.ditherType);
    return { values, rowCount, columnCount };
  }

  function averageCell(grayData, width, height, gridSize, row, column) {
    const startX = column * gridSize;
    const startY = row * gridSize;
    const endX = Math.min(startX + gridSize, width);
    const endY = Math.min(startY + gridSize, height);
    let sum = 0;
    let count = 0;

    for (let y = startY; y < endY; y++) {
      for (let x = startX; x < endX; x++) {
        sum += grayData[y * width + x];
        count++;
      }
    }

    return sum / count;
  }

  function blurCells(values, rowCount, columnCount, strength) {
    let result = new Float32Array(values);
    const passes = Math.floor(strength);

    for (let pass = 0; pass < passes; pass++) {
      result = blurOnce(result, rowCount, columnCount);
    }

    const fraction = strength - passes;
    if (fraction > 0) {
      for (let index = 0; index < result.length; index++) {
        result[index] = values[index] * (1 - fraction) + result[index] * fraction;
      }
    }

    return result;
  }

  function blurOnce(values, rowCount, columnCount) {
    const result = new Float32Array(values.length);

    for (let row = 0; row < rowCount; row++) {
      for (let column = 0; column < columnCount; column++) {
        let sum = 0;
        let count = 0;

        for (let yOffset = -1; yOffset <= 1; yOffset++) {
          for (let xOffset = -1; xOffset <= 1; xOffset++) {
            const sampleRow = row + yOffset;
            const sampleColumn = column + xOffset;

            if (sampleRow >= 0 && sampleRow < rowCount && sampleColumn >= 0 && sampleColumn < columnCount) {
              sum += values[sampleRow * columnCount + sampleColumn];
              count++;
            }
          }
        }

        result[row * columnCount + column] = sum / count;
      }
    }

    return result;
  }

  function applyDither(values, rowCount, columnCount, type) {
    if (type === 'FloydSteinberg') {
      applyFloydSteinberg(values, rowCount, columnCount);
    } else if (type === 'Ordered') {
      applyOrdered(values, rowCount, columnCount);
    } else if (type === 'Noise') {
      applyNoise(values);
    }
  }

  function applyFloydSteinberg(values, rowCount, columnCount) {
    for (let row = 0; row < rowCount; row++) {
      for (let column = 0; column < columnCount; column++) {
        const index = row * columnCount + column;
        const oldValue = values[index];
        const newValue = oldValue < 128 ? 0 : 255;
        const error = oldValue - newValue;

        values[index] = newValue;
        distributeError(values, row, column + 1, rowCount, columnCount, error * 7 / 16);
        distributeError(values, row + 1, column - 1, rowCount, columnCount, error * 3 / 16);
        distributeError(values, row + 1, column, rowCount, columnCount, error * 5 / 16);
        distributeError(values, row + 1, column + 1, rowCount, columnCount, error / 16);
      }
    }
  }

  function distributeError(values, row, column, rowCount, columnCount, amount) {
    if (row >= 0 && row < rowCount && column >= 0 && column < columnCount) {
      values[row * columnCount + column] += amount;
    }
  }

  function applyOrdered(values, rowCount, columnCount) {
    const matrix = [[0, 2], [3, 1]];

    for (let row = 0; row < rowCount; row++) {
      for (let column = 0; column < columnCount; column++) {
        const threshold = (matrix[row % 2][column % 2] + 0.5) * 255 / 4;
        const index = row * columnCount + column;
        values[index] = values[index] < threshold ? 0 : 255;
      }
    }
  }

  function applyNoise(values) {
    for (let index = 0; index < values.length; index++) {
      values[index] = values[index] + (Math.random() - 0.5) * 50 < 128 ? 0 : 255;
    }
  }

  function drawDots(canvas, cellData, settings) {
    const context = canvas.getContext('2d');
    const gridSize = settings.gridSize;
    const dotColor = settings.invert ? settings.backgroundColor : settings.dotColor;
    const angle = settings.dotAngle * Math.PI / 180;
    const jitterMax = gridSize * settings.dotJitter / 100 * 0.5;

    clearBackground(context, canvas.width, canvas.height, settings);

    for (let row = 0; row < cellData.rowCount; row++) {
      for (let column = 0; column < cellData.columnCount; column++) {
        const brightness = cellData.values[row * cellData.columnCount + column];
        const level = settings.invert ? brightness / 255 : 1 - brightness / 255;
        const radius = gridSize * 0.5 * level * settings.dotScale / 100;

        if (radius > 0.5) {
          const jitter = getJitter(row, column, jitterMax);
          ns.drawDotShape(
            context,
            column * gridSize + gridSize / 2 + jitter.x,
            row * gridSize + gridSize / 2 + jitter.y,
            radius,
            settings.dotShape,
            dotColor,
            angle,
            settings.dotOpacity / 100
          );
        }
      }
    }
  }

  function clearBackground(context, width, height, settings) {
    context.clearRect(0, 0, width, height);

    if (!settings.transparentBackground) {
      context.fillStyle = settings.invert ? settings.dotColor : settings.backgroundColor;
      context.fillRect(0, 0, width, height);
    }
  }

  function getJitter(row, column, maxOffset) {
    if (maxOffset <= 0) {
      return { x: 0, y: 0 };
    }

    return {
      x: (hashToUnit(row, column, 17) * 2 - 1) * maxOffset,
      y: (hashToUnit(row, column, 43) * 2 - 1) * maxOffset
    };
  }

  function hashToUnit(row, column, seed) {
    const value = Math.sin((row * 127.1 + column * 311.7 + seed * 74.7)) * 43758.5453;
    return value - Math.floor(value);
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  ns.resizeCanvasToMedia = resizeCanvasToMedia;
  ns.clearCanvas = clearCanvas;
  ns.drawOriginal = drawOriginal;
  ns.generateHalftone = generateHalftone;
})(window.HalftoneEditor = window.HalftoneEditor || {});
