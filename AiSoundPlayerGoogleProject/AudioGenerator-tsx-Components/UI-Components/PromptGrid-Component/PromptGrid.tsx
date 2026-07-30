import { css, html, LitElement, CSSResultGroup } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface Prompt {
  readonly promptId: string;
  text: string;
  weight: number;
  cc: number;
  color: string;
}

interface MidiDispatcher {
  activeMidiInputId: string | null;
  getMidiAccess(): Promise<string[]>;
  getDeviceName(id: string): string | null;
}

@customElement('prompt-grid')
export class PromptGrid extends LitElement {
  static override styles = css`
    #grid {
      aspect-ratio: 1;
      display: grid;
      width: 80vmin;
      gap: 2.5vmin;
      margin-top: 10vmin;
    }
  ` as CSSResultGroup;

  @property({ type: Object }) prompts: Map<string, Prompt> = new Map();
  @property({ type: Object }) filteredPrompts = new Set<string>();
  @property({ type: Object }) midiDispatcher!: MidiDispatcher;
  @property({ type: Boolean }) showMidi = false;
  @property({ type: Number }) audioLevel = 0;
  @property({ type: Number }) gridSize = 4;

  private handlePromptChanged(e: CustomEvent<Prompt>) {
    // Bubble the event up to parent component
    this.dispatchEvent(new CustomEvent('prompt-changed', {
      detail: e.detail,
      bubbles: true,
      composed: true
    }));
  }

  private renderPrompts() {
    return [...this.prompts.values()].map((prompt) => {
      return html`<prompt-controller
        promptId=${prompt.promptId}
        filtered=${this.filteredPrompts.has(prompt.text)}
        cc=${prompt.cc}
        text=${prompt.text}
        weight=${prompt.weight}
        color=${prompt.color}
        .midiDispatcher=${this.midiDispatcher}
        .showCC=${this.showMidi}
        audioLevel=${this.audioLevel}
        @prompt-changed=${this.handlePromptChanged}>
      </prompt-controller>`;
    });
  }

  override render() {
    return html`
      <div id="grid" style="grid-template-columns: repeat(${this.gridSize}, 1fr)">${this.renderPrompts()}</div>
    `;
  }
} 