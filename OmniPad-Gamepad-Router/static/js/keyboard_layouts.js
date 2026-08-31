/**
 * OmniPad — Keyboard Layout Definitions & Controller Badges.
 */

const KEYBOARD_LAYOUTS = {
  standard_full: [
    [
      { code: "Escape", label: "ESC", class: "vk-w-1-25" },
      { spacer: true },
      { code: "F1", label: "F1" }, { code: "F2", label: "F2" }, { code: "F3", label: "F3" }, { code: "F4", label: "F4" },
      { spacer: true },
      { code: "F5", label: "F5" }, { code: "F6", label: "F6" }, { code: "F7", label: "F7" }, { code: "F8", label: "F8" },
      { spacer: true },
      { code: "F9", label: "F9" }, { code: "F10", label: "F10" }, { code: "F11", label: "F11" }, { code: "F12", label: "F12" },
      { spacer: true },
      { code: "PrintScreen", label: "PRT" }
    ],
    [
      { code: "Backquote", label: "`", sub: "~" },
      { code: "Digit1", label: "1", sub: "!" }, { code: "Digit2", label: "2", sub: "@" },
      { code: "Digit3", label: "3", sub: "#" }, { code: "Digit4", label: "4", sub: "$" },
      { code: "Digit5", label: "5", sub: "%" }, { code: "Digit6", label: "6", sub: "^" },
      { code: "Digit7", label: "7", sub: "&" }, { code: "Digit8", label: "8", sub: "*" },
      { code: "Digit9", label: "9", sub: "(" }, { code: "Digit0", label: "0", sub: ")" },
      { code: "Minus", label: "-", sub: "_" }, { code: "Equal", label: "=", sub: "+" },
      { code: "Backspace", label: "BACKSPACE", class: "vk-w-2" }
    ],
    [
      { code: "Tab", label: "TAB", class: "vk-w-1-5" },
      { code: "KeyQ", label: "Q" }, { code: "KeyW", label: "W" }, { code: "KeyE", label: "E" },
      { code: "KeyR", label: "R" }, { code: "KeyT", label: "T" }, { code: "KeyY", label: "Y" },
      { code: "KeyU", label: "U" }, { code: "KeyI", label: "I" }, { code: "KeyO", label: "O" },
      { code: "KeyP", label: "P" }, { code: "BracketLeft", label: "[", sub: "{" },
      { code: "BracketRight", label: "]", sub: "}" }, { code: "Backslash", label: "\\", sub: "|", class: "vk-w-1-5" }
    ],
    [
      { code: "CapsLock", label: "CAPS", class: "vk-w-1-75" },
      { code: "KeyA", label: "A" }, { code: "KeyS", label: "S" }, { code: "KeyD", label: "D" },
      { code: "KeyF", label: "F" }, { code: "KeyG", label: "G" }, { code: "KeyH", label: "H" },
      { code: "KeyJ", label: "J" }, { code: "KeyK", label: "K" }, { code: "KeyL", label: "L" },
      { code: "Semicolon", label: ";", sub: ":" }, { code: "Quote", label: "'", sub: "\"" },
      { code: "Enter", label: "ENTER", class: "vk-w-2-25" }
    ],
    [
      { code: "ShiftLeft", label: "SHIFT", class: "vk-w-2-25" },
      { code: "KeyZ", label: "Z" }, { code: "KeyX", label: "X" }, { code: "KeyC", label: "C" },
      { code: "KeyV", label: "V" }, { code: "KeyB", label: "B" }, { code: "KeyN", label: "N" },
      { code: "KeyM", label: "M" }, { code: "Comma", label: ",", sub: "<" },
      { code: "Period", label: ".", sub: ">" }, { code: "Slash", label: "/", sub: "?" },
      { code: "ShiftRight", label: "SHIFT", class: "vk-w-1-75" },
      { code: "ArrowUp", label: "▲" }
    ],
    [
      { code: "ControlLeft", label: "CTRL", class: "vk-w-1-5" },
      { code: "MetaLeft", label: "WIN", class: "vk-w-1-25" },
      { code: "AltLeft", label: "ALT", class: "vk-w-1-25" },
      { code: "Space", label: "SPACE", class: "vk-w-space" },
      { code: "AltRight", label: "ALT", class: "vk-w-1" },
      { code: "ControlRight", label: "CTRL", class: "vk-w-1" },
      { code: "ArrowLeft", label: "◀" },
      { code: "ArrowDown", label: "▼" },
      { code: "ArrowRight", label: "▶" }
    ]
  ],

  wasd_fighter: [
    [
      { code: "Escape", label: "ESC" },
      { code: "Digit1", label: "1" }, { code: "Digit2", label: "2" }, { code: "Digit3", label: "3" },
      { code: "Digit4", label: "4" }, { code: "Digit5", label: "5" }, { code: "Digit6", label: "6" },
      { code: "Backspace", label: "BACK / SHARE", class: "vk-w-1-5" },
      { spacer: true },
      { code: "KeyU", label: "U (A/✕/LK)", class: "vk-highlight-action" },
      { code: "KeyI", label: "I (B/○/MK)", class: "vk-highlight-action" },
      { code: "KeyO", label: "O (RT/R2/HK)", class: "vk-highlight-action" }
    ],
    [
      { code: "Tab", label: "TAB" },
      { code: "KeyQ", label: "Q" },
      { code: "KeyW", label: "W (UP)", class: "vk-highlight-move" },
      { code: "KeyE", label: "E" },
      { code: "KeyR", label: "R" },
      { code: "KeyT", label: "T" },
      { code: "KeyY", label: "Y" },
      { spacer: true },
      { code: "KeyJ", label: "J (X/□/LP)", class: "vk-highlight-action" },
      { code: "KeyK", label: "K (Y/△/MP)", class: "vk-highlight-action" },
      { code: "KeyL", label: "L (RB/R1/HP)", class: "vk-highlight-action" }
    ],
    [
      { code: "CapsLock", label: "CAPS (L3)" },
      { code: "KeyA", label: "A (LEFT)", class: "vk-highlight-move" },
      { code: "KeyS", label: "S (DOWN)", class: "vk-highlight-move" },
      { code: "KeyD", label: "D (RIGHT)", class: "vk-highlight-move" },
      { code: "KeyF", label: "F" },
      { code: "KeyG", label: "G" },
      { code: "KeyH", label: "H" },
      { spacer: true },
      { code: "Semicolon", label: ";" },
      { code: "Quote", label: "'" },
      { code: "Enter", label: "START / OPTIONS", class: "vk-w-2" }
    ],
    [
      { code: "ShiftLeft", label: "SHIFT (LT / L2 / DI)", class: "vk-w-2 vk-highlight-modifier" },
      { code: "KeyZ", label: "Z" }, { code: "KeyX", label: "X" }, { code: "KeyC", label: "C" },
      { code: "KeyV", label: "V" }, { code: "KeyB", label: "B" }, { code: "KeyN", label: "N" },
      { code: "KeyM", label: "M (MAP)" },      { spacer: true },
      { code: "ArrowUp", label: "▲" },
      { code: "ShiftRight", label: "SHIFT (LT / L2)", class: "vk-w-1-5" }
    ],
    [
      { code: "ControlLeft", label: "CTRL (RT / R2)", class: "vk-w-1-5 vk-highlight-modifier" },
      { code: "AltLeft", label: "ALT" },
      { code: "Space", label: "SPACE (LB / L1 / PARRY)", class: "vk-w-space vk-highlight-modifier" },
      { code: "AltRight", label: "ALT" },
      { spacer: true },
      { code: "ArrowLeft", label: "◀" }, { code: "ArrowDown", label: "▼" }, { code: "ArrowRight", label: "▶" }
    ]
  ],

  arrow_numpad: [
    [
      { code: "Escape", label: "ESC" },
      { spacer: true },
      { code: "NumLock", label: "NUM" }, { code: "NumpadDivide", label: "/" },
      { code: "NumpadMultiply", label: "*" }, { code: "NumpadSubtract", label: "-" }
    ],
    [
      { code: "ArrowUp", label: "▲ (UP)", class: "vk-w-1-5 vk-highlight-move" },
      { spacer: true },
      { code: "Numpad7", label: "7", class: "vk-highlight-action" },
      { code: "Numpad8", label: "8", class: "vk-highlight-action" },
      { code: "Numpad9", label: "9", class: "vk-highlight-action" },
      { code: "NumpadAdd", label: "+", class: "vk-w-1-25" }
    ],
    [
      { code: "ArrowLeft", label: "◀ (L)", class: "vk-highlight-move" },
      { code: "ArrowDown", label: "▼ (D)", class: "vk-highlight-move" },
      { code: "ArrowRight", label: "▶ (R)", class: "vk-highlight-move" },
      { spacer: true },
      { code: "Numpad4", label: "4", class: "vk-highlight-action" },
      { code: "Numpad5", label: "5", class: "vk-highlight-action" },
      { code: "Numpad6", label: "6", class: "vk-highlight-action" },
      { code: "NumpadEnter", label: "ENTER", class: "vk-w-1-25 vk-highlight-modifier" }
    ],
    [
      { code: "ShiftRight", label: "SHIFT", class: "vk-w-2 vk-highlight-modifier" },
      { code: "ControlRight", label: "CTRL", class: "vk-w-1-5 vk-highlight-modifier" },
      { spacer: true },
      { code: "Numpad1", label: "1", class: "vk-highlight-action" },
      { code: "Numpad2", label: "2", class: "vk-highlight-action" },
      { code: "Numpad3", label: "3", class: "vk-highlight-action" },
      { code: "NumpadDecimal", label: "." }
    ],
    [
      { code: "Space", label: "SPACEBAR", class: "vk-w-space vk-highlight-modifier" },
      { spacer: true },
      { code: "Numpad0", label: "0 (SPACE / JUMP)", class: "vk-w-2 vk-highlight-modifier" }
    ]
  ],

  compact_60: [
    [
      { code: "Escape", label: "ESC" },
      { code: "Digit1", label: "1" }, { code: "Digit2", label: "2" }, { code: "Digit3", label: "3" },
      { code: "Digit4", label: "4" }, { code: "Digit5", label: "5" }, { code: "Digit6", label: "6" },
      { code: "Digit7", label: "7" }, { code: "Digit8", label: "8" }, { code: "Digit9", label: "9" },
      { code: "Digit0", label: "0" }, { code: "Backspace", label: "⌫", class: "vk-w-1-5" }
    ],
    [
      { code: "Tab", label: "TAB" },
      { code: "KeyQ", label: "Q" }, { code: "KeyW", label: "W", class: "vk-highlight-move" }, { code: "KeyE", label: "E" },
      { code: "KeyR", label: "R" }, { code: "KeyT", label: "T" }, { code: "KeyY", label: "Y" },
      { code: "KeyU", label: "U", class: "vk-highlight-action" }, { code: "KeyI", label: "I", class: "vk-highlight-action" },
      { code: "KeyO", label: "O", class: "vk-highlight-action" }, { code: "KeyP", label: "P" }, { code: "Enter", label: "↵", class: "vk-w-1-5" }
    ],
    [
      { code: "CapsLock", label: "CAPS" },
      { code: "KeyA", label: "A", class: "vk-highlight-move" }, { code: "KeyS", label: "S", class: "vk-highlight-move" },
      { code: "KeyD", label: "D", class: "vk-highlight-move" }, { code: "KeyF", label: "F" }, { code: "KeyG", label: "G" },
      { code: "KeyH", label: "H" }, { code: "KeyJ", label: "J", class: "vk-highlight-action" },
      { code: "KeyK", label: "K", class: "vk-highlight-action" }, { code: "KeyL", label: "L", class: "vk-highlight-action" },
      { code: "Quote", label: "'" }
    ],
    [
      { code: "ShiftLeft", label: "SHIFT", class: "vk-w-1-75 vk-highlight-modifier" },
      { code: "KeyZ", label: "Z" }, { code: "KeyX", label: "X" }, { code: "KeyC", label: "C" },
      { code: "KeyV", label: "V" }, { code: "KeyB", label: "B" }, { code: "KeyN", label: "N" },
      { code: "KeyM", label: "M" }, { code: "ArrowUp", label: "▲" },
      { code: "ShiftRight", label: "SHIFT", class: "vk-w-1-75 vk-highlight-modifier" }
    ],
    [
      { code: "ControlLeft", label: "CTRL", class: "vk-w-1-25 vk-highlight-modifier" },
      { code: "AltLeft", label: "ALT" },
      { code: "Space", label: "SPACE", class: "vk-w-space vk-highlight-modifier" },
      { code: "ArrowLeft", label: "◀" }, { code: "ArrowDown", label: "▼" }, { code: "ArrowRight", label: "▶" }
    ]
  ]
};

