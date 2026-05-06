(function(ns) {
  const WIDTH = 720;
  const HEIGHT = 540;

  function createMotionSample(id) {
    const canvas = document.createElement('canvas');
    canvas.width = WIDTH;
    canvas.height = HEIGHT;

    const context = canvas.getContext('2d');
    const render = getRenderer(id);
    if (!render) {
      return null;
    }

    return {
      canvas,
      width: WIDTH,
      height: HEIGHT,
      renderFrame: (time) => render(context, time / 1000)
    };
  }

  function getRenderer(id) {
    if (id === 'orbit') return renderOrbit;
    if (id === 'waves') return renderWaves;
    if (id === 'scanner') return renderScanner;
    if (id === 'pulse') return renderPulse;
    if (id === 'spiral') return renderSpiral;
    if (id === 'bounce') return renderBounce;
    if (id === 'stripes') return renderStripes;
    if (id === 'radar') return renderRadar;
    if (id === 'blobs') return renderBlobs;
    if (id === 'checker') return renderChecker;
    if (id === 'rain') return renderRain;
    if (id === 'rings') return renderRings;
    return null;
  }

  function renderOrbit(context, time) {
    fill(context, '#f6f7f9');
    drawRadialBackground(context, 360, 270, 420);

    for (let index = 0; index < 7; index++) {
      const angle = time * 0.9 + index * Math.PI * 2 / 7;
      const radius = 70 + index * 22;
      const x = 360 + Math.cos(angle) * radius;
      const y = 270 + Math.sin(angle * 1.2) * radius * 0.62;
      const shade = 32 + index * 24;
      context.fillStyle = `rgb(${shade}, ${shade + 8}, ${shade + 18})`;
      circle(context, x, y, 34 + index * 4);
    }
  }

  function renderWaves(context, time) {
    fill(context, '#eef1f5');

    for (let y = 0; y < HEIGHT; y += 18) {
      const shade = 40 + Math.floor(y / HEIGHT * 190);
      context.fillStyle = `rgb(${shade}, ${shade + 4}, ${shade + 10})`;
      context.beginPath();
      context.moveTo(0, y + 24);

      for (let x = 0; x <= WIDTH; x += 24) {
        context.lineTo(x, y + Math.sin(x * 0.018 + time * 2.2 + y * 0.03) * 24);
      }

      context.lineTo(WIDTH, y + 34);
      context.lineTo(WIDTH, y + 72);
      context.lineTo(0, y + 72);
      context.closePath();
      context.fill();
    }
  }

  function renderScanner(context, time) {
    const gradient = context.createLinearGradient(0, 0, WIDTH, HEIGHT);
    gradient.addColorStop(0, '#f7f8fa');
    gradient.addColorStop(1, '#6c7584');
    context.fillStyle = gradient;
    context.fillRect(0, 0, WIDTH, HEIGHT);

    const scannerX = (Math.sin(time * 1.6) * 0.5 + 0.5) * WIDTH;
    context.fillStyle = '#151a21';
    context.fillRect(scannerX - 36, 0, 72, HEIGHT);

    for (let index = 0; index < 12; index++) {
      context.fillStyle = index % 2 ? '#d9dee7' : '#303846';
      context.fillRect(index * 70 - ((time * 80) % 70), 110 + index * 13, 44, 260);
    }
  }

  function renderPulse(context, time) {
    fill(context, '#f4f5f7');

    for (let row = 0; row < 7; row++) {
      for (let column = 0; column < 9; column++) {
        const x = 76 + column * 72;
        const y = 66 + row * 68;
        const pulse = Math.sin(time * 2.4 + row * 0.9 + column * 0.65) * 0.5 + 0.5;
        const shade = Math.floor(24 + pulse * 214);
        context.fillStyle = `rgb(${shade}, ${shade}, ${shade + 4})`;
        circle(context, x, y, 16 + pulse * 28);
      }
    }
  }

  function renderSpiral(context, time) {
    fill(context, '#f2f4f7');
    context.save();
    context.translate(WIDTH / 2, HEIGHT / 2);
    context.rotate(time * 0.35);

    for (let index = 0; index < 90; index++) {
      const angle = index * 0.42 + time * 1.2;
      const radius = index * 4.2;
      const size = 10 + index * 0.22;
      const shade = Math.floor(24 + index * 2.35);
      context.fillStyle = `rgb(${shade}, ${shade + 4}, ${shade + 12})`;
      circle(context, Math.cos(angle) * radius, Math.sin(angle) * radius, size);
    }

    context.restore();
  }

  function renderBounce(context, time) {
    fill(context, '#f8fafc');

    for (let index = 0; index < 14; index++) {
      const speed = 0.9 + index * 0.08;
      const x = 70 + ((time * 70 * speed + index * 91) % (WIDTH - 140));
      const y = 80 + Math.abs(Math.sin(time * speed + index)) * (HEIGHT - 170);
      const shade = 28 + index * 13;
      context.fillStyle = `rgb(${shade}, ${shade + 6}, ${shade + 14})`;
      circle(context, x, y, 18 + (index % 5) * 8);
    }
  }

  function renderStripes(context, time) {
    fill(context, '#f0f2f6');
    context.save();
    context.translate(WIDTH / 2, HEIGHT / 2);
    context.rotate(-Math.PI / 8);

    for (let index = -20; index < 22; index++) {
      const x = index * 42 + (time * 80) % 42;
      const shade = 42 + ((index + 20) % 12) * 16;
      context.fillStyle = `rgb(${shade}, ${shade + 3}, ${shade + 9})`;
      context.fillRect(x, -HEIGHT, 24, HEIGHT * 2);
    }

    context.restore();
  }

  function renderRadar(context, time) {
    fill(context, '#e9edf3');
    context.save();
    context.translate(WIDTH / 2, HEIGHT / 2);

    for (let radius = 70; radius <= 260; radius += 48) {
      context.strokeStyle = `rgb(${80 + radius / 3}, ${86 + radius / 3}, ${96 + radius / 3})`;
      context.lineWidth = 10;
      context.beginPath();
      context.arc(0, 0, radius, 0, Math.PI * 2);
      context.stroke();
    }

    context.rotate(time * 1.6);
    const gradient = context.createLinearGradient(0, 0, 290, 0);
    gradient.addColorStop(0, '#111827');
    gradient.addColorStop(1, '#f8fafc');
    context.fillStyle = gradient;
    context.beginPath();
    context.moveTo(0, 0);
    context.arc(0, 0, 290, -0.18, 0.18);
    context.closePath();
    context.fill();
    context.restore();
  }

  function renderBlobs(context, time) {
    fill(context, '#f7f8fa');

    for (let index = 0; index < 8; index++) {
      const x = 360 + Math.sin(time * (0.7 + index * 0.08) + index) * (80 + index * 22);
      const y = 270 + Math.cos(time * (0.55 + index * 0.06) + index * 1.7) * (54 + index * 16);
      const radius = 54 + Math.sin(time * 1.4 + index) * 24;
      const shade = 34 + index * 24;
      context.fillStyle = `rgba(${shade}, ${shade + 7}, ${shade + 18}, 0.76)`;
      circle(context, x, y, radius);
    }
  }

  function renderChecker(context, time) {
    fill(context, '#f8fafc');
    const size = 58;
    const offset = (time * 36) % size;

    for (let row = -1; row < HEIGHT / size + 2; row++) {
      for (let column = -1; column < WIDTH / size + 2; column++) {
        const parity = (row + column) % 2;
        const shade = parity ? 54 : 196;
        context.fillStyle = `rgb(${shade}, ${shade + 3}, ${shade + 8})`;
        context.fillRect(column * size + offset, row * size - offset, size, size);
      }
    }
  }

  function renderRain(context, time) {
    const gradient = context.createLinearGradient(0, 0, 0, HEIGHT);
    gradient.addColorStop(0, '#f6f7f9');
    gradient.addColorStop(1, '#5e6877');
    context.fillStyle = gradient;
    context.fillRect(0, 0, WIDTH, HEIGHT);

    for (let index = 0; index < 90; index++) {
      const x = (index * 83 + time * 140) % (WIDTH + 100) - 50;
      const y = (index * 47 + time * 240) % (HEIGHT + 130) - 80;
      const shade = 24 + (index % 9) * 18;
      context.strokeStyle = `rgb(${shade}, ${shade + 5}, ${shade + 15})`;
      context.lineWidth = 4 + index % 4;
      context.beginPath();
      context.moveTo(x, y);
      context.lineTo(x - 24, y + 76);
      context.stroke();
    }
  }

  function renderRings(context, time) {
    fill(context, '#f5f6f8');
    context.save();
    context.translate(WIDTH / 2, HEIGHT / 2);

    for (let index = 0; index < 14; index++) {
      const radius = ((time * 72 + index * 42) % 620) + 20;
      const shade = Math.max(20, 230 - index * 14);
      context.strokeStyle = `rgb(${shade}, ${shade + 2}, ${shade + 8})`;
      context.lineWidth = 18;
      context.beginPath();
      context.arc(0, 0, radius, 0, Math.PI * 2);
      context.stroke();
    }

    context.restore();
  }

  function drawRadialBackground(context, x, y, radius) {
    const gradient = context.createRadialGradient(x, y, 20, x, y, radius);
    gradient.addColorStop(0, '#ffffff');
    gradient.addColorStop(0.62, '#aeb6c3');
    gradient.addColorStop(1, '#2b313c');
    context.fillStyle = gradient;
    context.fillRect(0, 0, WIDTH, HEIGHT);
  }

  function fill(context, color) {
    context.fillStyle = color;
    context.fillRect(0, 0, WIDTH, HEIGHT);
  }

  function circle(context, x, y, radius) {
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.fill();
  }

  ns.createMotionSample = createMotionSample;
})(window.HalftoneEditor = window.HalftoneEditor || {});
