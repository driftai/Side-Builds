import { LitElement } from 'lit';
import { customElement } from 'lit/decorators.js';
import { MidiDispatcher } from '../../../MIDI-&-Control/MidiDispatcher-Component/MidiDispatcher.tsx';
import { PromptDefaults } from '../../../Data-Management/PromptDefaults-Component/PromptDefaults.tsx';

// Import the main component from the parent directory
import { PromptDjMidi } from '../../../MainComponent-Component/PromptDjMidi.tsx';

@customElement('app-initializer')
export class AppInitializer extends LitElement {
  
  static async initialize(parent: HTMLElement) {
    const midiDispatcher = new MidiDispatcher();
    const initialPrompts = PromptDefaults.getInitialPrompts();

    const pdjMidi = new PromptDjMidi(
      initialPrompts,
      midiDispatcher,
    );
    parent.appendChild(pdjMidi);
  }

  override render() {
    // This component doesn't render UI directly, it's an initializer
    return null;
  }
} 