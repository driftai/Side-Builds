import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

type PlaybackState = 'stopped' | 'playing' | 'loading' | 'paused';

interface Prompt {
  readonly promptId: string;
  text: string;
  weight: number;
  cc: number;
  color: string;
}

import { MusicConfigPreset } from '../../Audio-Processing-Controllers/Utilities-&-Initialization/TypeDefinitions-Component/TypeDefinitions.tsx';

interface ToastMessage {
  show(message: string): void;
}

@customElement('settings-persistence')
export class SettingsPersistence extends LitElement {
  @property({ type: Object }) toastMessage?: ToastMessage;
  @property({ type: Object }) prompts: Map<string, Prompt> = new Map();

  @state() private savedKnobPresets: Map<string, Map<string, Prompt>> = new Map();
  @state() private selectedPresetName = '';
  @state() private newPresetName = '';

  // Music Config Presets State
  @state() private savedMusicConfigPresets: Map<string, MusicConfigPreset> = new Map();
  @state() private selectedMusicConfigPresetName = '';

  constructor() {
    super();
  }

  /**
   * Load master volume from localStorage with validation
   * @returns Master volume value between 0 and 1
   */
  loadMasterVolume(): number {
    const savedVolume = localStorage.getItem('masterVolume');
    if (savedVolume !== null) {
      const volume = parseFloat(savedVolume);
      // Ensure loaded volume is within valid range [0, 1]
      return Math.max(0, Math.min(1, volume));
    }
    return 1; // Default volume
  }

  /**
   * Save master volume to localStorage
   * @param volume Volume value to save
   */
  saveMasterVolume(volume: number): void {
    localStorage.setItem('masterVolume', volume.toString());
  }

  /**
   * Load playback state from localStorage
   * @returns Restored playback state or 'playing' as default to enable auto-play on load
   */
  loadPlaybackState(): PlaybackState {
    const savedState = localStorage.getItem('playbackState');
    if (savedState && ['stopped', 'playing', 'paused'].includes(savedState)) {
      return savedState as PlaybackState;
    } else if (savedState === 'loading') {
      // Treat persisted 'loading' as 'playing' to avoid getting stuck after reconnection
      return 'playing';
    }
    return 'playing'; // Default to 'playing' for auto-play on page load
  }

  /**
   * Save playback state to localStorage
   * @param state Playback state to save
   */
  savePlaybackState(state: PlaybackState): void {
    // Avoid saving transient 'loading' state to prevent resume issues
    if (state !== 'loading') {
      localStorage.setItem('playbackState', state);
    }
  }

  /**
   * Clear playback state from localStorage
   * Used when user explicitly stops or disconnects
   */
  clearPlaybackState(): void {
    localStorage.removeItem('playbackState');
  }

  /**
   * Load fade settings from localStorage
   * @returns Object containing fadeInDurationSec and fadeOutDurationSec, or null if not found
   */
  loadFadeSettings(): { fadeInDurationSec: number, fadeOutDurationSec: number } | null {
    const fadeIn = localStorage.getItem('fadeInDurationSec');
    const fadeOut = localStorage.getItem('fadeOutDurationSec');

    if (fadeIn !== null && fadeOut !== null) {
      return {
        fadeInDurationSec: parseFloat(fadeIn),
        fadeOutDurationSec: parseFloat(fadeOut)
      };
    }
    return null;
  }

  /**
   * Save fade settings to localStorage
   * @param fadeInDurationSec Fade-in duration in seconds
   * @param fadeOutDurationSec Fade-out duration in seconds
   */
  saveFadeSettings(fadeInDurationSec: number, fadeOutDurationSec: number): void {
    localStorage.setItem('fadeInDurationSec', fadeInDurationSec.toString());
    localStorage.setItem('fadeOutDurationSec', fadeOutDurationSec.toString());
  }

