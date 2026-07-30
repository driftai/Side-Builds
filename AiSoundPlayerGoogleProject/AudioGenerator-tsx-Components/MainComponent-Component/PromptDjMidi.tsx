// Full class content

import { css, html, LitElement } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';

import { type LiveMusicSession } from '@google/genai';
import type { ToastMessage } from '../UI-Components/ToastMessage-Component/ToastMessage.js';
import type { Prompt, PlaybackState, VisualizationMode } from '../Audio-Processing-Controllers/Utilities-&-Initialization/TypeDefinitions-Component/TypeDefinitions.js';


import { MidiDispatcher } from '../MIDI-&-Control/MidiDispatcher-Component/MidiDispatcher.js';
import { AudioAnalyser } from '../Audio-&-Visualization/AudioAnalyser-Component/AudioAnalyser.js';
import { SettingsPanel } from '../UI-Components/SettingsPanel-Component/SettingsPanel.js';
import type { SettingsCoordinator } from '../Audio-Processing-Controllers/Utilities-&-Initialization/SettingsCoordinator-Component/SettingsCoordinator.js';
import { StatusMessage } from '../UI-Components/StatusMessage-Component/StatusMessage.js';
import { WaveformVisualizer } from '../Audio-&-Visualization/WaveformVisualizer-Component/WaveformVisualizer.js';
import { RecordingController } from '../Audio-&-Visualization/RecordingController-Component/RecordingController.js';
import { SessionTimer } from '../Data-Management/SessionTimer-Component/SessionTimer.js';
import { BackgroundGenerator } from '../Visual-Effects/BackgroundGenerator-Component/BackgroundGenerator.js';
import { MusicConfigController } from '../Audio-Processing-Controllers/MusicConfigController-Component/MusicConfigController.js';

import { AudioContextManager } from '../Audio-&-Visualization/AudioContextManager-Component/AudioContextManager.js';
import { FadeController } from '../Audio-Processing-Controllers/FadeController-Component/FadeController.js';
import { ConnectionController } from '../Audio-Processing-Controllers/ConnectionController-Component/ConnectionController.js';
import { PromptManager } from '../Data-Management/PromptManager-Component/PromptManager.js';
import { PlaybackDurationController } from '../Audio-Processing-Controllers/PlaybackDurationController-Component/PlaybackDurationController.js';
import { SettingsPersistence } from '../Data-Management/SettingsPersistence-Component/SettingsPersistence.js';
import { AudioLevelMonitor } from '../Audio-&-Visualization/AudioLevelMonitor-Component/AudioLevelMonitor.js';
import { AudioBufferHandler } from '../Audio-&-Visualization/AudioBufferHandler-Component/AudioBufferHandler.js';
import { MasterVolumeController } from '../Data-Management/MasterVolumeController-Component/MasterVolumeController.js';
import { GoogleAIConfig } from '../Audio-Processing-Controllers/Utilities-&-Initialization/GoogleAIConfig-Component/GoogleAIConfig.js';
import { PlaybackController } from '../Audio-Processing-Controllers/PlaybackController-Component/PlaybackController.js';
import { MidiUIController } from '../MIDI-&-Control/MidiUIController-Component/MidiUIController.js';
import { FrequencyHistoryManager } from '../Audio-&-Visualization/FrequencyHistoryManager-Component/FrequencyHistoryManager.js';

import { UIStateController } from '../Audio-Processing-Controllers/Utilities-&-Initialization/UIStateController-Component/UIStateController.js';
import { PresetController } from '../Data-Management/PresetController-Component/PresetController.js';
import { EventHandlerController } from '../Audio-Processing-Controllers/Utilities-&-Initialization/EventHandlerController-Component/EventHandlerController.js';
import { FilteredPromptsController } from '../Audio-Processing-Controllers/Utilities-&-Initialization/FilteredPromptsController-Component/FilteredPromptsController.js';
import { OutputNodeController } from '../Audio-Processing-Controllers/Utilities-&-Initialization/OutputNodeController-Component/OutputNodeController.js';
import { SessionController } from '../Audio-Processing-Controllers/SessionController-Component/SessionController.js';

import { PlayPauseHandler } from '../Audio-Processing-Controllers/PlayPauseHandler-Component/PlayPauseHandler.js';
import { PeakInteractionController } from '../Audio-&-Visualization/PeakInteractionController-Component/PeakInteractionController.js';
import { FadeSettingsHandler } from '../Audio-Processing-Controllers/FadeSettingsHandler-Component/FadeSettingsHandler.js';
import '../Audio-Processing-Controllers/Utilities-&-Initialization/AppViewportManager-Component/AppViewportManager.js';
import '../UI-Components/ControlButtonsPanel-Component/ControlButtonsPanel.js';
import '../UI-Components/PromptGrid-Component/PromptGrid.js';
import '../UI-Components/MainContainer-Component/MainContainer.js';

