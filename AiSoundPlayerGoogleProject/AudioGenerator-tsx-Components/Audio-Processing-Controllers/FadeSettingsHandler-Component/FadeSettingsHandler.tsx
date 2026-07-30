/**
 * @fileoverview Fade Settings Handler Component
 * @description Manages fade-in and fade-out duration settings and coordinates updates with FadeController
 * @license SPDX-License-Identifier: Apache-2.0
 */

import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

interface FadeController {
  fadeInDurationSec: number;
  fadeOutDurationSec: number;
}

@customElement('fade-settings-handler')
export class FadeSettingsHandler extends LitElement {
  @property({ type: Object }) fadeController!: FadeController;
  @property({ type: Object }) settingsPersistence: any;

  @state() private fadeInDurationSec = 2; // Default fade-in duration in seconds
  @state() private fadeOutDurationSec = 5; // Default fade-out duration in seconds

  override connectedCallback() {
    super.connectedCallback();
    // Load saved settings if available
    this.loadSavedSettings();
  }

  // Poll for settingsPersistence if it's not immediately available
  async loadSavedSettings() {
    // Small delay to ensure settingsPersistence is injected
    await new Promise(resolve => setTimeout(resolve, 0));

    if (this.settingsPersistence && this.settingsPersistence.loadFadeSettings) {
      const savedSettings = this.settingsPersistence.loadFadeSettings();
      if (savedSettings) {
        this.fadeInDurationSec = savedSettings.fadeInDurationSec;
        this.fadeOutDurationSec = savedSettings.fadeOutDurationSec;

        // Propagate loaded values to controller
        if (this.fadeController) {
          this.fadeController.fadeInDurationSec = this.fadeInDurationSec;
          this.fadeController.fadeOutDurationSec = this.fadeOutDurationSec;
        }

        // Notify parent
        if (this.onFadeInChange) this.onFadeInChange(this.fadeInDurationSec);
        if (this.onFadeOutChange) this.onFadeOutChange(this.fadeOutDurationSec);
      }
    }
  }

  // Callback function to notify parent component of changes
  @property({ type: Function }) onFadeInChange!: (duration: number) => void;
  @property({ type: Function }) onFadeOutChange!: (duration: number) => void;

  /**
   * Handles fade-in duration change events
   * @param e CustomEvent containing the new fade-in duration
   */
  handleFadeInChange(e: CustomEvent) {
    this.fadeInDurationSec = e.detail;
    if (this.fadeController) {
      this.fadeController.fadeInDurationSec = e.detail;
    }
    if (this.onFadeInChange) {
      this.onFadeInChange(e.detail);
    }
    // Save to persistence
    if (this.settingsPersistence && this.settingsPersistence.saveFadeSettings) {
      this.settingsPersistence.saveFadeSettings(this.fadeInDurationSec, this.fadeOutDurationSec);
    }
  }

  /**
   * Handles fade-out duration change events
   * @param e CustomEvent containing the new fade-out duration
   */
  handleFadeOutChange(e: CustomEvent) {
    this.fadeOutDurationSec = e.detail;
    if (this.fadeController) {
      this.fadeController.fadeOutDurationSec = e.detail;
    }
    if (this.onFadeOutChange) {
      this.onFadeOutChange(e.detail);
    }
    // Save to persistence
    if (this.settingsPersistence && this.settingsPersistence.saveFadeSettings) {
      this.settingsPersistence.saveFadeSettings(this.fadeInDurationSec, this.fadeOutDurationSec);
    }
  }

  /**
   * Gets the current fade-in duration
   */
  getFadeInDuration(): number {
    return this.fadeInDurationSec;
  }

  /**
   * Gets the current fade-out duration
   */
  getFadeOutDuration(): number {
    return this.fadeOutDurationSec;
  }

  /**
   * Sets the fade-in duration programmatically
   * @param duration Duration in seconds
   */
  setFadeInDuration(duration: number): void {
    this.fadeInDurationSec = duration;
    if (this.fadeController) {
      this.fadeController.fadeInDurationSec = duration;
    }
  }

  /**
   * Sets the fade-out duration programmatically
   * @param duration Duration in seconds
   */
  setFadeOutDuration(duration: number): void {
    this.fadeOutDurationSec = duration;
    if (this.fadeController) {
      this.fadeController.fadeOutDurationSec = duration;
    }
  }

  /**
   * Gets both fade durations as an object
   */
  getFadeSettings() {
    return {
      fadeInDurationSec: this.fadeInDurationSec,
      fadeOutDurationSec: this.fadeOutDurationSec
    };
  }

  override render() {
    // This component doesn't render UI directly, it's a settings handler
    return null;
  }
} 