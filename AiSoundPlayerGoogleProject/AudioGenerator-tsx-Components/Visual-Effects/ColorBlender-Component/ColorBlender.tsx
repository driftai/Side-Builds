import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface Prompt {
  readonly promptId: string;
  text: string;
  weight: number;
  cc: number;
  color: string;
}

@customElement('color-blender')
export class ColorBlender extends LitElement {
  @property({ type: Object }) prompts: Map<string, Prompt> = new Map();

  /**
   * Calculates a blended color based on the colors and weights of active prompts.
   * @returns An rgba color string.
   */
  getBlendedActivePromptColor(): string {
    let totalWeight = 0;
    let r = 0, g = 0, b = 0;
    const activePrompts: Prompt[] = [];

    // Collect active prompts and calculate total weight
    this.prompts.forEach(prompt => {
      if (prompt.weight > 0) {
        activePrompts.push(prompt);
        totalWeight += prompt.weight;
      }
    });

    if (activePrompts.length === 0 || totalWeight === 0) {
      // Return a default color (e.g., white) if no prompts are active
      return 'rgba(255, 255, 255, 0.7)';
    }

    // Calculate weighted sum of RGB values
    activePrompts.forEach(prompt => {
      // Convert hex color to RGB
      const hex = prompt.color.replace('#', '');
      const colorR = parseInt(hex.substring(0, 2), 16);
      const colorG = parseInt(hex.substring(2, 4), 16);
      const colorB = parseInt(hex.substring(4, 6), 16);

      // Add weighted RGB values
      r += colorR * prompt.weight;
      g += colorG * prompt.weight;
      b += colorB * prompt.weight;
    });

    // Calculate the average RGB values
    const avgR = Math.round(r / totalWeight);
    const avgG = Math.round(g / totalWeight);
    const avgB = Math.round(b / totalWeight);

    // Return as rgba string (using a fixed alpha or an alpha based on totalWeight if desired)
    // Let's use a fixed alpha for consistency with existing styles, e.g., 0.7
    return `rgba(${avgR}, ${avgG}, ${avgB}, 0.7)`;
  }

  override render() {
    // This component doesn't render UI directly, it's a utility component
    return null;
  }
} 