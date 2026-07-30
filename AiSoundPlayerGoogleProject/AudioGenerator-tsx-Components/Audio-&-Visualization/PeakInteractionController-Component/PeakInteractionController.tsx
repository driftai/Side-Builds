// PeakInteractionController.tsx - Handles interactive peak visualization and prompt weight updates from frequency peaks

import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import type { Prompt } from '../../TypeDefinitions-Component/TypeDefinitions.js';
import { ToastMessage } from '../../UI-Components/ToastMessage-Component/ToastMessage.js';

@customElement('peak-interaction-controller')
export class PeakInteractionController extends LitElement {
  @property({ type: Object }) prompts: Map<string, Prompt> = new Map();
  @property({ type: Object }) toastMessage!: ToastMessage;

  handlePeakClick(event: CustomEvent) {
    // Logic from PeakHandler
    const { bin, intensity } = event.detail;
    const promptIndex = bin % this.prompts.size;
    const promptId = Array.from(this.prompts.keys())[promptIndex];
    const prompt = this.prompts.get(promptId);

    if (prompt) {
      const weightChange = intensity / 255;
      prompt.weight = Math.min(1, Math.max(0, prompt.weight + weightChange));
      this.toastMessage.show(`Adjusted ${prompt.text} by ${weightChange.toFixed(2)}`);
      this.requestUpdate();
      this.dispatchEvent(new CustomEvent('prompt-updated', { detail: prompt }));
    }
  }

  override render() {
    return null;
  }
} 