import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface Prompt {
  readonly promptId: string;
  text: string;
  weight: number;
  cc: number;
  color: string;
}

interface ToastMessage {
  show(message: string): void;
}

interface PeakData {
  x: number;
  y: number;
  bin: number;
  intensity: number;
}

@customElement('peak-handler')
export class PeakHandler extends LitElement {
  @property({ type: Object }) prompts: Map<string, Prompt> = new Map();
  @property({ type: Object }) toastMessage!: ToastMessage;

  /**
   * Handles peak click events and boosts active prompt weights based on peak intensity
   * @param event CustomEvent containing the peak data
   */
  handlePeakClick(event: CustomEvent) {
    const hitPeak = event.detail.peak;
    
    // Calculate boost amount based on peak intensity (max boost 0.2)
    const boostAmount = (hitPeak.intensity / 255) * 0.2;

    let promptsUpdated = false;
    const updatedPrompts = new Map<string, Prompt>();

    this.prompts.forEach((prompt, promptId) => {
      // Only boost active prompts (weight > 0)
      if (prompt.weight > 0) {
        const newWeight = Math.min(2, prompt.weight + boostAmount); // Cap weight at max 2
        if (newWeight !== prompt.weight) {
          const updatedPrompt = { ...prompt, weight: newWeight };
          updatedPrompts.set(promptId, updatedPrompt);
          promptsUpdated = true;
        } else {
          updatedPrompts.set(promptId, prompt);
        }
      } else {
        updatedPrompts.set(promptId, prompt);
      }
    });

    if (promptsUpdated) {
      this.toastMessage.show(`Boosted active prompts based on frequency peak!`);
      // Dispatch event with updated prompts for parent to handle
      this.dispatchEvent(new CustomEvent('prompts-updated', {
        detail: updatedPrompts,
        bubbles: true,
        composed: true
      }));
    } else {
      this.toastMessage.show(`No active prompts to boost.`);
    }
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 