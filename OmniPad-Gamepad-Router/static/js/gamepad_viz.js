/**
 * OmniPad Gamepad Visualizer (Vector SVG Renderer).
 * Real-time hardware controller visualization with analog deflection and trigger fill meters.
 */

class GamepadVisualizer {
  constructor(container, idPrefix = "pad") {
    this.container = typeof container === "string" ? document.getElementById(container) : container;
    this.idPrefix = idPrefix;
    this.render();
  }

  render() {
    if (!this.container) return;
    const p = this.idPrefix;
    this.container.innerHTML = `
      <svg class="gamepad-svg" viewBox="0 0 400 240" width="100%" height="100%" style="max-width: 380px;">
        <defs>
          <filter id="${p}-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        <!-- Controller Body Silhouette -->
        <path d="M 90 40 C 130 35, 270 35, 310 40 C 360 45, 390 120, 360 210 C 345 240, 305 230, 280 180 C 250 160, 150 160, 120 180 C 95 230, 55 240, 40 210 C 10 120, 40 45, 90 40 Z"
              fill="#12161f" stroke="rgba(255,255,255,0.12)" stroke-width="3" />

        <!-- Triggers / Bumpers -->
        <!-- LT Trigger Gauge & Bumper -->
        <rect id="${p}-lb" x="80" y="18" width="55" height="14" rx="4" fill="#1e2638" stroke="#334155" stroke-width="1.5" />
        <text x="107" y="29" fill="#94a3b8" font-size="9" font-family="monospace" text-anchor="middle" font-weight="bold">LB</text>
        
        <rect x="80" y="6" width="55" height="8" rx="3" fill="#0f172a" stroke="#334155" stroke-width="1" />
        <rect id="${p}-lt-bar" x="80" y="6" width="0" height="8" rx="3" fill="#00f0ff" />
        <text x="107" y="13" fill="#64748b" font-size="7" font-family="monospace" text-anchor="middle">LT</text>

        <!-- RT Trigger Gauge & Bumper -->
        <rect id="${p}-rb" x="265" y="18" width="55" height="14" rx="4" fill="#1e2638" stroke="#334155" stroke-width="1.5" />
        <text x="292" y="29" fill="#94a3b8" font-size="9" font-family="monospace" text-anchor="middle" font-weight="bold">RB</text>

        <rect x="265" y="6" width="55" height="8" rx="3" fill="#0f172a" stroke="#334155" stroke-width="1" />
        <rect id="${p}-rt-bar" x="265" y="6" width="0" height="8" rx="3" fill="#00f0ff" />
        <text x="292" y="13" fill="#64748b" font-size="7" font-family="monospace" text-anchor="middle">RT</text>

        <!-- Left Analog Stick (XInput standard placement) -->
        <g transform="translate(110, 95)">
          <circle cx="0" cy="0" r="28" fill="#0a0d14" stroke="#1e293b" stroke-width="2" />
          <circle id="${p}-ls-stick" cx="0" cy="0" r="18" fill="#1e293b" stroke="#38bdf8" stroke-width="2" />
          <text x="0" y="3" fill="#94a3b8" font-size="8" font-family="monospace" text-anchor="middle" font-weight="bold">LS</text>
        </g>

        <!-- D-Pad -->
        <g transform="translate(155, 150)">
          <!-- Background Base -->
          <rect x="-24" y="-8" width="48" height="16" rx="3" fill="#0f172a" stroke="#1e293b" stroke-width="1" />
          <rect x="-8" y="-24" width="16" height="48" rx="3" fill="#0f172a" stroke="#1e293b" stroke-width="1" />
          
          <!-- Directions -->
          <polygon id="${p}-dpad-up" points="-6,-10 6,-10 0,-20" fill="#334155" />
          <polygon id="${p}-dpad-down" points="-6,10 6,10 0,20" fill="#334155" />
          <polygon id="${p}-dpad-left" points="-10,-6 -10,6 -20,0" fill="#334155" />
          <polygon id="${p}-dpad-right" points="10,-6 10,6 20,0" fill="#334155" />
        </g>

        <!-- Center Controls -->
        <!-- Back / Select -->
        <circle id="${p}-back" cx="170" cy="95" r="7" fill="#1e293b" stroke="#334155" stroke-width="1.5" />
        <text x="170" y="112" fill="#64748b" font-size="7" font-family="monospace" text-anchor="middle">BACK</text>

        <!-- Guide / Logo -->
        <circle id="${p}-guide" cx="200" cy="80" r="11" fill="#0f172a" stroke="#00f0ff" stroke-width="2" />
        <text x="200" y="84" fill="#00f0ff" font-size="9" font-family="sans-serif" text-anchor="middle" font-weight="bold">X</text>

        <!-- Start -->
        <circle id="${p}-start" cx="230" cy="95" r="7" fill="#1e293b" stroke="#334155" stroke-width="1.5" />
        <text x="230" y="112" fill="#64748b" font-size="7" font-family="monospace" text-anchor="middle">START</text>

        <!-- Right Analog Stick -->
        <g transform="translate(245, 150)">
          <circle cx="0" cy="0" r="28" fill="#0a0d14" stroke="#1e293b" stroke-width="2" />
          <circle id="${p}-rs-stick" cx="0" cy="0" r="18" fill="#1e293b" stroke="#38bdf8" stroke-width="2" />
          <text x="0" y="3" fill="#94a3b8" font-size="8" font-family="monospace" text-anchor="middle" font-weight="bold">RS</text>
        </g>

        <!-- Face Action Buttons (X, Y, A, B) -->
        <g transform="translate(290, 95)">
          <!-- X Button (Left) -->
          <circle id="${p}-btn-x" cx="-20" cy="0" r="10" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5" />
          <text x="-20" y="4" fill="#38bdf8" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">X</text>

          <!-- Y Button (Top) -->
          <circle id="${p}-btn-y" cx="0" cy="-20" r="10" fill="#1e293b" stroke="#facc15" stroke-width="1.5" />
          <text x="0" y="-16" fill="#facc15" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">Y</text>

          <!-- B Button (Right) -->
          <circle id="${p}-btn-b" cx="20" cy="0" r="10" fill="#1e293b" stroke="#f87171" stroke-width="1.5" />
          <text x="20" y="4" fill="#f87171" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">B</text>

          <!-- A Button (Bottom) -->
          <circle id="${p}-btn-a" cx="0" cy="20" r="10" fill="#1e293b" stroke="#4ade80" stroke-width="1.5" />
          <text x="0" y="24" fill="#4ade80" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">A</text>
        </g>
      </svg>
    `;
    this.cacheElements();
  }

