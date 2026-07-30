import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('fade-controller')
export class FadeController extends LitElement {
  @property({ type: Object }) outputNode!: GainNode;
  @property({ type: Object }) audioContext!: AudioContext;
  @property({ type: Number }) fadeInDurationSec = 2; // Default fade-in duration in seconds
  @property({ type: Number }) fadeOutDurationSec = 5; // Default fade-out duration in seconds
  @property({ type: Number }) masterVolume = 1; // Master volume level

  /**
   * Applies fade-in effect to the audio output
   * @param masterVolume Target volume level to fade to
   */
  applyFadeIn(masterVolume: number = this.masterVolume) {
    if (!this.outputNode || !this.audioContext) {
      console.warn('FadeController: outputNode or audioContext not available for fade-in');
      return;
    }

    const startTime = this.audioContext.currentTime;
    const fadeEndTime = startTime + this.fadeInDurationSec;
    
    // Start from 0 volume and ramp up to master volume
    this.outputNode.gain.setValueAtTime(0, startTime);
    this.outputNode.gain.linearRampToValueAtTime(masterVolume, fadeEndTime);
  }

  /**
   * Applies fade-out effect to the audio output
   * @param targetVolume Target volume level to fade to (default 0)
   * @returns Promise that resolves when fade-out is complete
   */
  applyFadeOut(targetVolume: number = 0): Promise<void> {
    return new Promise((resolve) => {
      if (!this.outputNode || !this.audioContext) {
        console.warn('FadeController: outputNode or audioContext not available for fade-out');
        resolve();
        return;
      }

      const stopTime = this.audioContext.currentTime;
      const fadeOutEndTime = stopTime + this.fadeOutDurationSec;
      
      // Ramp volume down to target volume
      this.outputNode.gain.cancelScheduledValues(stopTime);
      this.outputNode.gain.setValueAtTime(this.outputNode.gain.value, stopTime);
      this.outputNode.gain.linearRampToValueAtTime(targetVolume, fadeOutEndTime);

      // Resolve promise when fade-out is complete
      setTimeout(() => {
        resolve();
      }, this.fadeOutDurationSec * 1000 + 100); // Add small buffer
    });
  }

  /**
   * Immediately sets the volume without fading
   * @param volume Volume level (0-1)
   */
  setVolumeImmediate(volume: number) {
    if (!this.outputNode || !this.audioContext) {
      console.warn('FadeController: outputNode or audioContext not available for immediate volume set');
      return;
    }

    this.outputNode.gain.setValueAtTime(volume, this.audioContext.currentTime);
  }

  /**
   * Gets current fade settings
   */
  get fadeSettings() {
    return {
      fadeInDurationSec: this.fadeInDurationSec,
      fadeOutDurationSec: this.fadeOutDurationSec,
      masterVolume: this.masterVolume
    };
  }

  /**
   * Updates fade settings
   */
  updateFadeSettings(settings: {
    fadeInDurationSec?: number;
    fadeOutDurationSec?: number;
    masterVolume?: number;
  }) {
    if (settings.fadeInDurationSec !== undefined) {
      this.fadeInDurationSec = settings.fadeInDurationSec;
    }
    if (settings.fadeOutDurationSec !== undefined) {
      this.fadeOutDurationSec = settings.fadeOutDurationSec;
    }
    if (settings.masterVolume !== undefined) {
      this.masterVolume = settings.masterVolume;
    }
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 