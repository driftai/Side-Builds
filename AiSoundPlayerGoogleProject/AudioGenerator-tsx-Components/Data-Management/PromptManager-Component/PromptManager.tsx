import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { PromptDefaults } from '../PromptDefaults-Component/PromptDefaults.tsx';
import { throttle } from '../../Audio-Processing-Controllers/Utilities-&-Initialization/ThrottleUtility-Component/ThrottleUtility.tsx';

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

interface LiveMusicSession {
  setWeightedPrompts(params: { weightedPrompts: Prompt[] }): Promise<void>;
}

interface BackgroundGenerator {
  prompts: Map<string, Prompt>;
}

@customElement('prompt-manager')
export class PromptManager extends LitElement {
  @property({ type: Object }) prompts: Map<string, Prompt> = new Map();
  @property({ type: Object }) filteredPrompts = new Set<string>();
  @property({ type: Object }) session: LiveMusicSession | null = null;
  @property({ type: Object }) toastMessage!: ToastMessage;
  @property({ type: Object }) backgroundGenerator!: BackgroundGenerator;
  @property({ type: Object }) hostElement!: HTMLElement; // Reference to the host element for dispatching events
  @property({ type: String }) generationStyle: 'stacked' | 'blended' = 'stacked'; // Default to stacked

  @property({ type: Boolean }) autoVariationEnabled = false;
  @property({ type: Number }) autoVariationRate = 0.5; // Speed: 0.0 to 1.0
  @property({ type: Number }) autoVariationDepth = 0.2; // Intensity: 0.0 to 1.0

  private variationTimer: number | null = null;

