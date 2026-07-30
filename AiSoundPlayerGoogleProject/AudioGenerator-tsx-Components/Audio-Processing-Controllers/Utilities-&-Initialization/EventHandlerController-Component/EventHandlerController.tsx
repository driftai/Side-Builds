import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';

// Component dependencies for event delegation
interface UIStateController {
  toggleSettingsPanel(): void;
  setVisualizationMode(mode: any): void;
}

interface PlaybackDurationController {
  updateDurationMode(mode: 'indefinite' | 'timed'): void;
  updateDurationMinutes(minutes: number): void;
}

interface MasterVolumeController {
  handleVolumeChange(event: CustomEvent<number>): void;
}

interface MidiUIController {
  handleMidiInputChange(event: Event | CustomEvent): { activeMidiInputId: string | null };
}

/**
 * EventHandlerController - Manages event delegation for the main component
 * Centralizes simple event handlers that just delegate to other components
 */
@customElement('event-handler-controller')
export class EventHandlerController extends LitElement {
  // Component dependencies
  @property({ type: Object }) uiStateController!: UIStateController;
  @property({ type: Object }) playbackDurationController!: PlaybackDurationController;
  @property({ type: Object }) masterVolumeController!: MasterVolumeController;
  @property({ type: Object }) midiUIController!: MidiUIController;

  // Callback functions for complex operations that need to stay in main component
  @property({ type: Function }) toggleShowMidi!: () => Promise<void>;
  @property({ type: Function }) onMasterVolumeChange!: (volume: number) => void;
  @property({ type: Function }) onMidiInputChange!: (activeMidiInputId: string | null) => void;

  /**
   * Handle toggle MIDI show/hide
   */
  handleToggleShowMidi() {
    this.toggleShowMidi();
  }

  /**
   * Handle toggle settings panel
   */
  handleToggleSettingsPanel() {
    this.uiStateController.toggleSettingsPanel();
  }

  /**
   * Handle duration mode change (indefinite vs timed)
   */
  handleDurationModeChange(e: Event) {
    const selectElement = e.target as HTMLSelectElement;
    this.playbackDurationController.updateDurationMode(selectElement.value as 'indefinite' | 'timed');
  }

  /**
   * Handle duration minutes change
   */
  handleDurationMinutesChange(e: Event) {
    const inputElement = e.target as HTMLInputElement;
    this.playbackDurationController.updateDurationMinutes(parseInt(inputElement.value, 10) || 30);
  }

  /**
   * Handle visualization mode change
   */
  handleVisualizationModeChange(e: CustomEvent) {
    this.uiStateController.setVisualizationMode(e.detail);
  }

  /**
   * Handle master volume change with state synchronization
   */
  handleMasterVolumeChange(e: CustomEvent<number>) {
    console.log('EventHandlerController: handleMasterVolumeChange called with volume:', e.detail);
    
    // Create a properly formatted CustomEvent for MasterVolumeController
    const volumeEvent = new CustomEvent<number>('volume-change', {
      detail: e.detail,
      bubbles: true,
      composed: true
    });
    
    // Delegate to MasterVolumeController
    this.masterVolumeController.handleVolumeChange(volumeEvent);
    
    // Notify main component of the change for state sync
    this.onMasterVolumeChange(e.detail);
    
    console.log('EventHandlerController: Master volume change processed');
  }

  /**
   * Handle MIDI input change
   */
  handleMidiInputChange(event: Event | CustomEvent) {
    // Delegate to MidiUIController and get result
    const result = this.midiUIController.handleMidiInputChange(event);
    
    // Notify main component of the change for state sync
    this.onMidiInputChange(result.activeMidiInputId);
  }

  /**
   * Get all event handlers as an object for easy binding
   */
  getEventHandlers() {
    return {
      handleToggleShowMidi: this.handleToggleShowMidi.bind(this),
      handleToggleSettingsPanel: this.handleToggleSettingsPanel.bind(this),
      handleDurationModeChange: this.handleDurationModeChange.bind(this),
      handleDurationMinutesChange: this.handleDurationMinutesChange.bind(this),
      handleVisualizationModeChange: this.handleVisualizationModeChange.bind(this),
      handleMasterVolumeChange: this.handleMasterVolumeChange.bind(this),
      handleMidiInputChange: this.handleMidiInputChange.bind(this)
    };
  }

  override render() {
    return null; // This is a logic-only component, no UI
  }
} 