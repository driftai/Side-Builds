import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface Prompt {
  readonly promptId: string;
  text: string;
  weight: number;
  cc: number;
  color: string;
}

@customElement('background-generator')
export class BackgroundGenerator extends LitElement {
  @property({ type: Object }) prompts: Map<string, Prompt> = new Map();

  /**
   * Generates radial gradients for each prompt based on weight and color.
   * Uses throttling to prevent excessive re-rendering.
   */
  generateBackground(): string {
    const clamp01 = (v: number) => Math.min(Math.max(v, 0), 1);

    const MAX_WEIGHT = 0.5;
    const MAX_ALPHA = 0.6;

    const bg: string[] = [];

    [...this.prompts.values()].forEach((p, i) => {
      const alphaPct = clamp01(p.weight / MAX_WEIGHT) * MAX_ALPHA;
      const alpha = Math.round(alphaPct * 0xff)
        .toString(16)
        .padStart(2, '0');

      const stop = p.weight / 2;
      const x = (i % 4) / 3;
      const y = Math.floor(i / 4) / 3;
      const s = `radial-gradient(circle at ${x * 100}% ${y * 100}%, ${p.color}${alpha} 0px, ${p.color}00 ${stop * 100}%)`;

      bg.push(s);
    });

    return bg.join(', ');
  }

  override render() {
    // This component doesn't render UI directly, it's a utility component
    return null;
  }
} 