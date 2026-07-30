import { css, html, LitElement } from 'lit';
import { customElement, property, query } from 'lit/decorators.js';
import { classMap } from 'lit/directives/class-map.js';
import type { WeightKnob } from '../WeightKnob-Component/WeightKnob.js';

interface Prompt {
  readonly promptId: string;
  text: string;
  weight: number;
  cc: number;
  color: string;
}

interface ControlChange {
  channel: number;
  cc: number;
  value: number;
}

/** Simple class for dispatching MIDI CC messages as events. */
declare class MidiDispatcher extends EventTarget {
  activeMidiInputId: string | null;
  getMidiAccess(): Promise<string[]>;
  getDeviceName(id: string): string | null;
}

/** A single prompt input associated with a MIDI CC. */
@customElement('prompt-controller')
export class PromptController extends LitElement {
  static override styles = css`
    .prompt {
      height: 100%;
      width: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    weight-knob {
      height: 70%;
      flex-shrink: 0;
    }
    #midi {
      font-family: monospace;
      text-align: center;
      font-size: 1.5vmin;
      border: 0.2vmin solid #fff;
      border-radius: 0.5vmin;
      padding: 2px 5px;
      color: #fff;
      background: #0006;
      cursor: pointer;
      visibility: hidden;
      user-select: none;
      margin-top: 0.75vmin;
      .learn-mode & {
        color: orange;
        border-color: orange;
      }
      .show-cc & {
        visibility: visible;
      }
    }
    #text {
      font-family: 'Google Sans', sans-serif;
      font-weight: 500;
      font-size: 1.8vmin;
      max-width: 19vmin;
      min-width: 2vmin;
      padding: 0.1em 0.3em;
      margin-top: 0.5vmin;
      flex-shrink: 0;
      border-radius: 0.25vmin;
      text-align: center;
      white-space: nowrap;
      overflow: hidden;
      border: none;
      outline: none;
      -webkit-font-smoothing: antialiased;
      background: #000;
      color: #fff;
      &:not(:focus) {
        text-overflow: ellipsis;
      }
    }
    :host([filtered=true]) #text {
      background: #da2000;
    }
    :host(.high-weight) #text {
      border: 2px solid yellow; /* Example: Yellow border for high weight */
    }
    :host(.medium-weight) #text {
      border: 1px solid orange; /* Example: Orange border for medium weight */
    }
  `;

  @property({ type: String }) promptId = '';
  @property({ type: String }) text = '';
  @property({ type: Number }) weight = 0;
  @property({ type: String }) color = '';

  @property({ type: Number }) cc = 0;
  @property({ type: Number }) channel = 0; // Not currently used

  @property({ type: Boolean }) learnMode = false;
  @property({ type: Boolean }) showCC = false;

  @query('weight-knob') private weightInput!: WeightKnob;
  @query('#text') private textInput!: HTMLInputElement;

  @property({ type: Object })
  midiDispatcher: MidiDispatcher | null = null;

  @property({ type: Number }) audioLevel = 0;

  private lastValidText!: string;

  override connectedCallback() {
    super.connectedCallback();
    this.midiDispatcher?.addEventListener('cc-message', (e: Event) => {
      const customEvent = e as CustomEvent<ControlChange>;
      const { channel, cc, value } = customEvent.detail;
      if (this.learnMode) {
        this.cc = cc;
        this.channel = channel;
        this.learnMode = false;
        this.dispatchPromptChange();
      } else if (cc === this.cc) {
        this.weight = (value / 127) * 2;
        this.dispatchPromptChange();
      }
    });
  }

  override firstUpdated() {
    // contenteditable is applied to textInput so we can "shrink-wrap" to text width
    // It's set here and not render() because Lit doesn't believe it's a valid attribute.
    this.textInput.setAttribute('contenteditable', 'plaintext-only');

    // contenteditable will do weird things if this is part of the template.
    this.textInput.textContent = this.text;
    this.lastValidText = this.text;
  }

  update(changedProperties: Map<string, unknown>) {
    if (changedProperties.has('showCC') && !this.showCC) {
      this.learnMode = false;
    }
    if (changedProperties.has('text') && this.textInput) {
      this.textInput.textContent = this.text;
    }
    super.update(changedProperties);
  }

  private dispatchPromptChange() {
    this.dispatchEvent(
      new CustomEvent<Prompt>('prompt-changed', {
        detail: {
          promptId: this.promptId,
          text: this.text,
          weight: this.weight,
          cc: this.cc,
          color: this.color,
        },
      }),
    );
  }

  private async updateText() {
    const oldText = this.text;
    const newText = this.textInput.textContent?.trim();
    if (!newText) {
      this.text = this.lastValidText;
      this.textInput.textContent = this.lastValidText;
    } else {
      this.text = newText;
      this.lastValidText = newText;
    }
    
    if (oldText !== this.text) {
      console.log('PromptController: Text updated for prompt', this.promptId, 'from "' + oldText + '" to "' + this.text + '"');
    }
    
    this.dispatchPromptChange();
  }

  private onFocus() {
    // .select() for contenteditable doesn't work.
    const selection = window.getSelection();
    if (!selection) return;
    const range = document.createRange();
    range.selectNodeContents(this.textInput);
    selection.removeAllRanges();
    selection.addRange(range);
  }

  private updateWeight() {
    const oldWeight = this.weight;
    this.weight = this.weightInput.value;
    console.log('PromptController: Weight updated for prompt', this.promptId, '("' + this.text + '") from', oldWeight.toFixed(2), 'to', this.weight.toFixed(2));
    this.dispatchPromptChange();
  }

  // Add a class based on weight for visual indication
  get promptClasses() {
    return classMap({
      'prompt': true,
      'learn-mode': this.learnMode,
      'show-cc': this.showCC,
      'high-weight': this.weight > 1.5, // Example threshold for high weight
      'medium-weight': this.weight > 0.5 && this.weight <= 1.5, // Example threshold for medium weight
      // No class for low weight (weight <= 0.5)
    });
  }

  private toggleLearnMode() {
    this.learnMode = !this.learnMode;
  }

  override render() {
    return html`<div class=${this.promptClasses}>
      <weight-knob
        id="weight"
        value=${this.weight}
        color=${this.color}
        audioLevel=${this.audioLevel}
        @input=${this.updateWeight}></weight-knob>
      <span
        id="text"
        spellcheck="false"
        @focus=${this.onFocus}
        @blur=${this.updateText}></span>
      <div id="midi" @click=${this.toggleLearnMode}>
        ${this.learnMode ? 'Learn' : `CC:${this.cc}`}
      </div>
    </div>`;
  }
} 