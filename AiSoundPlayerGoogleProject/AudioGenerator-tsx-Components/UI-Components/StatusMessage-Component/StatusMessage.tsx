import { css, html, LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

@customElement('status-message')
export class StatusMessage extends LitElement {
  static override styles = css`
    #status-message {
      position: fixed; /* Changed from absolute to fixed for better positioning */
      top: 10px;
      left: 50%;
      transform: translateX(-50%);
      color: white;
      background-color: rgba(0, 0, 0, 0.8); /* Increased opacity for better visibility */
      padding: 8px 15px;
      border-radius: 5px;
      z-index: 1000; /* Increased z-index significantly to ensure visibility */
      font-size: 1.2em;
      text-align: center;
      transition: opacity 0.3s ease-in-out;
      pointer-events: none; /* Prevent interaction interference */
    }
    
    :host([hidden]) {
      display: none;
    }
    
    :host {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 0;
      pointer-events: none;
      z-index: 1000;
    }
  `;

  @state() private message: string = '';
  @state() private isVisible: boolean = false;
  
  private hideTimer: number | null = null;
  private readonly duration = 3000; // 3 seconds

  show(message: string, duration?: number) {
    this.message = message;
    this.isVisible = true;
    this.hidden = false;
    
    // Clear any existing timer
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
    }
    
    // Set new timer to auto-hide
    this.hideTimer = window.setTimeout(() => {
      this.hide();
    }, duration || this.duration);
    
    // Force re-render
    this.requestUpdate();
  }

  hide() {
    this.isVisible = false;
    this.hidden = true;
    this.message = '';
    
    // Clear timer if hiding manually
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
    }
    
    // Force re-render
    this.requestUpdate();
  }

  override disconnectedCallback() {
    super.disconnectedCallback();
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
    }
  }

  override render() {
    if (!this.isVisible || !this.message) {
      return html``;
    }
    
    return html`<div id="status-message">${this.message}</div>`;
  }
} 