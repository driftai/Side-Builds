interface Prompt {
  readonly promptId: string;
  text: string;
  weight: number;
  cc: number;
  color: string;
}

/** Default prompt configurations for the music generation system */
export const DEFAULT_PROMPTS = [
  { color: '#9900ff', text: 'Bossa Nova' },
  { color: '#5200ff', text: 'Chillwave' },
  { color: '#ff25f6', text: 'Drum and Bass' },
  { color: '#2af6de', text: 'Post Punk' },
  { color: '#ffdd28', text: 'Shoegaze' },
  { color: '#2af6de', text: 'Funk' },
  { color: '#9900ff', text: 'Chiptune' },
  { color: '#3dffab', text: 'Lush Strings' },
  { color: '#d8ff3e', text: 'Sparkling Arpeggios' },
  { color: '#d9b2ff', text: 'Staccato Rhythms' },
  { color: '#3dffab', text: 'Punchy Kick' },
  { color: '#ffdd28', text: 'Dubstep' },
  { color: '#ff25f6', text: 'K Pop' },
  { color: '#d8ff3e', text: 'Neo Soul' },
  { color: '#5200ff', text: 'Trip Hop' },
  { color: '#d9b2ff', text: 'Thrash' },
];

/** 
 * PromptDefaults utility class for managing prompt initialization and configuration
 */
export class PromptDefaults {

  /**
   * Gets initial prompts from localStorage or builds default prompts
   * @returns Map of prompts with their IDs as keys
   */
  static getInitialPrompts(): Map<string, Prompt> {
    const { localStorage } = window;
    const storedPrompts = localStorage.getItem('prompts');

    if (storedPrompts) {
      try {
        const prompts = JSON.parse(storedPrompts) as Prompt[];
        console.log('Loading stored prompts', prompts);
        return new Map(prompts.map((prompt) => [prompt.promptId, prompt]));
      } catch (e) {
        console.error('Failed to parse stored prompts', e);
      }
    }

    console.log('No stored prompts, using default prompts');
    return PromptDefaults.buildDefaultPrompts();
  }

  /**
   * Builds the default prompts configuration
   * @returns Map of default prompts with random 3 prompts activated
   */
  static buildDefaultPrompts(): Map<string, Prompt> {
    // Pick 3 random prompts to start with weight 1
    const startOn = [...DEFAULT_PROMPTS]
      .sort(() => Math.random() - 0.5)
      .slice(0, 3);

    const prompts = new Map<string, Prompt>();

    for (let i = 0; i < DEFAULT_PROMPTS.length; i++) {
      const promptId = `prompt-${i}`;
      const prompt = DEFAULT_PROMPTS[i];
      const { text, color } = prompt;
      prompts.set(promptId, {
        promptId,
        text,
        weight: startOn.includes(prompt) ? 1 : 0,
        cc: i,
        color,
      });
    }

    return prompts;
  }

  /**
   * Saves prompts to localStorage
   * @param prompts Map of prompts to save
   */
  static setStoredPrompts(prompts: Map<string, Prompt>): void {
    const storedPrompts = JSON.stringify([...prompts.values()]);
    const { localStorage } = window;
    localStorage.setItem('prompts', storedPrompts);
  }

  /**
   * Generates a specific number of prompts
   * @param count Number of prompts to generate
   * @returns Map of generated prompts
   */
  static generatePrompts(count: number): Map<string, Prompt> {
    const prompts = new Map<string, Prompt>();

    // Pick 3 random indices to start with weight 1
    const startIndices = new Set<number>();
    while (startIndices.size < 3 && startIndices.size < count) {
      startIndices.add(Math.floor(Math.random() * count));
    }

    for (let i = 0; i < count; i++) {
      const promptId = `prompt-${i}`;
      let text = '';
      let color = '';

      if (i < DEFAULT_PROMPTS.length) {
        text = DEFAULT_PROMPTS[i].text;
        color = DEFAULT_PROMPTS[i].color;
      } else {
        // Generate generic prompt for extras
        text = `Prompt ${i + 1}`;
        // Cycle through default colors
        color = DEFAULT_PROMPTS[i % DEFAULT_PROMPTS.length].color;
      }

      prompts.set(promptId, {
        promptId,
        text,
        weight: startIndices.has(i) ? 1 : 0,
        cc: i,
        color,
      });
    }

    return prompts;
  }
} 