  override updated(changedProperties: Map<string, unknown>) {
    super.updated(changedProperties);

    // Monitor session changes
    if (changedProperties.has('session')) {
      // Session updated - ready to send prompt updates if needed
    }

    // Monitor generation style changes
    if (changedProperties.has('generationStyle')) {
      console.log(`PromptManager: Generation style changed to '${this.generationStyle}' - updating session prompts`);
      this.setSessionPrompts();
    }

    // Monitor auto-variation changes
    if (changedProperties.has('autoVariationEnabled') ||
      changedProperties.has('autoVariationRate')) {
      this.handleAutoVariationChange();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.stopVariationLoop();
  }

  private handleAutoVariationChange() {
    if (this.autoVariationEnabled) {
      this.startVariationLoop();
    } else {
      this.stopVariationLoop();
    }
  }

  private stopVariationLoop() {
    if (this.variationTimer !== null) {
      window.clearInterval(this.variationTimer);
      this.variationTimer = null;
    }
  }

  @property({ type: Number }) autoVariationMinInterval = 200;
  @property({ type: Number }) autoVariationMaxInterval = 2000;
  @property({ type: Number }) autoVariationMaxChange = 0.25; // Maximum possible change (25%)


  private startVariationLoop() {
    this.stopVariationLoop();

    // Map rate (0-1) to interval
    // Slower rate = larger interval
    const intervalRange = this.autoVariationMaxInterval - this.autoVariationMinInterval;
    const interval = this.autoVariationMaxInterval - (this.autoVariationRate * intervalRange);

    this.variationTimer = window.setInterval(() => {
      this.applyVariation();
    }, interval);
  }

  private applyVariation() {
    const activePrompts = Array.from(this.prompts.values()).filter(p => p.weight > 0);
    if (activePrompts.length === 0) return;

    // Pick one random active prompt to nudge
    const targetPrompt = activePrompts[Math.floor(Math.random() * activePrompts.length)];

    // Calculate nudge amount based on depth and max allowed change
    const maxStep = this.autoVariationMaxChange * this.autoVariationDepth;
    const nudge = (Math.random() - 0.5) * 2 * maxStep;

    const newWeight = Math.max(0.01, Math.min(1.0, targetPrompt.weight + nudge));

    if (Math.abs(newWeight - targetPrompt.weight) > 0.001) {
      // Create new prompt object
      const updatedPrompt = { ...targetPrompt, weight: newWeight };

      // Update map
      const newPrompts = new Map(this.prompts);
      newPrompts.set(updatedPrompt.promptId, updatedPrompt);

      // Update state WITHOUT full reset (to avoid UI flicker ideally, but setPrompts triggers it)
      // We use setPrompts to ensure propagation
      this.prompts = newPrompts;
      this.requestUpdate();
      this.dispatchPromptsChange();
    }
  }

  /**
   * Get prompts that should be sent to the session (active and not filtered)
   */
  getPromptsToSend(): Prompt[] {
    return Array.from(this.prompts.values())
      .filter((p) => {
        return !this.filteredPrompts.has(p.text) && p.weight !== 0;
      });
  }

  /**
   * Send prompts to the session with throttling
   */
  setSessionPrompts = throttle(async () => {
    if (!this.session) {
      console.log('PromptManager: No session available for setSessionPrompts');
      return;
    }

    try {
      const promptsToSend = this.getPromptsToSend();

      if (promptsToSend.length === 0) {
        console.log('PromptManager: No active prompts to send to session');
        return;
      }

      console.log('PromptManager: Sending', promptsToSend.length, 'active prompts to session:');

      let finalPrompts = promptsToSend;

      // Apply normalization if style is 'blended'
      if (this.generationStyle === 'blended') {
        const totalWeight = promptsToSend.reduce((sum, p) => sum + p.weight, 0);
        if (totalWeight > 0) {
          console.log(`PromptManager: Normalizing weights (Total: ${totalWeight.toFixed(2)}) for 'blended' style.`);
          finalPrompts = promptsToSend.map(p => ({
            ...p,
            weight: p.weight / totalWeight
          }));
        }
      }

      finalPrompts.forEach(prompt => {
        console.log(`  • "${prompt.text}" (weight: ${prompt.weight.toFixed(2)})`);
      });

      // Ensure promptsToSend is an array of objects with 'text' and 'weight' properties
      await this.session.setWeightedPrompts({ weightedPrompts: finalPrompts });
      console.log('PromptManager: Prompts successfully sent to AI session');
    } catch (e: any) {
      if (e?.message?.includes('CLOSING') || e?.message?.includes('CLOSED')) {
        console.warn('PromptManager: WebSocket closed while sending prompts - suppressing error');
        // Do not toast - this is expected during rapid disconnect/reconnect
      } else {
        console.error('PromptManager: Error sending prompts to session:', e);
        this.toastMessage.show(`Error sending prompts: ${e.message}`);
      }
    }
  }, 100); // Reduced from 200ms to 100ms for more responsive audio processing

  /**
   * Update background generator immediately (no throttling for smooth UI)
   */
  private updateBackgroundGenerator() {
    if (this.backgroundGenerator) {
      this.backgroundGenerator.prompts = this.prompts;
    }
  }

  /**
   * Dispatch prompts change event and update session
   */
  dispatchPromptsChange() {
    console.log('PromptManager: Dispatching prompts change event and updating session');

    // Update background immediately for smooth UI
    this.updateBackgroundGenerator();

    if (this.hostElement) {
      this.hostElement.dispatchEvent(
        new CustomEvent('prompts-updated', { detail: this.prompts }),
      );
    }
    return this.setSessionPrompts();
  }

  /**
   * Set new prompts and trigger updates
   */
  setPrompts(newPrompts: Map<string, Prompt>) {
    this.prompts = newPrompts;

    // Log prompt set update
    const activePrompts = Array.from(this.prompts.values()).filter(p => p.weight > 0);
    console.log('PromptManager: Prompt set updated -', this.prompts.size, 'total prompts,', activePrompts.length, 'active');

    this.requestUpdate();
    this.dispatchPromptsChange();
  }

  /**
   * Reset all prompts to default values
   */
  resetAll() {
    // Reset to current size defaults
    this.setPrompts(PromptDefaults.generatePrompts(this.prompts.size));
  }

  /**
   * Resize the number of prompts, preserving existing ones where possible
   */
  resizePrompts(newCount: number) {
    const defaultPrompts = PromptDefaults.generatePrompts(newCount);
    const mergedPrompts = new Map<string, Prompt>();

    for (const [id, prompt] of defaultPrompts) {
      if (this.prompts.has(id)) {
        mergedPrompts.set(id, this.prompts.get(id)!);
      } else {
        mergedPrompts.set(id, prompt);
      }
    }

    this.setPrompts(mergedPrompts);
  }

  /**
   * Handle individual prompt changes
   */
  handlePromptChanged(e: CustomEvent<Prompt>) {
    const { promptId, text, weight, cc } = e.detail;

    console.log('PromptManager: Received prompt change for', promptId, '("' + text + '") - weight:', weight.toFixed(2), 'cc:', cc);

    const prompt = this.prompts.get(promptId);

    if (!prompt) {
      console.error('PromptManager: prompt not found', promptId);
      return;
    }

    const oldWeight = prompt.weight;
    const oldText = prompt.text;

    prompt.text = text;
    prompt.weight = weight;
    prompt.cc = cc;

    // Log what changed
    if (oldWeight !== weight) {
      console.log('PromptManager: Weight changed from', oldWeight.toFixed(2), 'to', weight.toFixed(2), 'for prompt "' + text + '"');
    }
    if (oldText !== text) {
      console.log('PromptManager: Text changed from "' + oldText + '" to "' + text + '"');
    }

    const newPrompts = new Map(this.prompts);
    newPrompts.set(promptId, prompt);

    this.setPrompts(newPrompts);
  }

  override render() {
    // This component doesn't render UI directly, it's a utility component
    return null;
  }
} 