@customElement('prompt-dj-midi')
export class PromptDjMidi extends LitElement {
  static override styles = css`
    play-pause-button {
      margin-top: 2vmin;
      width: 15vmin;
      height: 15vmin;
      display: flex;
      justify-content: center;
      align-items: center;
      flex-shrink: 0;
    }
  `;

  @state() private prompts: Map<string, Prompt>;
  private midiDispatcher: MidiDispatcher;
  private audioAnalyser: AudioAnalyser;
  private sessionTimer: SessionTimer;
  private backgroundGenerator: BackgroundGenerator;
  private musicConfigController: MusicConfigController;

  private audioContextManager: AudioContextManager;
  private fadeController: FadeController;
  private connectionController: ConnectionController;
  private promptManager: PromptManager;
  private playbackDurationController: PlaybackDurationController;
  private settingsPersistence: SettingsPersistence;
  private audioBufferHandler: AudioBufferHandler;
  private masterVolumeController: MasterVolumeController;
  private googleAIConfig: GoogleAIConfig;
  private playbackController: PlaybackController;
  private midiUIController: MidiUIController;
  private frequencyHistoryManager: FrequencyHistoryManager;




  @state() private playbackState: PlaybackState = 'stopped';

  private session: LiveMusicSession | null = null;
  private audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
    sampleRate: 48000,
    latencyHint: 'playback' // Increase internal buffer to reduce dropouts on Windows
  });
  private outputNode: GainNode;

  @property({ type: Boolean }) private showMidi = false;
  @state() private audioLevel = 0;
  @state() private midiInputIds: string[] = [];
  @state() private activeMidiInputId: string | null = null;

  @state() private showSettingsPanel = false;
  @state() private masterVolume = 1;

  @state() private savedKnobPresets: Map<string, Map<string, Prompt>> = new Map();
  @state() private selectedPresetName = '';
  @state() private newPresetName = '';


  @query('toast-message') private toastMessage!: ToastMessage;
  @query('settings-panel') private settingsPanel!: SettingsPanel;
  @query('status-message') private statusMessageComponent!: StatusMessage;
  @query('waveform-visualizer') private waveformVisualizer!: WaveformVisualizer;
  @query('recording-controller') private recordingController!: RecordingController;
  @query('audio-level-monitor') private audioLevelMonitor!: AudioLevelMonitor;
  @query('ui-state-controller') private uiStateController!: UIStateController;
  @query('preset-controller') private presetControllerElement!: PresetController;
  @query('settings-persistence') private settingsPersistenceElement!: SettingsPersistence;
  @query('event-handler-controller') private eventHandlerControllerElement!: EventHandlerController;
  @query('filtered-prompts-controller') private filteredPromptsControllerElement!: FilteredPromptsController;
  @query('output-node-controller') private outputNodeControllerElement!: OutputNodeController;
  @query('session-controller') private sessionControllerElement!: SessionController;
  @query('settings-coordinator') private settingsCoordinatorElement!: SettingsCoordinator;

  @query('play-pause-handler') private playPauseHandlerElement!: PlayPauseHandler;
  @query('peak-interaction-controller') private peakInteractionController!: PeakInteractionController;
  @query('fade-settings-handler') private fadeSettingsHandlerElement!: FadeSettingsHandler;

  @state() private visualizationMode: VisualizationMode = 'frequency';
  @state() private gridSize = 4;
  @state() private generationStyle: 'stacked' | 'blended' = 'stacked';

  @state() private autoVariationMinInterval = 200;
  @state() private autoVariationMaxInterval = 2000;
  @state() private autoVariationMaxChange = 0.25;
  @state() private autoVariationEnabled = false;
  @state() private autoVariationRate = 0.5;
  @state() private autoVariationDepth = 0.2;

  private audioBufferHistory: AudioBuffer[] = [];

  private lastPlaybackTime: number = 0;

  private sessionTimerUpdateListener = () => {
    this.requestUpdate();
  };

  private setGridSize(newSize: number) {
    if (newSize < 1) return;
    this.gridSize = newSize;

    this.promptManager.resizePrompts(newSize * newSize);

    // Sync local state and dependencies
    this.prompts = this.promptManager.prompts;
    this.settingsPersistenceElement.prompts = this.prompts;
    if (this.presetControllerElement) {
      this.presetControllerElement.prompts = this.prompts;
    }

    this.toastMessage?.show(`Grid size changed to ${newSize}x${newSize}`);
  }

  private handleToggleGridSize() {
    let newSize = this.gridSize + 1;
    if (newSize > 5) newSize = 3;
    this.setGridSize(newSize);
  }

  constructor(
    prompts: Map<string, Prompt>,
    midiDispatcher: MidiDispatcher,
  ) {
    super();
    this.prompts = prompts;
    this.midiDispatcher = midiDispatcher;
    this.audioAnalyser = new AudioAnalyser(this.audioContext);
    this.sessionTimer = new SessionTimer();
    this.backgroundGenerator = new BackgroundGenerator();
    this.musicConfigController = new MusicConfigController();

    this.audioContextManager = new AudioContextManager();
    this.fadeController = new FadeController();
    this.connectionController = new ConnectionController();
    this.promptManager = new PromptManager();
    this.playbackDurationController = new PlaybackDurationController();
    this.settingsPersistence = new SettingsPersistence();
    this.audioBufferHandler = new AudioBufferHandler();
    this.masterVolumeController = new MasterVolumeController();
    this.googleAIConfig = new GoogleAIConfig();
    this.playbackController = new PlaybackController();
    this.midiUIController = new MidiUIController();
    this.frequencyHistoryManager = new FrequencyHistoryManager();



    this.audioAnalyser.node.connect(this.audioContext.destination);
    this.outputNode = this.audioContext.createGain();
    this.outputNode.connect(this.audioAnalyser.node);

    // Set up AudioBufferHandler dependencies
    this.audioBufferHandler.audioContext = this.audioContext;
    this.audioBufferHandler.outputNode = this.outputNode;
    this.audioBufferHandler.playbackState = this.playbackState;

    // MasterVolumeController dependencies now set up by DependencyInitializer

    // Set up PlaybackController dependencies
    this.playbackController.audioContext = this.audioContext;
    this.playbackController.outputNode = this.outputNode;
    this.playbackController.audioAnalyser = this.audioAnalyser;
    this.playbackController.audioContextManager = this.audioContextManager;
    this.playbackController.fadeController = this.fadeController;
    this.playbackController.audioBufferHandler = this.audioBufferHandler;
    this.playbackController.playbackDurationController = this.playbackDurationController;
    this.playbackController.sessionTimer = this.sessionTimer;
    this.playbackController.masterVolume = this.masterVolume;

    // Set up MidiUIController dependencies
    this.midiUIController.midiDispatcher = this.midiDispatcher;
    this.midiUIController.showMidi = this.showMidi;
    this.midiUIController.midiInputIds = this.midiInputIds;
    this.midiUIController.activeMidiInputId = this.activeMidiInputId;
    // filteredPrompts will be set up after component initialization

    // Load master volume using MasterVolumeController



    // Set up AudioContextManager with the audio context
    this.audioContextManager.audioContext = this.audioContext;
    this.audioContextManager.playbackState = this.playbackState;

    // Set up FadeController with audio context and output node
    this.fadeController.audioContext = this.audioContext;
    this.fadeController.outputNode = this.outputNode;


    // Note: ConnectionController and PeakInteractionController dependencies will be set in firstUpdated()
    // after @query elements are available
  }



  override connectedCallback() {
    super.connectedCallback();
    // Viewport initialization now handled by AppViewportManager component

    // Listen for session timer updates to keep settings panel current
    this.sessionTimer.addEventListener('session-duration-updated', this.sessionTimerUpdateListener);

    // Master volume event listener now handled by DependencyInitializer
  }

  override async firstUpdated() {
    // Initialization now handled by DependencyInitializer component
    this.uiStateController.toastMessage = this.toastMessage;
    this.uiStateController.addEventListener('ui-state-change', (e: Event) => {
      const { showSettingsPanel, visualizationMode } = (e as CustomEvent).detail;
      this.showSettingsPanel = showSettingsPanel;
      this.visualizationMode = visualizationMode;
    });

    // Setup and initialize the PresetController with the correct SettingsPersistence instance
    this.presetControllerElement.settingsPersistence = this.settingsPersistenceElement;
    // CRITICAL FIX: Set prompts before initializing to ensure presets load properly
    this.presetControllerElement.prompts = this.prompts;
    this.presetControllerElement.initialize();

    // Initialize SettingsPanel with persistence
    if (this.settingsPanel) {
      this.settingsPanel.settingsPersistence = this.settingsPersistenceElement;
    }

    // Listen for events from the PresetController
    this.addEventListener('preset-data-updated', (e: Event) => {
      const { savedKnobPresets, selectedPresetName, newPresetName } = (e as CustomEvent).detail;
      this.savedKnobPresets = savedKnobPresets;
      this.selectedPresetName = selectedPresetName;
      this.newPresetName = newPresetName;
    });
    this.addEventListener('prompts-updated', (e: Event) => {
      const customEvent = e as CustomEvent<Map<string, Prompt>>;
      const newPrompts = customEvent.detail;

      // Update local state directly
      this.prompts = newPrompts;

      // Update dependencies that need to know about the change
      this.settingsPersistenceElement.prompts = this.prompts;
      if (this.presetControllerElement) {
        this.presetControllerElement.prompts = this.prompts;
      }

      // CRITICAL: Do NOT call this.setPrompts(newPrompts) or this.promptManager.setPrompts(newPrompts)
      // because this event originates FROM PromptManager. Calling setPrompts would create an infinite loop.
    });

    // Handle preset loading separately
    this.addEventListener('preset-prompts-loaded', (e: Event) => {
      const customEvent = e as CustomEvent<Map<string, Prompt>>;
      this.setPrompts(customEvent.detail);
    });

    // Listen for filtered prompts changes to update UI
    this.addEventListener('filtered-prompts-changed', () => {
      this.requestUpdate(); // Trigger re-render when filtered prompts change
    });

    // Set dependencies for PeakInteractionController
    this.peakInteractionController.prompts = this.prompts;
    this.peakInteractionController.toastMessage = this.toastMessage;

    // Auto-start playback moved to onSessionCreated callback
  }

  // Session connection now handled by SessionController component

  // Disconnection handling now delegated to SessionController component

  // Session timeout handling now delegated to SessionController component

  private getPromptsToSend() {
    return this.promptManager.getPromptsToSend();
  }

  private setSessionPrompts = () => {
    return this.promptManager.setSessionPrompts();
  };





  private handlePromptChanged(e: CustomEvent<Prompt>) {
    this.promptManager.handlePromptChanged(e);
    // Update local prompts reference after PromptManager handles the change
    this.prompts = this.promptManager.prompts;
  }

  private setPrompts(newPrompts: Map<string, Prompt>) {
    this.promptManager.setPrompts(newPrompts);
    // Update local prompts reference after PromptManager handles the change
    this.prompts = this.promptManager.prompts;
    // Keep SettingsPersistence component in sync with current prompts
    this.settingsPersistenceElement.prompts = this.prompts;
    // Also keep PresetController in sync
    if (this.presetControllerElement) {
      this.presetControllerElement.prompts = this.prompts;
    }
  }



  private async toggleShowMidi() {
    // Delegate to MidiUIController and sync state back
    const state = await this.midiUIController.toggleShowMidi();
    this.showMidi = state.showMidi;
    this.midiInputIds = state.midiInputIds;
    this.activeMidiInputId = state.activeMidiInputId;
    // filteredPrompts are now managed by FilteredPromptsController
  }





  private applySettings() {
    // Delegate to SettingsCoordinator component
    this.settingsCoordinatorElement.applySettings();
  }

  // --- All preset management methods have been moved to PresetController ---


  private handleOutputNodeRecreated(newOutputNode: GainNode) {
    // Delegate to OutputNodeController component
    if (this.outputNodeControllerElement) {
      this.outputNodeControllerElement.handleOutputNodeRecreated(newOutputNode);
    } else {
      console.error('OutputNodeController element not available - this should not happen as component is always rendered');
    }
  }

  override render() {
    return html`<app-viewport-manager .hostElement=${this}></app-viewport-manager>
    <main-container .backgroundGenerator=${this.backgroundGenerator} .prompts=${this.prompts}>
      <status-message></status-message>
      <control-buttons-panel
        .showMidi=${this.showMidi}
        .masterVolume=${this.masterVolume}
        .midiInputIds=${this.midiInputIds}
        .activeMidiInputId=${this.activeMidiInputId}
        .midiDispatcher=${this.midiDispatcher}
        @toggle-show-midi=${() => this.eventHandlerControllerElement?.handleToggleShowMidi()}
        @toggle-settings-panel=${() => this.eventHandlerControllerElement?.handleToggleSettingsPanel()}
        @master-volume-change=${(e: CustomEvent<number>) => this.eventHandlerControllerElement?.handleMasterVolumeChange(e)}
        @midi-input-change=${(e: Event) => this.eventHandlerControllerElement?.handleMidiInputChange(e)}
        @toggle-grid-size=${() => this.handleToggleGridSize()}
        @reset-music-context=${() => {
        if (this.session) {
          console.log('Resetting music context to break out of current beat/mood...');
          this.session.resetContext();
          this.toastMessage?.show('Music context reset - new mood incoming!');
        }
      }}
      ></control-buttons-panel>
      <prompt-grid
        .prompts=${this.prompts}
        .filteredPrompts=${this.filteredPromptsControllerElement?.getFilteredPrompts() || new Set()}
        .midiDispatcher=${this.midiDispatcher}
        .showMidi=${this.showMidi}
        .audioLevel=${this.audioLevel}
        .gridSize=${this.gridSize}
        @prompt-changed=${this.handlePromptChanged}
      ></prompt-grid>
      <play-pause-button 
        .playbackState=${this.playbackState} 
        @click=${() => this.playPauseHandlerElement.handlePlayPause()}
      ></play-pause-button>
      <play-pause-handler
        .session=${this.session}
        .playbackController=${this.playbackController}
        .masterVolume=${this.masterVolume}
        .playbackState=${this.playbackState}
        .audioContext=${this.audioContext}
        .toastMessage=${this.toastMessage}
        .statusMessage=${this.statusMessageComponent}
        .getPromptsToSend=${() => this.getPromptsToSend()}
        .handleDisconnection=${() => this.sessionControllerElement?.handleDisconnection()}
      ></play-pause-handler>
      <waveform-visualizer
        .visualizationMode=${this.visualizationMode}
        .audioLevel=${this.audioLevel}
        .audioAnalyser=${this.audioAnalyser}
        .frequencyHistory=${this.frequencyHistoryManager.getFrequencyHistory()}
        .audioBufferHistory=${this.audioBufferHistory}
        .lastPlaybackTime=${this.lastPlaybackTime}
        .playbackState=${this.playbackState}
        .audioContext=${this.audioContext}
        .prompts=${this.prompts}
        @peak-click=${(e: CustomEvent) => this.peakInteractionController.handlePeakClick(e)}
        style="position: absolute; bottom: 0; left: 0; width: 100%; height: 50px; z-index: 1;">
      </waveform-visualizer>
      <settings-panel
        .settingsPersistence=${this.settingsPersistenceElement || this.settingsPersistence}
        .showSettingsPanel=${this.showSettingsPanel}
        .playbackDurationMode=${this.playbackDurationController.durationSettings.playbackDurationMode}
        .playbackDurationMinutes=${this.playbackDurationController.durationSettings.playbackDurationMinutes}

        .fadeInDurationSec=${this.fadeSettingsHandlerElement?.getFadeInDuration() || 2}
        .fadeOutDurationSec=${this.fadeSettingsHandlerElement?.getFadeOutDuration() || 5}
        .sessionDurationDisplay=${this.sessionTimer.sessionDurationDisplay}
        .isRecording=${this.recordingController?.recordingState.isRecording || false}
        .recordedAudioUrl=${this.recordingController?.recordingState.recordedAudioUrl || null}
        .savedKnobPresets=${this.savedKnobPresets}
        .selectedPresetName=${this.selectedPresetName}
        .newPresetName=${this.newPresetName}
        .visualizationMode=${this.visualizationMode}
        .gridSize=${this.gridSize}
        .generationStyle=${this.generationStyle}
        .autoVariationEnabled=${this.autoVariationEnabled}
        .autoVariationRate=${this.autoVariationRate}
        .autoVariationDepth=${this.autoVariationDepth}
        .autoVariationMinInterval=${this.autoVariationMinInterval}
        .autoVariationMaxInterval=${this.autoVariationMaxInterval}
        .autoVariationMaxChange=${this.autoVariationMaxChange}
        @grid-size-change=${(e: CustomEvent) => this.setGridSize(e.detail)}
        @generation-style-change=${(e: CustomEvent) => { this.generationStyle = e.detail; }}
        @auto-variation-toggle=${(e: CustomEvent) => { this.autoVariationEnabled = e.detail; }}
        @auto-variation-rate-change=${(e: CustomEvent) => { this.autoVariationRate = e.detail; }}
        @auto-variation-depth-change=${(e: CustomEvent) => { this.autoVariationDepth = e.detail; }}
        @auto-variation-min-interval-change=${(e: CustomEvent) => { this.autoVariationMinInterval = e.detail; }}
        @auto-variation-max-interval-change=${(e: CustomEvent) => { this.autoVariationMaxInterval = e.detail; }}
        @auto-variation-max-change-change=${(e: CustomEvent) => { this.autoVariationMaxChange = e.detail; }}
        @duration-mode-change=${(e: CustomEvent) => this.eventHandlerControllerElement?.handleDurationModeChange(e as unknown as Event)}
        @duration-minutes-change=${(e: CustomEvent) => this.eventHandlerControllerElement?.handleDurationMinutesChange(e as unknown as Event)}
        @fade-in-change=${(e: CustomEvent) => this.fadeSettingsHandlerElement?.handleFadeInChange(e)}
        @fade-out-change=${(e: CustomEvent) => this.fadeSettingsHandlerElement?.handleFadeOutChange(e)}
        @save-preset=${() => this.presetControllerElement.saveCurrentKnobsAsPreset()}
        @load-preset=${() => this.presetControllerElement.loadSelectedPreset()}
        @delete-preset=${() => this.presetControllerElement.deleteSelectedPreset()}
        @preset-name-change=${(e: CustomEvent) => this.presetControllerElement.handleNewPresetNameChange(e.detail)}
        @preset-selection-change=${(e: CustomEvent) => this.presetControllerElement.handleSelectedPresetNameChange(e.detail)}
        @export-presets=${() => this.presetControllerElement.exportPresets()}
        @import-presets=${(e: CustomEvent<File>) => this.presetControllerElement.importPresets(e.detail)}
        @start-recording=${() => this.startRecording()}
        @stop-recording=${() => this.stopRecording()}
        @reconnect-session=${() => this.sessionControllerElement?.handleReconnectSession()}
        @test-audio=${() => this.testAudioChain()}
        @apply-settings=${() => this.applySettings()}
        @close-settings=${() => this.uiStateController.toggleSettingsPanel()}
        @visualization-mode-change=${(e: CustomEvent) => this.eventHandlerControllerElement?.handleVisualizationModeChange(e)}
        @music-config-change=${(e: CustomEvent) => {
        const config = e.detail;
        // Forward all config updates to MusicConfigController
        if (!config.useDefaultBpm) this.musicConfigController.updateBpm(config.bpm);
        if (!config.useDefaultDensity) this.musicConfigController.updateDensity(config.density);
        if (!config.useDefaultBrightness) this.musicConfigController.updateBrightness(config.brightness);
        if (!config.useDefaultGuidance) this.musicConfigController.updateGuidance(config.guidance);
        if (!config.useDefaultTemperature) this.musicConfigController.updateTemperature(config.temperature);
        this.musicConfigController.updateMuteBass(config.muteBass);
        this.musicConfigController.updateMuteDrums(config.muteDrums);
        this.musicConfigController.updateMuteOther(config.muteOther);
        this.musicConfigController.updateScale(config.scale);
        // Also update "use default" flags
        this.musicConfigController.updateUseDefaultBpm(config.useDefaultBpm);
        this.musicConfigController.updateUseDefaultDensity(config.useDefaultDensity);
        this.musicConfigController.updateUseDefaultBrightness(config.useDefaultBrightness);
        this.musicConfigController.updateUseDefaultGuidance(config.useDefaultGuidance);
        this.musicConfigController.updateUseDefaultTemperature(config.useDefaultTemperature);
      }}
      ></settings-panel>
      <recording-controller
        .audioContext=${this.audioContext}
        .outputNode=${this.outputNode}
        .toastMessage=${this.toastMessage}
      ></recording-controller>
      <audio-context-manager
        .audioContext=${this.audioContext}
        .playbackState=${this.playbackState}
      ></audio-context-manager>
      <fade-controller
        .audioContext=${this.audioContext}
        .outputNode=${this.outputNode}
        .fadeInDurationSec=${this.fadeSettingsHandlerElement?.getFadeInDuration() || 2}
        .fadeOutDurationSec=${this.fadeSettingsHandlerElement?.getFadeOutDuration() || 5}
        .masterVolume=${this.masterVolume}
      ></fade-controller>
      <fade-settings-handler
        .fadeController=${this.fadeController}
        .settingsPersistence=${this.settingsPersistence}
        .onFadeInChange=${() => {
        this.requestUpdate(); // Trigger re-render to update fade-controller properties
      }}
        .onFadeOutChange=${() => {
        this.requestUpdate(); // Trigger re-render to update fade-controller properties
      }}
      ></fade-settings-handler>
      <peak-handler
        .prompts=${this.prompts}
        .toastMessage=${this.toastMessage}
      ></peak-handler>
      <prompt-manager
        .prompts=${this.prompts}
        .filteredPrompts=${this.filteredPromptsControllerElement?.getFilteredPrompts() || new Set()}
        .session=${this.session}
        .toastMessage=${this.toastMessage}
        .backgroundGenerator=${this.backgroundGenerator}
        .hostElement=${this}
        .generationStyle=${this.generationStyle}
        .autoVariationEnabled=${this.autoVariationEnabled}
        .autoVariationRate=${this.autoVariationRate}
        .autoVariationDepth=${this.autoVariationDepth}
        .autoVariationMinInterval=${this.autoVariationMinInterval}
        .autoVariationMaxInterval=${this.autoVariationMaxInterval}
        .autoVariationMaxChange=${this.autoVariationMaxChange}
      ></prompt-manager>
      <playback-duration-controller
        .toastMessage=${this.toastMessage}
        .playbackState=${this.playbackState}
      ></playback-duration-controller>
      <settings-persistence
        .toastMessage=${this.toastMessage}
        .prompts=${this.prompts}
      ></settings-persistence>
      <preset-controller .prompts=${this.prompts}></preset-controller>
      <audio-level-monitor
        .audioAnalyser=${this.audioAnalyser}
        .waveformVisualizer=${this.waveformVisualizer}
        @audio-level-change=${(e: CustomEvent<number>) => (this.audioLevel = e.detail)}
      ></audio-level-monitor>
      <audio-buffer-handler
        .audioContext=${this.audioContext}
        .outputNode=${this.outputNode}
        .playbackState=${this.playbackState}
        .statusMessage=${this.statusMessageComponent}
      ></audio-buffer-handler>
      <master-volume-controller
        .outputNode=${this.outputNode}
        .fadeController=${this.fadeController}
        .settingsPersistence=${this.settingsPersistence}
        .playbackState=${this.playbackState}
      ></master-volume-controller>
      <playback-controller
        .session=${this.session}
        .audioContext=${this.audioContext}
        .outputNode=${this.outputNode}
        .audioAnalyser=${this.audioAnalyser}
        .toastMessage=${this.toastMessage}
        .audioContextManager=${this.audioContextManager}
        .fadeController=${this.fadeController}
        .audioBufferHandler=${this.audioBufferHandler}
        .playbackDurationController=${this.playbackDurationController}
        .sessionTimer=${this.sessionTimer}
        .getPromptsToSend=${() => this.getPromptsToSend()}
        .handleDisconnection=${() => this.sessionControllerElement?.handleDisconnection()}
        .masterVolume=${this.masterVolume}
        .playbackState=${this.playbackState}
        @output-node-recreated=${(e: CustomEvent<GainNode>) => this.handleOutputNodeRecreated(e.detail)}
      ></playback-controller>
      <midi-ui-controller
        .midiDispatcher=${this.midiDispatcher}
        .showMidi=${this.showMidi}
        .midiInputIds=${this.midiInputIds}
        .activeMidiInputId=${this.activeMidiInputId}
        .filteredPrompts=${this.filteredPromptsControllerElement?.getFilteredPrompts() || new Set()}
        @midi-ui-state-change=${(e: CustomEvent) => {
        const state = e.detail;
        this.showMidi = state.showMidi;
        this.midiInputIds = state.midiInputIds;
        this.activeMidiInputId = state.activeMidiInputId;
        // filteredPrompts updates handled by FilteredPromptsController
      }}
      ></midi-ui-controller>
      <frequency-history-manager
        .frequencyHistory=${this.frequencyHistoryManager.getFrequencyHistory()}
      ></frequency-history-manager>
      <dependency-initializer
        .settingsPersistence=${this.settingsPersistence}
        .connectionController=${this.connectionController}
        .playbackController=${this.playbackController}
        .promptManager=${this.promptManager}
        .playbackDurationController=${this.playbackDurationController}
        .musicConfigController=${this.musicConfigController}
        .audioLevelMonitor=${this.audioLevelMonitor}
        .frequencyHistoryManager=${this.frequencyHistoryManager}
        .audioBufferHandler=${this.audioBufferHandler}
        .masterVolumeController=${this.masterVolumeController}
        .toastMessage=${this.toastMessage}
        .statusMessageComponent=${this.statusMessageComponent}
        .waveformVisualizer=${this.waveformVisualizer}
        .outputNode=${this.outputNode}
        .fadeController=${this.fadeController}
        .prompts=${this.prompts}
        .backgroundGenerator=${this.backgroundGenerator}
        .hostElement=${this}
        .session=${this.session}
        .playbackState=${this.playbackState}
        .connectToSession=${() => this.sessionControllerElement?.connectToSession()}
        .setSessionPrompts=${() => this.setSessionPrompts()}
        .getPromptsToSend=${() => this.getPromptsToSend()}
        .handleDisconnection=${() => this.sessionControllerElement?.handleDisconnection()}
        .onPlaybackStateChange=${(state: PlaybackState) => {
        this.playbackState = state;
      }}
        .onPlaybackControllerStateChange=${(state: { playbackState: PlaybackState, lastPlaybackTime: number }) => {
        this.playbackState = state.playbackState;
        this.lastPlaybackTime = state.lastPlaybackTime;
      }}
        .onFrequencyHistoryUpdate=${() => {
        this.requestUpdate();
      }}
        .onMasterVolumeChange=${(volume: number) => {
        this.masterVolume = volume;
      }}
        .peakInteractionController=${this.peakInteractionController}
      ></dependency-initializer>
      <filtered-prompts-controller
        .toastMessage=${this.toastMessage}
      ></filtered-prompts-controller>
      <output-node-controller
        .masterVolumeController=${this.masterVolumeController}
        .audioBufferHandler=${this.audioBufferHandler}
        .fadeController=${this.fadeController}
        .hostElement=${this}
      ></output-node-controller>
      <session-controller
        .toastMessage=${this.toastMessage}
        .statusMessage=${this.statusMessageComponent}
        .googleAIConfig=${this.googleAIConfig}
        .connectionController=${this.connectionController}
        .sessionTimer=${this.sessionTimer}
        .audioBufferHandler=${this.audioBufferHandler}
        .filteredPromptsController=${this.filteredPromptsControllerElement}
        .musicConfigController=${this.musicConfigController}
        .promptManager=${this.promptManager}
        .audioContext=${this.audioContext}
        .settingsPersistence=${this.settingsPersistenceElement}
        .setSessionPrompts=${() => this.setSessionPrompts()}
        .onSessionCreated=${(session: LiveMusicSession) => {
        this.session = session;
        // Auto-start playback if there are active prompts
        const activePrompts = Array.from(this.prompts.values()).filter(p => p.weight > 0);
        if (activePrompts.length > 0) {
          this.playbackController.session = session; // Ensure PlaybackController has the session
          this.playbackController.play();
        }
      }}
        .onPlaybackStateChange=${(state: string) => { this.playbackState = state as PlaybackState; }}
        .onAudioBufferHistoryUpdate=${(history: AudioBuffer[]) => { this.audioBufferHistory = history; }}
        @session-closed=${() => {
        console.log('Main: session-closed received, clearing session refs');
        this.session = null;
        this.playbackController.session = null;
        if (this.playPauseHandlerElement) {
          this.playPauseHandlerElement.session = null;
        }
      }}
        @resume-playback=${() => {
        // CRITICAL FIX: Always ensure PlaybackController has the latest session before attempting to play
        if (this.session) {
          console.log('=== SETTING SESSION ON PLAYBACK CONTROLLER ===');
          this.playbackController.session = this.session;
        }

        // Also ensure other required properties are synchronized
        this.playbackController.masterVolume = this.masterVolume;

        this.playbackController.play(); // PlaybackController handles resume logic internally
      }}
        @stop-playback=${() => {
        // Ensure PlaybackController state is synchronized before stopping
        this.playbackController.masterVolume = this.masterVolume;
        this.playbackController.stop();
      }}
      ></session-controller>
      <settings-coordinator
        .toastMessage=${this.toastMessage}
        .playbackDurationController=${this.playbackDurationController}
        .playbackController=${this.playbackController}
        .uiStateController=${this.uiStateController}
      ></settings-coordinator>
      <toast-message></toast-message>
      <ui-state-controller></ui-state-controller>
      <event-handler-controller
        .uiStateController=${this.uiStateController}
        .playbackDurationController=${this.playbackDurationController}
        .masterVolumeController=${this.masterVolumeController}
        .midiUIController=${this.midiUIController}
        .toggleShowMidi=${() => this.toggleShowMidi()}
        .onMasterVolumeChange=${(volume: number) => { this.masterVolume = volume; }}
        .onMidiInputChange=${(activeMidiInputId: string | null) => { this.activeMidiInputId = activeMidiInputId; }}
      ></event-handler-controller>
      <peak-interaction-controller
        .prompts=${this.prompts}
        .toastMessage=${this.toastMessage}
      ></peak-interaction-controller>
    </main-container>`;
  }



  override async disconnectedCallback() {
    super.disconnectedCallback();
    // AudioLevelMonitor handles its own cleanup in disconnectedCallback
    // AudioContextManager handles its own cleanup in disconnectedCallback
    // SessionController handles session and session timer cleanup in its disconnectedCallback

    // Clean up session timer event listener
    this.sessionTimer.removeEventListener('session-duration-updated', this.sessionTimerUpdateListener);

    this.audioContext.close();
    this.playbackDurationController.stopTimedSession();
  }



  // Recording methods now handled by RecordingController component
  private async startRecording() {
    await this.recordingController.startRecording();
  }

  private stopRecording() {
    this.recordingController.stopRecording();
  }






  // Session reconnection now handled by SessionController component

  // Testing methods for audio diagnostics
  private async testAudioChain() {
    try {
      console.log('=== TESTING AUDIO CHAIN ===');
      console.log('AudioContext state:', this.audioContext.state);
      console.log('OutputNode gain:', this.outputNode.gain.value);
      console.log('Master volume:', this.masterVolume);

      // Test with a simple sine wave
      const oscillator = this.audioContext.createOscillator();
      const testGain = this.audioContext.createGain();

      oscillator.frequency.setValueAtTime(440, this.audioContext.currentTime); // A note
      testGain.gain.setValueAtTime(0.1, this.audioContext.currentTime); // Low volume test

      oscillator.connect(testGain);
      testGain.connect(this.outputNode);

      oscillator.start(this.audioContext.currentTime);
      oscillator.stop(this.audioContext.currentTime + 0.5); // 0.5 second test tone

      console.log('Test tone sent through audio chain');
      this.toastMessage?.show('Audio test tone played - check if you heard it');
    } catch (error) {
      console.error('Audio chain test failed:', error);
      this.toastMessage?.show('Audio chain test failed - check console');
    }
  }
} 