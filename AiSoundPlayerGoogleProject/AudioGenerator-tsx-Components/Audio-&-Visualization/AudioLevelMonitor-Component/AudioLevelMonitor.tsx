import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

interface AudioAnalyser {
  getCurrentLevel(): number;
}

interface WaveformVisualizer {
  updateFrequencyHistory(): void;
  drawWaveform(): void;
}

@customElement('audio-level-monitor')
export class AudioLevelMonitor extends LitElement {
  @property({ type: Object }) audioAnalyser!: AudioAnalyser;
  @property({ type: Object }) waveformVisualizer?: WaveformVisualizer;

  @state() audioLevel = 0;

  private audioLevelRafId: number | null = null;

  constructor() {
    super();
    this.updateAudioLevel = this.updateAudioLevel.bind(this);
  }

  override connectedCallback() {
    super.connectedCallback();
    this.startMonitoring();
  }

  override disconnectedCallback() {
    super.disconnectedCallback();
    this.stopMonitoring();
  }

  /**
   * Starts the audio level monitoring loop
   */
  startMonitoring() {
    if (!this.audioLevelRafId) {
      this.updateAudioLevel();
    }
  }

  /**
   * Stops the audio level monitoring loop
   */
  stopMonitoring() {
    if (this.audioLevelRafId !== null) {
      cancelAnimationFrame(this.audioLevelRafId);
      this.audioLevelRafId = null;
    }
  }

  /**
   * Updates audio level and triggers waveform visualizer updates
   */
  private updateAudioLevel() {
    this.audioLevelRafId = requestAnimationFrame(this.updateAudioLevel);
    
    // Update frequency history in the waveform visualizer
    if (this.waveformVisualizer) {
      this.waveformVisualizer.updateFrequencyHistory();
    }

    // Get current audio level from analyser
    if (this.audioAnalyser) {
      this.audioLevel = this.audioAnalyser.getCurrentLevel();
    }
    
    // Update the waveform visualizer
    if (this.waveformVisualizer) {
      this.waveformVisualizer.drawWaveform();
    }

    // Dispatch audio level change event for parent component
    this.dispatchEvent(new CustomEvent('audio-level-change', {
      detail: this.audioLevel,
      bubbles: true,
      composed: true
    }));
  }

  /**
   * Gets the current audio level
   */
  getCurrentLevel(): number {
    return this.audioLevel;
  }

  override render() {
    // This component doesn't render UI directly, it's a monitoring controller
    return null;
  }
} 