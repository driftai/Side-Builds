(function(ns) {
  function drawDotShape(context, centerX, centerY, radius, shape, color, angle, opacity) {
    context.save();
    context.translate(centerX, centerY);
    context.rotate(angle || 0);
    context.globalAlpha = opacity === undefined ? 1 : opacity;
    context.fillStyle = color;

    if (shape === 'square') {
      context.fillRect(-radius, -radius, radius * 2, radius * 2);
    } else if (shape === 'diamond') {
      drawPolygon(context, radius * 1.35, 4, Math.PI / 4);
    } else if (shape === 'triangle') {
      drawPolygon(context, radius * 1.45, 3, -Math.PI / 2);
    } else if (shape === 'hexagon') {
      drawPolygon(context, radius * 1.12, 6, Math.PI / 6);
    } else if (shape === 'cross') {
      const arm = Math.max(1, radius * 0.55);
      context.fillRect(-radius, -arm / 2, radius * 2, arm);
      context.fillRect(-arm / 2, -radius, arm, radius * 2);
    } else if (shape === 'horizontal') {
      context.fillRect(-radius, -radius * 0.35, radius * 2, radius * 0.7);
    } else if (shape === 'vertical') {
      context.fillRect(-radius * 0.35, -radius, radius * 0.7, radius * 2);
    } else {
      context.beginPath();
      context.arc(0, 0, radius, 0, Math.PI * 2);
      context.fill();
    }

    context.restore();
  }

  function drawPolygon(context, radius, sides, rotation) {
    context.beginPath();

    for (let side = 0; side < sides; side++) {
      const angle = rotation + side * Math.PI * 2 / sides;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;

      if (side === 0) {
        context.moveTo(x, y);
      } else {
        context.lineTo(x, y);
      }
    }

    context.closePath();
    context.fill();
  }

  ns.drawDotShape = drawDotShape;
})(window.HalftoneEditor = window.HalftoneEditor || {});
