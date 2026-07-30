import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

interface FadeController {
  masterVolume: number;
}

interface SettingsPersistence {
  saveMasterVolume(volume: number): void;
  loadMasterVolume(): number;
}

type PlaybackState = 'stopped' | 'playing' | 'loading' | 'paused';

@customElement('master-volume-controller')
export class MasterVolumeController extends LitElement {
  @property({ type: Object }) outputNode!: GainNode;
  @property({ type: Object }) fadeController!: FadeController;
  @property({ type: Object }) settingsPersistence!: SettingsPersistence;
  @property({ type: String }) playbackState: PlaybackState = 'stopped';

  @state() private masterVolume = 1; // Default master volume

  constructor() {
    super();
    this.handleVolumeChange = this.handleVolumeChange.bind(this);
  }

  override connectedCallback() {
    super.connectedCallback();
    // Load master volume from persistence on component initialization
    if (this.settingsPersistence) {
      this.masterVolume = this.settingsPersistence.loadMasterVolume();
      // CRITICAL FIX: Apply volume immediately on connection
      this.updateAudioNodesImmediate();
      // Dispatch event to sync parent components with the loaded volume
      this.dispatchVolumeChangeEvent();
    }
  }

  override updated(changedProps: Map<string, unknown>) {
    if (changedProps.has('playbackState') || changedProps.has('outputNode')) {
      // Re-apply volume based on new playback state or output node
      this.updateAudioNodesImmediate();
    }
  }

  /**
   * Handles master volume change events
   * @param e CustomEvent containing the new volume value
   */
  handleVolumeChange(e: CustomEvent<number>) {
    console.log('MasterVolumeController: handleVolumeChange called with volume:', e.detail);
    console.log('MasterVolumeController: outputNode available:', !!this.outputNode);
    console.log('MasterVolumeController: current outputNode gain value:', this.outputNode?.gain?.value);

    this.masterVolume = e.detail;

    // CRITICAL FIX: Apply volume changes IMMEDIATELY with forceApply=true
    // This ensures volume changes work regardless of playback state sync issues
    this.updateAudioNodesImmediate(true);
    this.saveMasterVolume();
    this.dispatchVolumeChangeEvent();

    console.log('MasterVolumeController: volume updated to:', this.masterVolume);
    console.log('MasterVolumeController: new outputNode gain value:', this.outputNode?.gain?.value);
  }

  /**
   * Applies the current volume to the assigned output node.
   * This is useful when the output node is recreated.
   */
  applyCurrentVolumeToNode() {
    console.log('MasterVolumeController: applyCurrentVolumeToNode called');
    this.updateAudioNodesImmediate();
  }

  /**
   * Updates audio nodes with the new master volume IMMEDIATELY
   * @param forceApply If true, always applies the master volume (used during volume changes)
   */
  private updateAudioNodesImmediate(forceApply: boolean = false) {
    console.log('MasterVolumeController: updateAudioNodesImmediate called, forceApply:', forceApply);
    console.log('MasterVolumeController: outputNode:', !!this.outputNode);
    console.log('MasterVolumeController: outputNode.gain:', !!this.outputNode?.gain);

    // When forceApply is true (during volume changes), always use master volume
    // Only mute (set to 0) when playback is explicitly stopped AND not forcing
    const effectiveVolume = (forceApply || this.playbackState === 'playing' || this.playbackState === 'loading')
      ? this.masterVolume
      : 0;
    console.log('MasterVolumeController: setting gain to:', effectiveVolume, '(master:', this.masterVolume, 'state:', this.playbackState, 'forceApply:', forceApply, ')');

    if (this.outputNode && this.outputNode.gain) {
      // CRITICAL FIX: Set volume immediately without any ramping for instant response
      this.outputNode.gain.setValueAtTime(effectiveVolume, this.outputNode.context.currentTime);
      console.log('MasterVolumeController: gain value set immediately to:', this.outputNode.gain.value);
    } else {
      console.error('MasterVolumeController: outputNode or gain not available');
    }

    if (this.fadeController) {
      this.fadeController.masterVolume = this.masterVolume;
      console.log('MasterVolumeController: fadeController volume updated to:', this.masterVolume);
    } else {
      console.warn('MasterVolumeController: fadeController not available');
    }
  }

  /**
   * Updates audio nodes with the new master volume (legacy method for compatibility)
   */
  private updateAudioNodes() {
    this.updateAudioNodesImmediate();
  }

  /**
   * Saves the current master volume to persistence
   */
  private saveMasterVolume() {
    if (this.settingsPersistence) {
      this.settingsPersistence.saveMasterVolume(this.masterVolume);
    }
  }

  /**
   * Dispatches a volume change event for parent components
   */
  private dispatchVolumeChangeEvent() {
    this.dispatchEvent(new CustomEvent('master-volume-updated', {
      detail: this.masterVolume,
      bubbles: true,
      composed: true
    }));
  }

  /**
   * Gets the current master volume
   */
  getCurrentVolume(): number {
    return this.masterVolume;
  }

  /**
   * Sets the master volume programmatically
   * @param volume Volume level (0-1)
   */
  setVolume(volume: number) {
    this.masterVolume = Math.max(0, Math.min(1, volume)); // Clamp between 0 and 1
    this.updateAudioNodesImmediate();
    this.saveMasterVolume();
    this.dispatchVolumeChangeEvent();
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 