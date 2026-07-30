import { css, html, LitElement, CSSResultGroup } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

// MidiDispatcher interface for type safety
interface MidiDispatcher {
  activeMidiInputId: string | null;
  getMidiAccess(): Promise<string[]>;
  getDeviceName(id: string): string | null;
}

@customElement('control-buttons-panel')
export class ControlButtonsPanel extends LitElement {
  static override styles = css`
    #buttons {
      position: absolute;
      top: 0;
      left: 0;
      padding: 5px;
      display: flex;
      gap: 5px;
      z-index: 1000;
    }
    button {
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      color: #fff;
      background: #0002;
      -webkit-font-smoothing: antialiased;
      border: 1.5px solid #fff;
      border-radius: 4px;
      user-select: none;
      padding: 3px 6px;
      &.active {
        background-color: #fff;
        color: #000;
      }
    }
    select {
      font: inherit;
      padding: 5px;
      background: #fff;
      color: #000;
      border-radius: 4px;
      border: none;
      outline: none;
      cursor: pointer;
    }
    .dimmer-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(0, 0, 0, 0.5);
      pointer-events: none;
      z-index: 999;
    }
  ` as CSSResultGroup;

  @property({ type: Boolean }) showMidi = false;
  @property({ type: Number }) masterVolume = 1;
  @property({ type: Array }) midiInputIds: string[] = [];
  @property({ type: String }) activeMidiInputId: string | null = null;
  @property({ type: Object }) midiDispatcher!: MidiDispatcher;

  @state() private dimmerActive = false;

  private emitEvent(eventName: string, detail?: any) {
    this.dispatchEvent(new CustomEvent(eventName, { detail, bubbles: true, composed: true }));
  }

  private handleToggleShowMidi() {
    this.emitEvent('toggle-show-midi');
  }

  private handleToggleSettingsPanel() {
    this.emitEvent('toggle-settings-panel');
  }

  private handleMasterVolumeChange(e: CustomEvent<number>) {
    console.log('ControlButtonsPanel: Received volume change:', e.detail);
    this.emitEvent('master-volume-change', e.detail);
    console.log('ControlButtonsPanel: Emitted master-volume-change event');
  }

  private handleMidiInputChange(event: Event) {
    const selectElement = event.target as HTMLSelectElement;
    const newMidiId = selectElement.value;
    this.emitEvent('midi-input-change', newMidiId);
  }

  private toggleDimmer() {
    this.dimmerActive = !this.dimmerActive;
  }

  override render() {
    return html`
      ${this.dimmerActive ? html`<div class="dimmer-overlay"></div>` : ''}
      <div id="buttons">
        <button
          @click=${this.toggleDimmer}
          class=${this.dimmerActive ? 'active' : ''}
          title="Toggle Screen Dimmer"
          >🌙</button
        >
        <button
          @click=${this.handleToggleShowMidi}
          class=${this.showMidi ? 'active' : ''}
          title="Toggle MIDI Settings"
          >MIDI</button
        >
        <button @click=${this.handleToggleSettingsPanel} title="Playback Settings">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-gear-fill" viewBox="0 0 16 16">
            <path d="M9.405 1.05c-.413-1.4-2.397-1.4-2.81 0l-.1.34a1.464 1.464 0 0 1-2.105.872l-.31-.17c-1.283-.698-2.686.705-1.987 1.987l.169.311a1.464 1.464 0 0 1-.872 2.105l-.34.1c-1.4.413-1.4 2.397 0 2.81l.34.1a1.464 1.464 0 0 1 .872 2.105l-.17.31c-.698 1.283.705 2.686 1.987 1.987l.311-.169a1.464 1.464 0 0 1 2.105.872l.1.34c.413 1.4 2.397 1.4 2.81 0l.1-.34a1.464 1.464 0 0 1 2.105-.872l.31.17c1.283.698 2.686-.705 1.987-1.987l-.169-.311a1.464 1.464 0 0 1 .872-2.105l.34-.1c1.4-.413-1.4-2.397 0-2.81l-.34-.1a1.464 1.464 0 0 1-.872-2.105l.17-.31c.698-1.283-.705-2.686-1.987-1.987l-.311.169a1.464 1.464 0 0 1-2.105-.872l-.1-.34zM8 10.93a2.929 2.929 0 1 1 0-5.858 2.929 2.929 0 0 1 0 5.858z"/>
          </svg>
        </button>
        <button @click=${() => this.emitEvent('reset-music-context')} title="Reset Music Context - Break out of current beat/mood">
          🔄
        </button>
        <button @click=${() => this.emitEvent('toggle-grid-size')} title="Toggle Grid Size (3x3, 4x4, 5x5)">
          ⊞
        </button>
        <volume-button
          .value=${this.masterVolume}
          @input=${this.handleMasterVolumeChange}
          title="Master Volume"
          style="width: 50px; height: 50px; /* Adjust size as needed */"
        ></volume-button>
        <select
          @change=${this.handleMidiInputChange}
          .value=${this.activeMidiInputId || ''}
          style=${this.showMidi ? '' : 'visibility: hidden'}>
          ${this.midiInputIds.length > 0
        ? this.midiInputIds.map(
          (id) =>
            html`<option value=${id}>
                    ${this.midiDispatcher.getDeviceName(id)}
                  </option>`,
        )
        : html`<option value="">No devices found</option>`}
        </select>
      </div>
    `;
  }
} 