const CONTROLLER_BADGES = {
  xbox_controller: {
    "KeyW": { badge: "LS ↑", highlight: "vk-highlight-move" },
    "KeyA": { badge: "LS ←", highlight: "vk-highlight-move" },
    "KeyS": { badge: "LS ↓", highlight: "vk-highlight-move" },
    "KeyD": { badge: "LS →", highlight: "vk-highlight-move" },
    "Space": { badge: "A / ✕", highlight: "vk-highlight-action" },
    "KeyE": { badge: "X / □", highlight: "vk-highlight-action" },
    "KeyQ": { badge: "Y / △", highlight: "vk-highlight-action" },
    "KeyR": { badge: "B / ○", highlight: "vk-highlight-action" },
    "ShiftLeft": { badge: "LT / L2", highlight: "vk-highlight-modifier" },
    "ShiftRight": { badge: "LT / L2", highlight: "vk-highlight-modifier" },
    "ControlLeft": { badge: "RT / R2", highlight: "vk-highlight-modifier" },
    "ControlRight": { badge: "RT / R2", highlight: "vk-highlight-modifier" },
    "KeyZ": { badge: "LB / L1", highlight: "vk-highlight-modifier" },
    "KeyC": { badge: "RB / R1", highlight: "vk-highlight-modifier" },
    "Escape": { badge: "BACK / SHARE", highlight: "vk-highlight-action" },
    "Enter": { badge: "START / OPT", highlight: "vk-highlight-action" },
    "F1": { badge: "GUIDE / PS", highlight: "vk-highlight-action" },
    "CapsLock": { badge: "L3", highlight: "vk-highlight-action" },
    "KeyF": { badge: "L3", highlight: "vk-highlight-action" },
    "KeyG": { badge: "R3", highlight: "vk-highlight-action" },
    "ArrowUp": { badge: "RS ↑", highlight: "vk-highlight-move" },
    "ArrowDown": { badge: "RS ↓", highlight: "vk-highlight-move" },
    "ArrowLeft": { badge: "RS ←", highlight: "vk-highlight-move" },
    "ArrowRight": { badge: "RS →", highlight: "vk-highlight-move" },
    "Digit1": { badge: "D↑", highlight: "vk-highlight-move" },
    "Digit2": { badge: "D↓", highlight: "vk-highlight-move" },
    "Digit3": { badge: "D←", highlight: "vk-highlight-move" },
    "Digit4": { badge: "D→", highlight: "vk-highlight-move" }
  },
  playstation_controller: {
    "KeyW": { badge: "LS ↑", highlight: "vk-highlight-move" },
    "KeyA": { badge: "LS ←", highlight: "vk-highlight-move" },
    "KeyS": { badge: "LS ↓", highlight: "vk-highlight-move" },
    "KeyD": { badge: "LS →", highlight: "vk-highlight-move" },
    "Space": { badge: "✕ / A", highlight: "vk-highlight-action" },
    "KeyE": { badge: "□ / X", highlight: "vk-highlight-action" },
    "KeyQ": { badge: "△ / Y", highlight: "vk-highlight-action" },
    "KeyR": { badge: "○ / B", highlight: "vk-highlight-action" },
    "ShiftLeft": { badge: "L2 / LT", highlight: "vk-highlight-modifier" },
    "ShiftRight": { badge: "L2 / LT", highlight: "vk-highlight-modifier" },
    "ControlLeft": { badge: "R2 / RT", highlight: "vk-highlight-modifier" },
    "ControlRight": { badge: "R2 / RT", highlight: "vk-highlight-modifier" },
    "KeyZ": { badge: "L1 / LB", highlight: "vk-highlight-modifier" },
    "KeyC": { badge: "R1 / RB", highlight: "vk-highlight-modifier" },
    "Escape": { badge: "SHARE / BACK", highlight: "vk-highlight-action" },
    "Enter": { badge: "OPT / START", highlight: "vk-highlight-action" },
    "F1": { badge: "PS / GUIDE", highlight: "vk-highlight-action" },
    "CapsLock": { badge: "L3", highlight: "vk-highlight-action" },
    "KeyF": { badge: "L3", highlight: "vk-highlight-action" },
    "KeyG": { badge: "R3", highlight: "vk-highlight-action" },
    "ArrowUp": { badge: "RS ↑", highlight: "vk-highlight-move" },
    "ArrowDown": { badge: "RS ↓", highlight: "vk-highlight-move" },
    "ArrowLeft": { badge: "RS ←", highlight: "vk-highlight-move" },
    "ArrowRight": { badge: "RS →", highlight: "vk-highlight-move" },
    "Digit1": { badge: "D↑", highlight: "vk-highlight-move" },
    "Digit2": { badge: "D↓", highlight: "vk-highlight-move" },
    "Digit3": { badge: "D←", highlight: "vk-highlight-move" },
    "Digit4": { badge: "D→", highlight: "vk-highlight-move" }
  }
};

CONTROLLER_BADGES.xbox_overlay = CONTROLLER_BADGES.xbox_controller;
CONTROLLER_BADGES.playstation_overlay = CONTROLLER_BADGES.playstation_controller;

window.KEYBOARD_LAYOUTS = KEYBOARD_LAYOUTS;
window.CONTROLLER_BADGES = CONTROLLER_BADGES;
