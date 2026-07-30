import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

interface MidiDispatcher {
  activeMidiInputId: string | null;
  getMidiAccess(): Promise<string[]>;
  getDeviceName(id: string): string | null;
}

@customElement('midi-ui-controller')
export class MidiUIController extends LitElement {
  @property({ type: Object }) midiDispatcher!: MidiDispatcher;
  @property({ type: Boolean }) showMidi = false;
  @property({ type: Array }) midiInputIds: string[] = [];
  @property({ type: String }) activeMidiInputId: string | null = null;
  @property({ type: Object }) filteredPrompts = new Set<string>();

  /**
   * Toggles the MIDI display and refreshes MIDI device list if showing
   */
  async toggleShowMidi(): Promise<{ 
    showMidi: boolean; 
    midiInputIds: string[]; 
    activeMidiInputId: string | null; 
    filteredPrompts: Set<string>; 
  }> {
    this.showMidi = !this.showMidi;
    
    if (!this.showMidi) {
      return {
        showMidi: this.showMidi,
        midiInputIds: this.midiInputIds,
        activeMidiInputId: this.activeMidiInputId,
        filteredPrompts: this.filteredPrompts
      };
    }

    // Get available MIDI devices
    const inputIds = await this.midiDispatcher.getMidiAccess();
    this.midiInputIds = inputIds.filter((id): id is string => typeof id === 'string');
    this.activeMidiInputId = this.midiDispatcher.activeMidiInputId;
    
    // Update filtered prompts with MIDI input IDs
    this.filteredPrompts = new Set(this.midiInputIds);
    if (this.activeMidiInputId && typeof this.activeMidiInputId === 'string') {
      this.filteredPrompts.add(this.activeMidiInputId);
    }

    // Dispatch state change event
    this.dispatchStateChangeEvent();

    return {
      showMidi: this.showMidi,
      midiInputIds: this.midiInputIds,
      activeMidiInputId: this.activeMidiInputId,
      filteredPrompts: this.filteredPrompts
    };
  }

  /**
   * Handles MIDI input selection change
   */
  handleMidiInputChange(event: Event | CustomEvent): { activeMidiInputId: string | null } {
    let newMidiId: string;
    
    if (event instanceof CustomEvent) {
      newMidiId = event.detail;
    } else {
      const selectElement = event.target as HTMLSelectElement;
      newMidiId = selectElement.value;
    }
    
    this.activeMidiInputId = newMidiId;
    this.midiDispatcher.activeMidiInputId = newMidiId;

    // Dispatch state change event
    this.dispatchStateChangeEvent();

    return { activeMidiInputId: this.activeMidiInputId };
  }

  /**
   * Dispatches a state change event to notify parent components
   */
  private dispatchStateChangeEvent() {
    this.dispatchEvent(new CustomEvent('midi-ui-state-change', {
      detail: {
        showMidi: this.showMidi,
        midiInputIds: this.midiInputIds,
        activeMidiInputId: this.activeMidiInputId,
        filteredPrompts: this.filteredPrompts
      },
      bubbles: true,
      composed: true
    }));
  }

  /**
   * Gets current MIDI UI state
   */
  getCurrentState() {
    return {
      showMidi: this.showMidi,
      midiInputIds: this.midiInputIds,
      activeMidiInputId: this.activeMidiInputId,
      filteredPrompts: this.filteredPrompts
    };
  }

  /**
   * Updates the internal state from external sources
   */
  updateState(state: {
    showMidi?: boolean;
    midiInputIds?: string[];
    activeMidiInputId?: string | null;
    filteredPrompts?: Set<string>;
  }) {
    if (state.showMidi !== undefined) this.showMidi = state.showMidi;
    if (state.midiInputIds !== undefined) this.midiInputIds = state.midiInputIds;
    if (state.activeMidiInputId !== undefined) this.activeMidiInputId = state.activeMidiInputId;
    if (state.filteredPrompts !== undefined) this.filteredPrompts = state.filteredPrompts;
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 