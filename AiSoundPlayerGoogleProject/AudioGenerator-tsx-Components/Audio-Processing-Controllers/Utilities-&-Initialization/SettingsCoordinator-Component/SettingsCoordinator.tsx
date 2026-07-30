/**
 * @fileoverview Settings Coordinator Component
 * @description Coordinates settings application between toast messages, playback duration, and UI state
 * @license SPDX-License-Identifier: Apache-2.0
 */

import { LitElement, html } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface ToastMessage {
  show(message: string): void;
}

interface PlaybackDurationController {
  applySettings(onSessionEnd: () => void): void;
}

interface PlaybackController {
  stop(): void;
}

interface UIStateController {
  toggleSettingsPanel(): void;
}

@customElement('settings-coordinator')
export class SettingsCoordinator extends LitElement {
  @property({ type: Object }) toastMessage!: ToastMessage;
  @property({ type: Object }) playbackDurationController!: PlaybackDurationController;
  @property({ type: Object }) playbackController!: PlaybackController;
  @property({ type: Object }) uiStateController!: UIStateController;

  /**
   * Applies settings and coordinates between multiple components
   * This method handles:
   * 1. Showing confirmation toast message
   * 2. Applying settings via PlaybackDurationController
   * 3. Managing UI state (closing settings panel)
   */
  applySettings(): void {
    // Show confirmation message
    if (this.toastMessage) {
      this.toastMessage.show('Settings applied.');
    }

    // Apply settings using the PlaybackDurationController
    if (this.playbackDurationController && this.playbackController) {
      this.playbackDurationController.applySettings(() => {
        this.playbackController.stop();
      });
    }

    // Close the settings panel
    if (this.uiStateController) {
      this.uiStateController.toggleSettingsPanel();
    }
  }

  override render() {
    // This component doesn't render visible content, it's a coordination controller
    return html``;
  }
} 