import { css, html, LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { classMap } from 'lit/directives/class-map.js';

// Toast Message component
// -----------------------------------------------------------------------------

@customElement('toast-message')
export class ToastMessage extends LitElement {
  static override styles = css`
    .toast {
      line-height: 1.6;
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background-color: #000;
      color: white;
      padding: 15px;
      border-radius: 5px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 15px;
      min-width: 200px;
      max-width: 80vw;
      transition: transform 0.5s cubic-bezier(0.19, 1, 0.22, 1);
    }
    button {
      border-radius: 100px;
      aspect-ratio: 1;
      border: none;
      color: #000;
      cursor: pointer;
    }
    .toast:not(.showing) {
      transition-duration: 1s;
      transform: translate(-50%, -200%);
    }
  `;

  @property({ type: String }) message = '';
  @property({ type: Boolean }) showing = false;

  private hideTimer: number | null = null;
  private readonly autoHideDuration = 5000; // 5 seconds

  override render() {
    return html`<div class=${classMap({ showing: this.showing, toast: true })}>
      <div class="message">${this.message}</div>
      <button @click=${this.hide}>✕</button>
    </div>`;
  }

  show(message: string) {
    this.showing = true;
    this.message = message;
    // Clear any existing timer
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
    }
    // Set a new timer to auto-hide
    this.hideTimer = window.setTimeout(() => {
      this.hide();
    }, this.autoHideDuration);
  }

  hide() {
    this.showing = false;
    // Clear the timer if hiding manually
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
    }
  }
} 