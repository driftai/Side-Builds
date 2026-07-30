import { css, html, LitElement } from 'lit';
import { customElement, property, state, query } from 'lit/decorators.js';
import type { VisualizationMode, MusicConfigPreset } from '../../Audio-Processing-Controllers/Utilities-&-Initialization/TypeDefinitions-Component/TypeDefinitions.tsx';
import '../../Data-Management/MusicConfigPresetController-Component/MusicConfigPresetController.tsx';
import { type MusicConfigPresetController } from '../../Data-Management/MusicConfigPresetController-Component/MusicConfigPresetController.tsx';
import { type PresetController } from '../../Data-Management/PresetController-Component/PresetController.tsx';
import { SettingsPersistence } from '../../Data-Management/SettingsPersistence-Component/SettingsPersistence.tsx';

interface ToastMessage {
  show(message: string): void;
}

@customElement('settings-panel')
export class SettingsPanel extends LitElement {
  static override styles = css`
    .settings-panel {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background-color: rgba(0,0,0,0.9);
      color: white;
      padding: 20px;
      border-radius: 8px;
      z-index: 100;
      display: flex;
      flex-direction: column;
      gap: 15px;
      border: 1px solid #555;
      width: 90%;
      max-width: 600px;
      box-sizing: border-box;
      overflow-y: auto;
      max-height: 90%;
    }
    .settings-panel h3 {
      margin-top: 0;
      text-align: center;
    }
    .settings-panel label {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .settings-panel input[type="number"] {
      width: 60px;
      padding: 5px;
      border-radius: 4px;
      border: 1px solid #ccc;
      background: #333;
      color: white;
    }
    .slider-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
    }
    .slider-row label {
      min-width: 180px;
      flex-shrink: 0;
    }
    .slider-row input[type="range"] {
      flex: 1;
      min-width: 100px;
      height: 6px;
      -webkit-appearance: none;
      appearance: none;
      background: linear-gradient(to right, #666, #fff);
      border-radius: 3px;
      cursor: pointer;
    }
    .slider-row input[type="range"]:disabled {
      opacity: 0.3;
      cursor: not-allowed;
    }
    .slider-row input[type="range"]::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: #fff;
      border: 2px solid #333;
      cursor: pointer;
    }
    .slider-row input[type="range"]::-moz-range-thumb {
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: #fff;
      border: 2px solid #333;
      cursor: pointer;
    }
    .slider-value {
      min-width: 45px;
      text-align: right;
      font-family: monospace;
      color: #0ff;
    }
    .model-decides-row {
      display: flex;
      align-items: center;
      gap: 5px;
      margin-left: 190px;
      margin-bottom: 12px;
      font-size: 0.9em;
      opacity: 0.8;
    }
    .settings-panel button {
      padding: 8px 12px;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      color: #fff;
      background: #0002;
      -webkit-font-smoothing: antialiased;
      border: 1.5px solid #fff;
      border-radius: 4px;
      user-select: none;
    }
    .settings-panel button:hover {
      background-color: #fff;
      color: #000;
    }
    .settings-panel button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .settings-panel button:disabled:hover {
      background: #0002;
      color: #fff;
    }
    .settings-section {
      margin-bottom: 15px;
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
    .button-like-label {
      padding: 4px 8px;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      color: #fff;
      background: #0002;
      -webkit-font-smoothing: antialiased;
      border: 1.5px solid #fff;
      border-radius: 4px;
      user-select: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;
    }
    .button-like-label:hover {
      background-color: #fff;
      color: #000;
    }
    .preset-row > button {
      padding: 4px 8px;
    }
    .preset-buttons {
      display: flex;
      gap: 5px;
      align-items: center;
    }
    .preset-row {
      display: flex;
      gap: 10px;
      align-items: center;
      margin-bottom: 10px;
    }
    .preset-row:last-child {
      margin-bottom: 0;
    }
    .preset-row > input[type="text"], .preset-row > select {
      flex-grow: 1;
      min-width: 100px;
    }
    .preset-row > button, .preset-row > .button-like-label {
      flex-shrink: 0;
    }
    .preset-actions {
      margin-top: 10px;
      display: flex;
      gap: 10px;
    }
    .import-btn {
      padding: 8px 12px;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      color: #fff;
      background: #0002;
      -webkit-font-smoothing: antialiased;
      border: 1.5px solid #fff;
      border-radius: 4px;
      user-select: none;
      display: inline-block;
    }
    .import-btn:hover {
      background-color: #fff;
      color: #000;
    }
    .import-btn input[type="file"] {
      display: none;
    }
  `;