  /**
   * Load presets from localStorage
   */
  loadPresetsFromStorage(): void {
    const storedPresets = localStorage.getItem('knobPresets');
    if (storedPresets) {
      try {
        const parsed = JSON.parse(storedPresets) as Record<string, Prompt[]>;
        const presetsMap = new Map<string, Map<string, Prompt>>();
        for (const [name, promptsArray] of Object.entries(parsed)) {
          const promptsMap = new Map<string, Prompt>();
          promptsArray.forEach(p => promptsMap.set(p.promptId, p));
          presetsMap.set(name, promptsMap);
        }
        this.savedKnobPresets = presetsMap;
        if (this.savedKnobPresets.size > 0) {
          this.selectedPresetName = this.savedKnobPresets.keys().next().value ?? '';
        }
      } catch (e) {
        console.error('Failed to load knob presets from localStorage:', e);
        this.savedKnobPresets = new Map();
      }
    }

    const storedSelected = localStorage.getItem('selectedPresetName');
    if (storedSelected) {
      try {
        this.selectedPresetName = JSON.parse(storedSelected);
      } catch (e) {
        console.error('Failed to parse selected preset name:', e);
        if (this.toastMessage) this.toastMessage.show('Failed to load selected preset name from storage');
      }
    }

    // Load Music Config Presets
    const storedConfigPresets = localStorage.getItem('musicConfigPresets');
    if (storedConfigPresets) {
      try {
        const parsed = JSON.parse(storedConfigPresets) as Record<string, MusicConfigPreset>;
        const configPresetsMap = new Map<string, MusicConfigPreset>(Object.entries(parsed));
        this.savedMusicConfigPresets = configPresetsMap;
      } catch (e) {
        console.error('Failed to load music config presets:', e);
        this.savedMusicConfigPresets = new Map();
      }
    }

    const storedSelectedConfig = localStorage.getItem('selectedMusicConfigPresetName');
    if (storedSelectedConfig) {
      try {
        this.selectedMusicConfigPresetName = JSON.parse(storedSelectedConfig);
      } catch (e) {
        console.error('Failed to parse selected music config preset name:', e);
      }
    }
  }

  /**
   * Load Music Config Presets from localStorage
   */
  loadMusicConfigPresetsFromStorage(): void {
    const storedConfigPresets = localStorage.getItem('musicConfigPresets');
    if (storedConfigPresets) {
      try {
        const parsed = JSON.parse(storedConfigPresets) as Record<string, MusicConfigPreset>;
        const configPresetsMap = new Map<string, MusicConfigPreset>(Object.entries(parsed));
        this.savedMusicConfigPresets = configPresetsMap;
      } catch (e) {
        console.error('Failed to load music config presets:', e);
        this.savedMusicConfigPresets = new Map();
      }
    }

    const storedSelectedConfig = localStorage.getItem('selectedMusicConfigPresetName');
    if (storedSelectedConfig) {
      try {
        this.selectedMusicConfigPresetName = JSON.parse(storedSelectedConfig);
      } catch (e) {
        console.error('Failed to parse selected music config preset name:', e);
      }
    }
  }

  /**
   * Save presets to localStorage
   */
  saveKnobPresetsToStorage(): void {
    const presetsToStore: Record<string, Prompt[]> = {};
    for (const [name, promptsMap] of this.savedKnobPresets.entries()) {
      presetsToStore[name] = Array.from(promptsMap.values());
    }
    localStorage.setItem('knobPresets', JSON.stringify(presetsToStore));
    localStorage.setItem('selectedPresetName', JSON.stringify(this.selectedPresetName));
  }

  /**
   * Save Music Config Presets to localStorage
   */
  saveMusicConfigPresetsToStorage(): void {
    const presetsToStore: Record<string, MusicConfigPreset> = Object.fromEntries(this.savedMusicConfigPresets);
    localStorage.setItem('musicConfigPresets', JSON.stringify(presetsToStore));
    localStorage.setItem('selectedMusicConfigPresetName', JSON.stringify(this.selectedMusicConfigPresetName));
  }

  /**
   * Update new preset name
   */
  updateNewPresetName(name: string): void {
    this.newPresetName = name;
  }

  /**
   * Update selected preset name
   */
  updateSelectedPresetName(name: string): void {
    this.selectedPresetName = name;
    this.saveKnobPresetsToStorage(); // Save the updated selected name
  }

  /**
   * Save current prompts as a new preset
   */
  saveCurrentKnobsAsPreset(): boolean {
    const trimmedName = this.newPresetName.trim();
    if (!trimmedName) {
      this.toastMessage?.show('Please enter a name for the preset.');
      return false;
    }

    // Check if preset already exists and confirm overwrite
    if (this.savedKnobPresets.has(trimmedName)) {
      if (!window.confirm(`Preset '${trimmedName}' already exists. Overwrite it?`)) {
        this.toastMessage?.show('Update cancelled.');
        return false;
      }
    }

    const currentPromptsCopy = new Map<string, Prompt>();
    this.prompts.forEach((value, key) => {
      currentPromptsCopy.set(key, { ...value }); // Create a shallow copy of each prompt
    });
    this.savedKnobPresets.set(trimmedName, currentPromptsCopy);
    this.saveKnobPresetsToStorage();
    this.toastMessage?.show(this.savedKnobPresets.has(trimmedName) ? `Preset '${trimmedName}' updated.` : `Preset '${trimmedName}' saved.`);
    this.newPresetName = ''; // Clear input field
    if (!this.selectedPresetName && this.savedKnobPresets.size > 0) {
      this.selectedPresetName = trimmedName; // Select the newly saved/updated preset if none was selected
    } else if (!this.savedKnobPresets.has(this.selectedPresetName) && this.savedKnobPresets.size > 0) {
      // If the previously selected preset was deleted or its name changed somehow (not via this flow), select first available
      this.selectedPresetName = this.savedKnobPresets.keys().next().value ?? '';
    }
    this.requestUpdate(); // To update the dropdown and button states
    return true;
  }

