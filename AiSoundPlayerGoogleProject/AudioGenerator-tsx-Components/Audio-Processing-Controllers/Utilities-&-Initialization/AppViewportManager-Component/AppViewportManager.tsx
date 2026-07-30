/**
 * @fileoverview App Viewport Manager Component
 * @description Manages viewport initialization, layout setup, and app-level display configuration
 * @license SPDX-License-Identifier: Apache-2.0
 */

import { LitElement, html } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { ViewportController } from '../ViewportController-Component/ViewportController.js';

@customElement('app-viewport-manager')
export class AppViewportManager extends LitElement {
  @property({ type: Object }) hostElement!: HTMLElement;
  
  override connectedCallback() {
    super.connectedCallback();
    this.initializeViewport();
  }
  
  /**
   * Initializes the viewport and applies necessary styles for full-screen app display
   */
  private initializeViewport() {
    // Apply document-level viewport styles for full-screen display
    ViewportController.applyViewportStyles();
    
    // Apply flex display to the host element if provided
    if (this.hostElement) {
      ViewportController.applyFlexDisplay(this.hostElement);
    }
    
    // Dispatch event to notify that viewport initialization is complete
    this.dispatchEvent(new CustomEvent('viewport-initialized', {
      bubbles: true,
      composed: true
    }));
  }
  
  /**
   * Resets viewport styles to browser defaults (for cleanup if needed)
   */
  resetViewport() {
    ViewportController.resetViewportStyles();
    
    this.dispatchEvent(new CustomEvent('viewport-reset', {
      bubbles: true,
      composed: true
    }));
  }
  
  /**
   * Gets the current viewport configuration status
   */
  get viewportStatus() {
    return {
      isInitialized: true,
      hasHostElement: !!this.hostElement
    };
  }
  
  override render() {
    // This component doesn't render visible content, it's a logic controller
    return html``;
  }
} 