  @property({ type: Boolean }) showSettingsPanel = false;
  @property({ type: String }) playbackDurationMode: 'indefinite' | 'timed' = 'indefinite';
  @property({ type: Number }) playbackDurationMinutes = 30;
  @property({ type: Number }) fadeInDurationSec = 2;
  @property({ type: Number }) fadeOutDurationSec = 5;
  @property({ type: String }) sessionDurationDisplay = '00:00';
  @property({ type: Boolean }) isRecording = false;
  @property({ type: String }) recordedAudioUrl: string | null = null;
  @property({ type: Number }) currentBpm = 90;
  @property({ type: Number }) currentDensity = 0.5;
  @property({ type: Number }) currentBrightness = 0.5;
  @property({ type: Number }) currentGuidance = 4.0;
  @property({ type: Number }) currentTemperature = 1.5;
  @property({ type: Boolean }) muteBass = false;
  @property({ type: Boolean }) muteDrums = false;
  @property({ type: Boolean }) onlyBassAndDrums = false;
  @property({ type: String }) currentScale = 'SCALE_UNSPECIFIED';
  @property({ type: Boolean }) useDefaultBpm = true;
  @property({ type: Boolean }) useDefaultDensity = true;
  @property({ type: Boolean }) useDefaultBrightness = true;
  @property({ type: Boolean }) useDefaultGuidance = true;
  @property({ type: Boolean }) useDefaultTemperature = true;
  @property({ type: String }) visualizationMode: VisualizationMode = 'frequency';
  @property({ type: Object }) savedKnobPresets: Map<string, any> = new Map();
  @property({ type: String }) selectedPresetName = '';
  @property({ type: String }) newPresetName = '';
  @property({ type: Object }) toastMessage!: ToastMessage;
  @property({ type: Object }) settingsPersistence!: SettingsPersistence;

  // Music Config Preset State
  @state() private savedMusicConfigPresets: Map<string, MusicConfigPreset> = new Map();
  @state() private selectedMusicConfigPresetName = '';
  @state() private newMusicConfigPresetName = '';

  @property({ type: Number }) gridSize = 4;
  @property({ type: String }) generationStyle: 'stacked' | 'blended' = 'stacked';

  @property({ type: Boolean }) autoVariationEnabled = false;
  @property({ type: Number }) autoVariationRate = 0.5;
  @property({ type: Number }) autoVariationDepth = 0.2;
  @property({ type: Number }) autoVariationMinInterval = 200;
  @property({ type: Number }) autoVariationMaxInterval = 2000;
  @property({ type: Number }) autoVariationMaxChange = 0.25;

  @query('preset-controller') presetController!: PresetController;
  @query('music-config-preset-controller') musicConfigPresetController!: MusicConfigPresetController;

  private emitEvent(eventName: string, detail?: any) {
    this.dispatchEvent(new CustomEvent(eventName, { detail, bubbles: true, composed: true }));
  }

  private handleGenerationStyleChange(e: Event) {
    const input = e.target as HTMLInputElement;
    this.generationStyle = input.value as 'stacked' | 'blended';
    this.emitEvent('generation-style-change', this.generationStyle);
  }

  private handleGridSizeChange(e: Event) {
    const inputElement = e.target as HTMLInputElement;
    const newSize = parseInt(inputElement.value, 10);
    if (!isNaN(newSize) && newSize >= 1) {
      this.gridSize = newSize;
      this.emitEvent('grid-size-change', this.gridSize);
    }
  }

  private handleDurationModeChange(e: Event) {
    const selectElement = e.target as HTMLSelectElement;
    this.playbackDurationMode = selectElement.value as 'indefinite' | 'timed';
    this.emitEvent('duration-mode-change', this.playbackDurationMode);
  }