  /**
   * Load selected preset
   * @returns Map of prompts if successful, null otherwise
   */
  loadSelectedPreset(): Map<string, Prompt> | null {
    if (!this.selectedPresetName || !this.savedKnobPresets.has(this.selectedPresetName)) {
      this.toastMessage?.show('No preset selected or found.');
      return null;
    }
    const presetPrompts = this.savedKnobPresets.get(this.selectedPresetName)!;
    const newPromptsToLoad = new Map<string, Prompt>();
    presetPrompts.forEach((value, key) => {
      newPromptsToLoad.set(key, { ...value }); // Deep copy
    });
    this.toastMessage?.show(`Preset '${this.selectedPresetName}' loaded.`);
    return newPromptsToLoad;
  }

  /**
   * Delete selected preset
   */
  deleteSelectedPreset(): void {
    if (this.savedKnobPresets.has(this.selectedPresetName)) {
      this.savedKnobPresets.delete(this.selectedPresetName);
      this.saveKnobPresetsToStorage();
      this.toastMessage?.show(`Preset "${this.selectedPresetName}" deleted.`);
      // Select the first preset in the list or none if empty
      this.selectedPresetName = this.savedKnobPresets.keys().next().value || '';
      this.requestUpdate();
    } else {
      this.toastMessage?.show(`Preset "${this.selectedPresetName}" not found.`);
    }
  }

  mergePresets(importedPresets: Map<string, Map<string, Prompt>>): void {
    let importedCount = 0;
    let overwrittenCount = 0;

    importedPresets.forEach((value, key) => {
      if (this.savedKnobPresets.has(key)) {
        overwrittenCount++;
      } else {
        importedCount++;
      }
      this.savedKnobPresets.set(key, value);
    });

    this.saveKnobPresetsToStorage();
    this.toastMessage?.show(`Import complete. Added: ${importedCount}, Overwritten: ${overwrittenCount}.`);
  }

  // --- Music Config Preset Methods ---

  saveCurrentMusicConfigAsPreset(name: string, config: MusicConfigPreset): void {
    const trimmedName = name.trim();
    if (!trimmedName) {
      this.toastMessage?.show('Please enter a name for the preset.');
      return;
    }

    if (this.savedMusicConfigPresets.has(trimmedName)) {
      if (!window.confirm(`Preset '${trimmedName}' already exists. Overwrite it?`)) {
        return;
      }
    }

    this.savedMusicConfigPresets.set(trimmedName, { ...config });
    this.selectedMusicConfigPresetName = trimmedName;
    this.saveMusicConfigPresetsToStorage();
    this.toastMessage?.show(`Music Preset '${trimmedName}' saved.`);
    this.requestUpdate();
  }

  deleteMusicConfigPreset(name: string): void {
    if (this.savedMusicConfigPresets.has(name)) {
      this.savedMusicConfigPresets.delete(name);
      if (this.selectedMusicConfigPresetName === name) {
        this.selectedMusicConfigPresetName = '';
      }
      this.saveMusicConfigPresetsToStorage();
      this.toastMessage?.show(`Music Preset '${name}' deleted.`);
      this.requestUpdate();
    }
  }

  updateSelectedMusicConfigPresetName(name: string): void {
    this.selectedMusicConfigPresetName = name;
    this.saveMusicConfigPresetsToStorage();
  }

  mergeMusicConfigPresets(importedPresets: Map<string, MusicConfigPreset>): void {
    let importedCount = 0;
    let overwrittenCount = 0;

    importedPresets.forEach((value, key) => {
      if (this.savedMusicConfigPresets.has(key)) {
        overwrittenCount++;
      } else {
        importedCount++;
      }
      this.savedMusicConfigPresets.set(key, value);
    });

    this.saveMusicConfigPresetsToStorage();
    this.toastMessage?.show(`Music Config Import complete. Added: ${importedCount}, Overwritten: ${overwrittenCount}.`);
  }

  /**
   * Get current preset data
   */
  get presetData() {
    return {
      savedKnobPresets: this.savedKnobPresets,
      selectedPresetName: this.selectedPresetName,
      newPresetName: this.newPresetName,
      savedMusicConfigPresets: this.savedMusicConfigPresets,
      selectedMusicConfigPresetName: this.selectedMusicConfigPresetName
    };
  }

  override render() {
    // This component doesn't render UI directly, it's a utility component
    return null;
  }
}