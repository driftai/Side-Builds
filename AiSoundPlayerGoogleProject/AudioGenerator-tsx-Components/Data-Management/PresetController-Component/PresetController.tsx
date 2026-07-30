import { LitElement, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { type Prompt } from '../../Audio-Processing-Controllers/Utilities-&-Initialization/TypeDefinitions-Component/TypeDefinitions.tsx';
import { type SettingsPersistence } from '../SettingsPersistence-Component/SettingsPersistence.tsx';

@customElement('preset-controller')
export class PresetController extends LitElement {
  @property({ type: Object }) settingsPersistence?: SettingsPersistence;

  // The controller needs to know about the current prompts to save them.
  private _prompts: Map<string, Prompt> = new Map();

  @property({ type: Object })
  get prompts(): Map<string, Prompt> {
    return this._prompts;
  }

  set prompts(prompts: Map<string, Prompt>) {
    this._prompts = prompts;
    if (this.settingsPersistence) {
      this.settingsPersistence.prompts = prompts;
    }
  }

  @state() private savedKnobPresets: Map<string, Map<string, Prompt>> = new Map();
  @state() private selectedPresetName = '';
  @state() private newPresetName = '';

  private initialized = false;

  override willUpdate(changedProperties: PropertyValues) {
    if (changedProperties.has('settingsPersistence') && this.settingsPersistence && !this.initialized) {
      this.initialize();
      this.initialized = true;
    }
  }

  /**
   * Loads initial preset data from storage and notifies the parent.
   */
  initialize() {
    if (!this.settingsPersistence) {
      console.warn('Cannot initialize PresetController: SettingsPersistence not set.');
      return;
    }
    this.settingsPersistence.loadPresetsFromStorage();
    const presetData = this.settingsPersistence.presetData;
    this.savedKnobPresets = presetData.savedKnobPresets;
    this.selectedPresetName = presetData.selectedPresetName;
    this.newPresetName = presetData.newPresetName;
    // Do not auto-load the selected preset; allow random initialization on page load
    // if (this.selectedPresetName && this.savedKnobPresets.has(this.selectedPresetName)) {
    //   this.loadSelectedPreset();
    // }
    this.dispatchStateUpdate();
  }

  handleNewPresetNameChange(name: string) {
    this.newPresetName = name;
    this.settingsPersistence?.updateNewPresetName(name);
    this.dispatchStateUpdate();
  }

  handleSelectedPresetNameChange(name: string) {
    this.selectedPresetName = name;
    this.settingsPersistence?.updateSelectedPresetName(name);
    this.dispatchStateUpdate();
  }

  exportPresets() {
    if (!this.settingsPersistence) {
      console.warn('Cannot export presets: SettingsPersistence not set.');
      return;
    }
    const presetsToExport = this.settingsPersistence.presetData.savedKnobPresets;
    if (presetsToExport.size === 0) {
      this.dispatchEvent(new CustomEvent('toast-message', {
        detail: 'No presets to export.',
        bubbles: true,
        composed: true
      }));
      return;
    }

    // Convert Map to an array of [key, value] pairs for JSON serialization
    const presetsArray = Array.from(presetsToExport.entries()).map(([key, value]) => {
      return [key, Array.from(value.entries())];
    });

    const jsonString = JSON.stringify(presetsArray, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'prompt-dj-presets.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  importPresets(file: File) {
    if (!this.settingsPersistence) {
      console.warn('Cannot import presets: SettingsPersistence not set.');
      return;
    }
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const jsonString = event.target?.result as string;
        const presetsArray: [string, [string, Prompt][]][] = JSON.parse(jsonString);

        if (!Array.isArray(presetsArray)) {
          throw new Error('Invalid preset file format.');
        }

        // Convert array back to Map with correct types
        const importedPresets = new Map<string, Map<string, Prompt>>(
          presetsArray.map(([presetName, prompts]) => [presetName, new Map<string, Prompt>(prompts)])
        );

        // Merge with existing presets
        this.settingsPersistence?.mergePresets(importedPresets);

        // Reload and update UI
        this.initialize();

        this.dispatchEvent(new CustomEvent('toast-message', {
          detail: 'Presets imported successfully.',
          bubbles: true,
          composed: true
        }));

      } catch (error: any) {
        this.dispatchEvent(new CustomEvent('toast-message', {
          detail: `Error importing presets: ${error.message}`,
          bubbles: true,
          composed: true
        }));
      }
    };
    reader.readAsText(file);
  }

  saveCurrentKnobsAsPreset() {
    if (!this.settingsPersistence) {
      console.warn('Cannot save preset: SettingsPersistence not set.');
      return;
    }
    const success = this.settingsPersistence.saveCurrentKnobsAsPreset();
    if (success) {
      const presetData = this.settingsPersistence.presetData;
      this.savedKnobPresets = presetData.savedKnobPresets;
      this.selectedPresetName = presetData.selectedPresetName;
      this.newPresetName = presetData.newPresetName;
      this.dispatchStateUpdate();
    }
  }

  loadSelectedPreset() {
    if (!this.settingsPersistence) {
      console.warn('Cannot load preset: SettingsPersistence not set.');
      return;
    }
    const loadedPrompts = this.settingsPersistence.loadSelectedPreset();
    if (loadedPrompts) {
      // Notify parent to update the main prompts state
      this.dispatchEvent(new CustomEvent('preset-prompts-loaded', {
        detail: loadedPrompts,
        bubbles: true,
        composed: true,
      }));
    }
  }

  deleteSelectedPreset() {
    if (!this.settingsPersistence) {
      console.warn('Cannot delete preset: SettingsPersistence not set.');
      return;
    }
    this.settingsPersistence.deleteSelectedPreset();
    const presetData = this.settingsPersistence.presetData;
    this.savedKnobPresets = presetData.savedKnobPresets;
    this.selectedPresetName = presetData.selectedPresetName;
    this.newPresetName = presetData.newPresetName;
    this.dispatchStateUpdate();
  }

  /**
   * Dispatches an event with the current preset data so the UI can update.
   */
  private dispatchStateUpdate() {
    this.dispatchEvent(new CustomEvent('preset-data-updated', {
      detail: {
        savedKnobPresets: this.savedKnobPresets,
        selectedPresetName: this.selectedPresetName,
        newPresetName: this.newPresetName,
      },
      bubbles: true,
      composed: true,
    }));
  }

  override render() {
    // This is a controller component and does not render UI
    return null;
  }
}