  private handleDurationMinutesChange(e: Event) {
    const inputElement = e.target as HTMLInputElement;
    this.playbackDurationMinutes = parseInt(inputElement.value, 10) || 30;
    this.emitEvent('duration-minutes-change', this.playbackDurationMinutes);
  }

  private handleNewPresetNameChange(e: Event) {
    const inputElement = e.target as HTMLInputElement;
    this.newPresetName = inputElement.value;
    this.emitEvent('preset-name-change', this.newPresetName);
  }

  private handleSelectedPresetNameChange(e: Event) {
    const selectElement = e.target as HTMLSelectElement;
    this.selectedPresetName = selectElement.value;
    this.emitEvent('preset-selection-change', this.selectedPresetName);
  }

  private saveCurrentKnobsAsPreset() {
    this.emitEvent('save-preset', { name: this.newPresetName.trim() });
  }

  private loadSelectedPreset() {
    this.emitEvent('load-preset', { name: this.selectedPresetName });
  }

  private deleteSelectedPreset() {
    this.emitEvent('delete-preset');
  }

  private exportPresets() {
    this.emitEvent('export-presets');
  }

  private handleFileImport(e: Event) {
    const input = e.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      this.emitEvent('import-presets', file);
      // Reset file input so the same file can be loaded again
      input.value = '';
    }
  }

  private applySettings() {
    this.emitEvent('apply-settings');
  }

  private startRecording() {
    this.emitEvent('start-recording');
  }

  private stopRecording() {
    this.emitEvent('stop-recording');
  }

  private handleReconnectSession() {
    this.emitEvent('reconnect-session');
  }

  private testAudio() {
    this.emitEvent('test-audio');
  }

  private sendMusicConfig() {
    this.emitEvent('music-config-change', {
      bpm: this.currentBpm,
      density: this.currentDensity,
      brightness: this.currentBrightness,
      guidance: this.currentGuidance,
      temperature: this.currentTemperature,
      muteBass: this.muteBass,
      muteDrums: this.muteDrums,
      onlyBassAndDrums: this.onlyBassAndDrums,
      scale: this.currentScale,
      useDefaultBpm: this.useDefaultBpm,
      useDefaultDensity: this.useDefaultDensity,
      useDefaultBrightness: this.useDefaultBrightness,
      useDefaultGuidance: this.useDefaultGuidance,
      useDefaultTemperature: this.useDefaultTemperature
    });
  }

  private saveCurrentMusicConfigPreset() {
    const currentConfig: MusicConfigPreset = {
      bpm: this.currentBpm,
      useDefaultBpm: this.useDefaultBpm,
      density: this.currentDensity,
      useDefaultDensity: this.useDefaultDensity,
      brightness: this.currentBrightness,
      useDefaultBrightness: this.useDefaultBrightness,
      guidance: this.currentGuidance,
      useDefaultGuidance: this.useDefaultGuidance,
      temperature: this.currentTemperature,
      useDefaultTemperature: this.useDefaultTemperature,
      muteBass: this.muteBass,
      muteDrums: this.muteDrums,
      onlyBassAndDrums: this.onlyBassAndDrums,
      currentScale: this.currentScale
    };
    this.musicConfigPresetController.saveCurrentConfigAsPreset(currentConfig);
  }

  private loadMusicConfigPreset(preset: MusicConfigPreset) {
    this.currentBpm = preset.bpm;
    this.useDefaultBpm = preset.useDefaultBpm;
    this.currentDensity = preset.density;
    this.useDefaultDensity = preset.useDefaultDensity;
    this.currentBrightness = preset.brightness;
    this.useDefaultBrightness = preset.useDefaultBrightness;
    this.currentGuidance = preset.guidance;
    this.useDefaultGuidance = preset.useDefaultGuidance;
    this.currentTemperature = preset.temperature;
    this.useDefaultTemperature = preset.useDefaultTemperature;

    // Handle new boolean flags if they exist in preset, default to false if not
    this.muteBass = preset.muteBass ?? false;
    this.muteDrums = preset.muteDrums ?? false;
    this.onlyBassAndDrums = preset.onlyBassAndDrums ?? false;

    this.currentScale = preset.currentScale ?? 'SCALE_UNSPECIFIED';

    this.sendMusicConfig(); // Apply changes immediately
  }

  override render() {
    if (!this.showSettingsPanel) return html``;

    const presetNames = Array.from(this.savedKnobPresets.keys());
    const trimmedNewPresetName = this.newPresetName.trim();
    const isUpdatingExistingPreset = this.savedKnobPresets.has(trimmedNewPresetName) && trimmedNewPresetName !== '';
    const saveButtonText = isUpdatingExistingPreset ? `Update '${trimmedNewPresetName}'` : 'Save as New Preset';

    return html`
      <div class="settings-panel">
        <div class="settings-section">
          <h3>Playback Duration</h3>
          <div>
            <label>
              <input 
                type="radio" 
                name="durationMode" 
                value="indefinite" 
                .checked=${this.playbackDurationMode === 'indefinite'}
                @change=${this.handleDurationModeChange}>
              Indefinite
            </label>
          </div>
          <div>
            <label>
              <input 
                type="radio" 
                name="durationMode" 
                value="timed" 
                .checked=${this.playbackDurationMode === 'timed'}
                @change=${this.handleDurationModeChange}>
              Timed (minutes):
            </label>
            <input 
              type="number" 
              .value=${this.playbackDurationMinutes.toString()} 
              @input=${this.handleDurationMinutesChange} 
              ?disabled=${this.playbackDurationMode !== 'timed'}
              min="1">
          </div>
        </div>

        <div class="settings-section">
          <h3>Audio Fades (seconds)</h3>
          <div>
            <label>Fade In:</label>
            <input 
              type="number" 
              .value=${this.fadeInDurationSec.toString()} 
              step="0.1"
              @input=${(e: Event) => {
        this.fadeInDurationSec = parseFloat((e.target as HTMLInputElement).value) || 0;
        this.emitEvent('fade-in-change', this.fadeInDurationSec);
      }}
              min="0">
          </div>
          <div>
            <label>Fade Out:</label>
            <input 
              type="number" 
              .value=${this.fadeOutDurationSec.toString()} 
              step="0.1"
              @input=${(e: Event) => {
        this.fadeOutDurationSec = parseFloat((e.target as HTMLInputElement).value) || 0;
        this.emitEvent('fade-out-change', this.fadeOutDurationSec);
      }}
              min="0">
          </div>
        </div>

        <div class="settings-section">
          <h3>Session Info</h3>
          <p>Current Duration: ${this.sessionDurationDisplay}</p>
          <button @click=${this.handleReconnectSession}>Reconnect Session</button>
          <button @click=${this.testAudio} class="test-button">🔊 Test Audio Chain</button>
        </div>

        <div class="settings-section">
          <h3>Audio Recording</h3>
          ${this.isRecording
        ? html`<button @click=${this.stopRecording}>Stop Recording</button>`
        : html`<button @click=${this.startRecording}>Start Recording</button>`
      }
          ${this.recordedAudioUrl
        ? html`<a href=${this.recordedAudioUrl} download="recorded-music.wav"><button>Download Recording</button></a>`
        : ''
      }
        </div>

        <div class="settings-section">
          <h3>Music Generation Parameters</h3>

           <!-- Music Config Presets UI -->
          <div class="preset-controls">
            <h4>⚙️ Parameter Presets</h4>
            <div class="preset-row">
              <select 
                .value=${this.selectedMusicConfigPresetName}
                @change=${(e: Event) => this.musicConfigPresetController.handleSelectedPresetNameChange((e.target as HTMLSelectElement).value)}
              >
                <option value="" disabled ?selected=${!this.selectedMusicConfigPresetName}>Select a Preset...</option>
                ${Array.from(this.savedMusicConfigPresets.keys()).map(name => html`
                  <option value=${name} ?selected=${name === this.selectedMusicConfigPresetName}>${name}</option>
                `)}
              </select>
              <button 
                @click=${() => this.musicConfigPresetController.deleteSelectedPreset()}
                ?disabled=${!this.selectedMusicConfigPresetName}
                title="Delete Selected Preset"
              >🗑️</button>
            </div>
            
            <div class="preset-row">
              <input 
                type="text" 
                placeholder="New preset name..." 
                .value=${this.newMusicConfigPresetName}
                @input=${(e: Event) => this.musicConfigPresetController.handleNewPresetNameChange((e.target as HTMLInputElement).value)}
              >
              <button 
                @click=${this.saveCurrentMusicConfigPreset}
                ?disabled=${!this.newMusicConfigPresetName}
                title="Save Current Parameters"
              >💾 Save</button>
            </div>

            <div class="preset-actions">
               <button @click=${() => this.musicConfigPresetController.exportPresets()}>📤 Export</button>
               <label class="import-btn">
                 📥 Import
                 <input type="file" accept=".json" @change=${(e: Event) => {
        const file = (e.target as HTMLInputElement).files?.[0];
        if (file) this.musicConfigPresetController.importPresets(file);
        (e.target as HTMLInputElement).value = ''; // Reset
      }}>
               </label>
            </div>
            <hr style="border-color: #444; margin: 15px 0;">
          </div>

          <!-- Auto Variation -->
          <div class="settings-section">
            <h4>🌊 Automatic Variation</h4>
            <div style="margin-bottom: 10px;">
              <label>
                <input 
                  type="checkbox" 
                  .checked=${this.autoVariationEnabled} 
                  @change=${(e: Event) => {
        this.autoVariationEnabled = (e.target as HTMLInputElement).checked;
        this.emitEvent('auto-variation-toggle', this.autoVariationEnabled);
      }}>
                Enable Smart Variation
              </label>
            </div>
            
            <div class="slider-row" style=${this.autoVariationEnabled ? '' : 'opacity: 0.5; pointer-events: none;'}>
              <label>Rate (Speed): <span style="font-weight: normal; opacity: 0.8; font-family: monospace;">${(this.autoVariationMaxInterval - (this.autoVariationRate * (this.autoVariationMaxInterval - this.autoVariationMinInterval))).toFixed(0)}ms</span></label>
              <input 
                type="range" 
                min="0" max="1" step="0.05"
                .value=${this.autoVariationRate.toString()}
                @input=${(e: Event) => {
        this.autoVariationRate = parseFloat((e.target as HTMLInputElement).value);
        this.emitEvent('auto-variation-rate-change', this.autoVariationRate);
        this.requestUpdate();
      }}>
            </div>

            <div class="slider-row" style=${this.autoVariationEnabled ? '' : 'opacity: 0.5; pointer-events: none;'}>
              <label>Depth (Intensity): <span style="font-weight: normal; opacity: 0.8; font-family: monospace;">+/-${(this.autoVariationDepth * this.autoVariationMaxChange * 100).toFixed(1)}%</span></label>
              <input 
                type="range" 
                min="0" max="1" step="0.05"
                .value=${this.autoVariationDepth.toString()}
                @input=${(e: Event) => {
        this.autoVariationDepth = parseFloat((e.target as HTMLInputElement).value);
        this.emitEvent('auto-variation-depth-change', this.autoVariationDepth);
        this.requestUpdate();
      }}>
            </div>

             <div style="font-size: 0.85em; opacity: 0.8; margin-top: 5px; margin-bottom: 5px; border-top: 1px solid #444; padding-top: 5px;">
               <strong>Advanced Limits</strong>
             </div>
             
             <div class="slider-row" style="font-size: 0.9em; ${this.autoVariationEnabled ? '' : 'opacity: 0.5; pointer-events: none;'}">
                <label>Min Interval: <span style="font-weight: normal; opacity: 0.8; font-family: monospace;">${this.autoVariationMinInterval}ms</span></label>
                <input 
                  type="range" 
                  min="50" max="5000" step="50"
                  .value=${this.autoVariationMinInterval.toString()}
                  @input=${(e: Event) => {
        this.autoVariationMinInterval = parseFloat((e.target as HTMLInputElement).value);
        this.emitEvent('auto-variation-min-interval-change', this.autoVariationMinInterval);
        this.requestUpdate();
      }}>
             </div>

             <div class="slider-row" style="font-size: 0.9em; ${this.autoVariationEnabled ? '' : 'opacity: 0.5; pointer-events: none;'}">
                <label>Max Interval: <span style="font-weight: normal; opacity: 0.8; font-family: monospace;">${this.autoVariationMaxInterval}ms</span></label>
                <input 
                  type="range" 
                  min="500" max="10000" step="100"
                  .value=${this.autoVariationMaxInterval.toString()}
                  @input=${(e: Event) => {
        this.autoVariationMaxInterval = parseFloat((e.target as HTMLInputElement).value);
        this.emitEvent('auto-variation-max-interval-change', this.autoVariationMaxInterval);
        this.requestUpdate();
      }}>
             </div>

             <div class="slider-row" style="font-size: 0.9em; ${this.autoVariationEnabled ? '' : 'opacity: 0.5; pointer-events: none;'}">
                <label>Max Change Limit: <span style="font-weight: normal; opacity: 0.8; font-family: monospace;">${(this.autoVariationMaxChange * 100).toFixed(0)}%</span></label>
                <input 
                  type="range" 
                  min="0.01" max="1.0" step="0.01"
                  .value=${this.autoVariationMaxChange.toString()}
                  @input=${(e: Event) => {
        this.autoVariationMaxChange = parseFloat((e.target as HTMLInputElement).value);
        this.emitEvent('auto-variation-max-change-change', this.autoVariationMaxChange);
        this.requestUpdate();
      }}>
             </div>

            <div style="font-size: 0.85em; opacity: 0.8; margin-bottom: 15px;">
              Subtly changes active prompt strengths over time.
            </div>
          </div>

          <!-- Generation Style -->
          <div class="settings-section">
            <h4>Generation Style</h4>
            <div style="display: flex; gap: 15px; margin-bottom: 10px;">
              <label>
                <input 
                  type="radio" 
                  name="generationStyle" 
                  value="stacked" 
                  .checked=${this.generationStyle === 'stacked'}
                  @change=${this.handleGenerationStyleChange}>
                Stacked (Custom)
              </label>
              <label>
                <input 
                  type="radio" 
                  name="generationStyle" 
                  value="blended" 
                  .checked=${this.generationStyle === 'blended'}
                  @change=${this.handleGenerationStyleChange}>
                Blended (Official)
              </label>
            </div>
            <div style="font-size: 0.85em; opacity: 0.8; margin-bottom: 15px;">
              ${this.generationStyle === 'stacked'
        ? 'Raw weights. Intense, layered sound. Weights are added together.'
        : 'Normalized weights. Cohesive, mixed sound. Weights sum to 100%.'}
            </div>
          </div>
          
          <!-- BPM Slider -->
          <div class="slider-row">
            <label>🥁 BPM:</label>
            <input
              type="range"
              .value=${this.currentBpm.toString()}
              @input=${(e: Event) => {
        this.currentBpm = parseInt((e.target as HTMLInputElement).value, 10) || 60;
        this.sendMusicConfig();
      }}
              min="60" max="200" step="1"
              ?disabled=${this.useDefaultBpm}>
            <span class="slider-value">${this.currentBpm}</span>
          </div>
          <div class="model-decides-row">
            <input type="checkbox" .checked=${this.useDefaultBpm}
              @change=${(e: Event) => { this.useDefaultBpm = (e.target as HTMLInputElement).checked; this.sendMusicConfig(); }}>
            <span>Model Decides</span>
          </div>

          <!-- Density Slider -->
          <div class="slider-row">
            <label>🎵 Density:</label>
            <input
              type="range"
              .value=${this.currentDensity.toString()}
              @input=${(e: Event) => {
        this.currentDensity = parseFloat((e.target as HTMLInputElement).value) || 0;
        this.sendMusicConfig();
      }}
              min="0" max="1" step="0.05"
              ?disabled=${this.useDefaultDensity}>
            <span class="slider-value">${this.currentDensity.toFixed(2)}</span>
          </div>
          <div class="model-decides-row">
            <input type="checkbox" .checked=${this.useDefaultDensity}
              @change=${(e: Event) => { this.useDefaultDensity = (e.target as HTMLInputElement).checked; this.sendMusicConfig(); }}>
            <span>Model Decides</span>
          </div>

          <!-- Brightness Slider -->
          <div class="slider-row">
            <label>☀️ Brightness:</label>
            <input
              type="range"
              .value=${this.currentBrightness.toString()}
              @input=${(e: Event) => {
        this.currentBrightness = parseFloat((e.target as HTMLInputElement).value) || 0;
        this.sendMusicConfig();
      }}
              min="0" max="1" step="0.05"
              ?disabled=${this.useDefaultBrightness}>
            <span class="slider-value">${this.currentBrightness.toFixed(2)}</span>
          </div>
          <div class="model-decides-row">
            <input type="checkbox" .checked=${this.useDefaultBrightness}
              @change=${(e: Event) => { this.useDefaultBrightness = (e.target as HTMLInputElement).checked; this.sendMusicConfig(); }}>
            <span>Model Decides</span>
          </div>

          <!-- Guidance Slider -->
          <div class="slider-row">
            <label>🎯 Guidance:</label>
            <input
              type="range"
              .value=${this.currentGuidance.toString()}
              @input=${(e: Event) => {
        this.currentGuidance = parseFloat((e.target as HTMLInputElement).value) || 0;
        this.sendMusicConfig();
      }}
              min="0" max="6" step="0.1"
              ?disabled=${this.useDefaultGuidance}>
            <span class="slider-value">${this.currentGuidance.toFixed(1)}</span>
          </div>
          <div class="model-decides-row">
            <input type="checkbox" .checked=${this.useDefaultGuidance}
              @change=${(e: Event) => { this.useDefaultGuidance = (e.target as HTMLInputElement).checked; this.sendMusicConfig(); }}>
            <span>Model Decides</span>
          </div>

          <!-- Chaos/Variation Slider -->
          <div class="slider-row">
            <label>🎲 Chaos/Variation:</label>
            <input
              type="range"
              .value=${this.currentTemperature.toString()}
              @input=${(e: Event) => {
        this.currentTemperature = parseFloat((e.target as HTMLInputElement).value) || 0;
        this.sendMusicConfig();
      }}
              min="0" max="3" step="0.1"
              ?disabled=${this.useDefaultTemperature}>
            <span class="slider-value">${this.currentTemperature.toFixed(1)}</span>
          </div>
          <div class="model-decides-row">
            <input type="checkbox" .checked=${this.useDefaultTemperature}
              @change=${(e: Event) => { this.useDefaultTemperature = (e.target as HTMLInputElement).checked; this.sendMusicConfig(); }}>
            <span>Model Decides</span>
          </div>
          <div>
            <label>
              <input
                type="checkbox"
                .checked=${this.muteBass}
                @change=${(e: Event) => {
        this.muteBass = (e.target as HTMLInputElement).checked;
        this.sendMusicConfig();
      }}>
              🎸 Mute Bass
            </label>
          </div>
          <div>
            <label>
              <input
                type="checkbox"
                .checked=${this.muteDrums}
                @change=${(e: Event) => {
        this.muteDrums = (e.target as HTMLInputElement).checked;
        this.sendMusicConfig();
      }}>
              🥁 Mute Drums
            </label>
          </div>
          <div>
            <label>
              <input
                type="checkbox"
                .checked=${this.onlyBassAndDrums}
                @change=${(e: Event) => {
        this.onlyBassAndDrums = (e.target as HTMLInputElement).checked;
        this.sendMusicConfig();
      }}>
              🎹 Only Bass & Drums
            </label>
          </div>
          <div>
            <label>Musical Key/Scale:</label>
            <select .value=${this.currentScale} @change=${(e: Event) => {
        this.currentScale = (e.target as HTMLSelectElement).value;
        this.sendMusicConfig();
      }}>
              <option value="SCALE_UNSPECIFIED">Default (Model Decides)</option>
              <option value="C_MAJOR_A_MINOR">C major / A minor</option>
              <option value="D_FLAT_MAJOR_B_FLAT_MINOR">D♭ major / B♭ minor</option>
              <option value="D_MAJOR_B_MINOR">D major / B minor</option>
              <option value="E_FLAT_MAJOR_C_MINOR">E♭ major / C minor</option>
              <option value="E_MAJOR_D_FLAT_MINOR">E major / C♯/D♭ minor</option>
              <option value="F_MAJOR_D_MINOR">F major / D minor</option>
              <option value="G_FLAT_MAJOR_E_FLAT_MINOR">G♭ major / E♭ minor</option>
              <option value="G_MAJOR_E_MINOR">G major / E minor</option>
              <option value="A_FLAT_MAJOR_F_MINOR">A♭ major / F minor</option>
              <option value="A_MAJOR_G_FLAT_MINOR">A major / F♯/G♭ minor</option>
              <option value="B_FLAT_MAJOR_G_MINOR">B♭ major / G minor</option>
              <option value="B_MAJOR_A_FLAT_MINOR">B major / G♯/A♭ minor</option>
            </select>
          </div>
        </div>

        <div class="settings-section">
          <h3>Visualization</h3>
          <div>
            <label>Mode:</label>
            <select .value=${this.visualizationMode} @change=${(e: Event) => {
        this.visualizationMode = (e.target as HTMLSelectElement).value as VisualizationMode;
        this.emitEvent('visualization-mode-change', this.visualizationMode);
      }}>
              <option value="frequency">Frequency Bars</option>
              <option value="waveform">Waveform</option>
              <option value="circle">Expanding Circle</option>
              <option value="spectrogram">Spectrogram</option>
              <option value="frequency-peaks">Frequency Peaks</option>
              <option value="audio-track">Audio Track</option>
            </select>
          </div>
        </div>

        <div class="settings-section">
          <h3>Grid Settings</h3>
          <div>
             <label>Grid Size (N x N):</label>
             <input type="number" 
                    .value=${this.gridSize.toString()} 
                    @input=${this.handleGridSizeChange}
                    min="1" max="10">
          </div>
        </div>

        <div class="settings-section">
          <h3>Knob Presets</h3>
          <div class="preset-row">
            <input 
              type="text" 
              placeholder="New preset name" 
              .value=${this.newPresetName} 
              @input=${this.handleNewPresetNameChange}
            >
            <button 
                @click=${this.saveCurrentKnobsAsPreset} 
                ?disabled=${!trimmedNewPresetName}
            >
                ${saveButtonText}
            </button>
          </div>
          <div class="preset-row">
            <select 
              .value=${this.selectedPresetName} 
              @change=${this.handleSelectedPresetNameChange}
              ?disabled=${presetNames.length === 0}
            >
              <option value="" ?hidden=${presetNames.length > 0}>No presets available</option>
              ${presetNames.map(name => html`<option value=${name}>${name}</option>`)}
            </select>
            <button @click=${this.loadSelectedPreset} ?disabled=${!this.selectedPresetName}>Load</button>
            <button @click=${this.deleteSelectedPreset} ?disabled=${!this.selectedPresetName}>Delete</button>
          </div>
          <div class="preset-row">
            <button @click=${this.exportPresets} ?disabled=${presetNames.length === 0}>Export All</button>
            <label for="import-presets-input" class="button-like-label">
              Import
              <input id="import-presets-input" type="file" @change=${this.handleFileImport} accept=".json" style="display: none;"/>
            </label>
          </div>
        </div>
        
        <hr>
        <button @click=${this.applySettings}>Apply Settings & Close</button>
        <button @click=${() => this.emitEvent('close-settings')}>Cancel & Close</button>
      <music-config-preset-controller
        .settingsPersistence=${this.settingsPersistence}
        @music-config-preset-state-updated=${(e: CustomEvent) => {
        this.savedMusicConfigPresets = e.detail.savedMusicConfigPresets;
        this.selectedMusicConfigPresetName = e.detail.selectedMusicConfigPresetName;
        this.newMusicConfigPresetName = e.detail.newPresetName;
      }}
        @music-config-preset-loaded=${(e: CustomEvent) => this.loadMusicConfigPreset(e.detail)}
      ></music-config-preset-controller>
      </div>
    `;
  }
} 