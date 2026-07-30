import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

@customElement('frequency-history-manager')
export class FrequencyHistoryManager extends LitElement {
  @property({ type: Array }) frequencyHistory: Uint8Array[] = [];
  
  @state() private readonly frequencyHistoryLength = 100; // Number of frequency frames to store

  /**
   * Adds a new frequency data frame to the history
   * @param frequencyData - Uint8Array containing frequency data
   */
  addFrequencyFrame(frequencyData: Uint8Array): void {
    // Add new frame to history
    this.frequencyHistory = [...this.frequencyHistory, new Uint8Array(frequencyData)];
    
    // Trim history to maintain maximum length
    this.trimFrequencyHistory();
  }

  /**
   * Trims the frequency history to maintain the maximum length
   */
  private trimFrequencyHistory(): void {
    if (this.frequencyHistory.length > this.frequencyHistoryLength) {
      this.frequencyHistory = this.frequencyHistory.slice(-this.frequencyHistoryLength);
    }
  }

  /**
   * Gets the current frequency history
   */
  getFrequencyHistory(): Uint8Array[] {
    return [...this.frequencyHistory];
  }

  /**
   * Clears all frequency history
   */
  clearFrequencyHistory(): void {
    this.frequencyHistory = [];
  }

  /**
   * Gets the maximum history length
   */
  getMaxHistoryLength(): number {
    return this.frequencyHistoryLength;
  }

  /**
   * Gets the current history length
   */
  getCurrentHistoryLength(): number {
    return this.frequencyHistory.length;
  }

  /**
   * Dispatches frequency history update event
   */
  private dispatchFrequencyHistoryUpdate(): void {
    this.dispatchEvent(new CustomEvent('frequency-history-updated', {
      detail: this.frequencyHistory,
      bubbles: true,
      composed: true
    }));
  }

  override updated(changedProperties: Map<string, unknown>) {
    super.updated(changedProperties);
    
    if (changedProperties.has('frequencyHistory')) {
      this.dispatchFrequencyHistoryUpdate();
    }
  }

  override render() {
    // This component doesn't render UI directly, it's a data manager
    return null;
  }
} 