  cacheElements() {
    const p = this.idPrefix;
    const $ = (id) => document.getElementById(`${p}-${id}`);

    this.els = {
      btnA: $("btn-a"),
      btnB: $("btn-b"),
      btnX: $("btn-x"),
      btnY: $("btn-y"),
      btnLB: $("lb"),
      btnRB: $("rb"),
      barLT: $("lt-bar"),
      barRT: $("rt-bar"),
      btnStart: $("start"),
      btnBack: $("back"),
      btnGuide: $("guide"),
      dpadUp: $("dpad-up"),
      dpadDown: $("dpad-down"),
      dpadLeft: $("dpad-left"),
      dpadRight: $("dpad-right"),
      stickLS: $("ls-stick"),
      stickRS: $("rs-stick"),
    };
  }

  update(state) {
    if (!state || !this.els) return;
    const buttons = state.buttons || {};
    const axes = state.axes || {};

    const setPressed = (el, isPressed, activeColor = "#00f0ff") => {
      if (!el) return;
      el.setAttribute("fill", isPressed ? activeColor : "#1e293b");
    };

    // Face Buttons
    setPressed(this.els.btnA, buttons.A, "#4ade80");
    setPressed(this.els.btnB, buttons.B, "#f87171");
    setPressed(this.els.btnX, buttons.X, "#38bdf8");
    setPressed(this.els.btnY, buttons.Y, "#facc15");

    // Bumpers
    setPressed(this.els.btnLB, buttons.LB, "#00f0ff");
    setPressed(this.els.btnRB, buttons.RB, "#00f0ff");

    // Triggers (Analog fill bar)
    const lt = Math.max(0, Math.min(1, parseFloat(axes.lt || 0)));
    const rt = Math.max(0, Math.min(1, parseFloat(axes.rt || 0)));
    if (this.els.barLT) this.els.barLT.setAttribute("width", (lt * 55).toFixed(1));
    if (this.els.barRT) this.els.barRT.setAttribute("width", (rt * 55).toFixed(1));

    // Center Buttons
    setPressed(this.els.btnStart, buttons.START, "#00f0ff");
    setPressed(this.els.btnBack, buttons.BACK || buttons.SELECT, "#00f0ff");
    setPressed(this.els.btnGuide, buttons.GUIDE, "#00f0ff");

    // D-Pad
    setPressed(this.els.dpadUp, buttons.DPAD_UP, "#00f0ff");
    setPressed(this.els.dpadDown, buttons.DPAD_DOWN, "#00f0ff");
    setPressed(this.els.dpadLeft, buttons.DPAD_LEFT, "#00f0ff");
    setPressed(this.els.dpadRight, buttons.DPAD_RIGHT, "#00f0ff");

    // Left Stick (Displacement max radius 10px)
    const lx = Math.max(-1, Math.min(1, parseFloat(axes.lx || 0)));
    const ly = Math.max(-1, Math.min(1, parseFloat(axes.ly || 0)));
    if (this.els.stickLS) {
      this.els.stickLS.setAttribute("cx", (lx * 10).toFixed(1));
      this.els.stickLS.setAttribute("cy", (ly * -10).toFixed(1));
      setPressed(this.els.stickLS, buttons.LS, "#0284c7");
    }

    // Right Stick
    const rx = Math.max(-1, Math.min(1, parseFloat(axes.rx || 0)));
    const ry = Math.max(-1, Math.min(1, parseFloat(axes.ry || 0)));
    if (this.els.stickRS) {
      this.els.stickRS.setAttribute("cx", (rx * 10).toFixed(1));
      this.els.stickRS.setAttribute("cy", (ry * -10).toFixed(1));
      setPressed(this.els.stickRS, buttons.RS, "#0284c7");
    }
  }
}

window.GamepadVisualizer = GamepadVisualizer;
