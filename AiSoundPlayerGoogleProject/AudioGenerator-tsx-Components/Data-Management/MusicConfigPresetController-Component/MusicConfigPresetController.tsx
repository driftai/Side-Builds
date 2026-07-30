import { LitElement, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { MusicConfigPreset } from '../../Audio-Processing-Controllers/Utilities-&-Initialization/TypeDefinitions-Component/TypeDefinitions.tsx';
import { type SettingsPersistence } from '../SettingsPersistence-Component/SettingsPersistence.tsx';

@customElement('music-config-preset-controller')
export class MusicConfigPresetController extends LitElement {
    @property({ type: Object }) settingsPersistence?: SettingsPersistence;

    @state() private savedMusicConfigPresets: Map<string, MusicConfigPreset> = new Map();
    @state() private selectedMusicConfigPresetName = '';
    @state() private newPresetName = '';

    private initialized = false;

    private defaultPresets: Map<string, MusicConfigPreset> = new Map([
        ['Dynamic / High Energy', {
            bpm: 140, useDefaultBpm: false,
            density: 0.8, useDefaultDensity: false,
            brightness: 0.9, useDefaultBrightness: false,
            guidance: 4.5, useDefaultGuidance: false,
            temperature: 1.5, useDefaultTemperature: false,
            muteBass: false, muteDrums: false, onlyBassAndDrums: false,
            currentScale: 'SCALE_UNSPECIFIED'
        }],
        ['Chill / Stable', {
            bpm: 90, useDefaultBpm: false,
            density: 0.3, useDefaultDensity: false,
            brightness: 0.4, useDefaultBrightness: false,
            guidance: 4.0, useDefaultGuidance: true,
            temperature: 0.8, useDefaultTemperature: false,
            muteBass: false, muteDrums: false, onlyBassAndDrums: false,
            currentScale: 'C_MAJOR_A_MINOR'
        }],
        ['Strict / Focused', {
            bpm: 120, useDefaultBpm: false,
            density: 0.6, useDefaultDensity: false,
            brightness: 0.6, useDefaultBrightness: false,
            guidance: 6.0, useDefaultGuidance: false,
            temperature: 0.5, useDefaultTemperature: false,
            muteBass: false, muteDrums: false, onlyBassAndDrums: false,
            currentScale: 'E_FLAT_MAJOR_C_MINOR'
        }],
        ['Wild / Chaotic', {
            bpm: 160, useDefaultBpm: false,
            density: 0.9, useDefaultDensity: false,
            brightness: 0.9, useDefaultBrightness: false,
            guidance: 1.0, useDefaultGuidance: false,
            temperature: 2.5, useDefaultTemperature: false,
            muteBass: false, muteDrums: false, onlyBassAndDrums: false,
            currentScale: 'SCALE_UNSPECIFIED'
        }],
        ['Default', {
            bpm: 120, useDefaultBpm: true,
            density: 0.5, useDefaultDensity: true,
            brightness: 0.5, useDefaultBrightness: true,
            guidance: 4.0, useDefaultGuidance: true,
            temperature: 1.1, useDefaultTemperature: true,
            muteBass: false, muteDrums: false, onlyBassAndDrums: false,
            currentScale: 'SCALE_UNSPECIFIED'
        }]
    ]);

    override willUpdate(changedProperties: PropertyValues) {
        if (changedProperties.has('settingsPersistence') && this.settingsPersistence && !this.initialized) {
            this.initialize();
            this.initialized = true;
        }
    }

    initialize() {
        if (!this.settingsPersistence) return;

        // Load presets and refresh state
        this.settingsPersistence.loadMusicConfigPresetsFromStorage();
        const presetData = this.settingsPersistence.presetData;
        this.savedMusicConfigPresets = new Map(presetData.savedMusicConfigPresets);
        this.selectedMusicConfigPresetName = presetData.selectedMusicConfigPresetName;

        // Add default presets if they don't exist
        let defaultsAdded = false;
        this.defaultPresets.forEach((preset, name) => {
            if (!this.savedMusicConfigPresets.has(name)) {
                this.settingsPersistence?.saveCurrentMusicConfigAsPreset(name, preset);
                defaultsAdded = true;
            }
        });

        if (defaultsAdded) {
            // Re-read if we added defaults
            const updatedData = this.settingsPersistence.presetData;
            this.savedMusicConfigPresets = updatedData.savedMusicConfigPresets;
        }

        this.dispatchStateUpdate();
    }

    saveCurrentConfigAsPreset(currentConfig: MusicConfigPreset) {
        if (!this.settingsPersistence) return;
        this.settingsPersistence.saveCurrentMusicConfigAsPreset(this.newPresetName, currentConfig);
        this.refreshState();
    }

    deleteSelectedPreset() {
        if (!this.settingsPersistence) return;
        this.settingsPersistence.deleteMusicConfigPreset(this.selectedMusicConfigPresetName);
        this.refreshState();
    }

    handleNewPresetNameChange(name: string) {
        this.newPresetName = name;
        this.dispatchStateUpdate();
    }

    handleSelectedPresetNameChange(name: string) {
        this.selectedMusicConfigPresetName = name;
        this.settingsPersistence?.updateSelectedMusicConfigPresetName(name);
        this.dispatchStateUpdate();
        this.loadSelectedPreset();
    }

    loadSelectedPreset() {
        if (!this.settingsPersistence || !this.selectedMusicConfigPresetName) return;

        const preset = this.savedMusicConfigPresets.get(this.selectedMusicConfigPresetName);
        if (preset) {
            this.dispatchEvent(new CustomEvent('music-config-preset-loaded', {
                detail: preset,
                bubbles: true,
                composed: true
            }));
        }
    }

    exportPresets() {
        if (!this.savedMusicConfigPresets.size) return;

        const presetsArray = Array.from(this.savedMusicConfigPresets.entries());
        const jsonString = JSON.stringify(presetsArray, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'music-fx-dj-config-presets.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    importPresets(file: File) {
        const reader = new FileReader();
        reader.onload = (event) => {
            try {
                const jsonString = event.target?.result as string;
                const presetsArray: [string, MusicConfigPreset][] = JSON.parse(jsonString);

                const importedPresets = new Map<string, MusicConfigPreset>(presetsArray);
                this.settingsPersistence?.mergeMusicConfigPresets(importedPresets);
                this.refreshState();

            } catch (error) {
                console.error('Failed to import presets:', error);
                this.dispatchEvent(new CustomEvent('toast-message', {
                    detail: 'Failed to import presets. Invalid format.',
                    bubbles: true,
                    composed: true
                }));
            }
        };
        reader.readAsText(file);
    }

    private refreshState() {
        if (!this.settingsPersistence) return;
        const presetData = this.settingsPersistence.presetData;
        this.savedMusicConfigPresets = new Map(presetData.savedMusicConfigPresets);
        this.selectedMusicConfigPresetName = presetData.selectedMusicConfigPresetName;
        this.dispatchStateUpdate();
    }

    private dispatchStateUpdate() {
        this.dispatchEvent(new CustomEvent('music-config-preset-state-updated', {
            detail: {
                savedMusicConfigPresets: this.savedMusicConfigPresets,
                selectedMusicConfigPresetName: this.selectedMusicConfigPresetName,
                newPresetName: this.newPresetName,
            },
            bubbles: true,
            composed: true,
        }));
    }

    override render() {
        return null;
    }
}
