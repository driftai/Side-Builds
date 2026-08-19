export function actionButton(text, className, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = text;
  button.className = className;
  button.addEventListener("click", handler);
  return button;
}

export function resultNode(template, title, subtitle, actions, badge = "") {
  const node = template.content.firstElementChild.cloneNode(true);
  node.querySelector(".result-title").textContent = title;
  const sub = node.querySelector(".result-sub");
  sub.textContent = subtitle || "";
  if (badge) {
    const chip = document.createElement("span");
    chip.className = "mini-badge";
    chip.textContent = badge;
    sub.prepend(chip);
  }
  node.querySelector(".result-actions").append(...actions);
  return node;
}

export function formatTime(ms) {
  return `${(Number(ms || 0) / 1000).toFixed(2)} s`;
}

export function escapeHtml(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
