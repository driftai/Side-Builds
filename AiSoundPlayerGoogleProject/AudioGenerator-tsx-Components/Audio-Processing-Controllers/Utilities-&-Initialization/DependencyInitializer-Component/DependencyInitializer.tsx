import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';

// Interface definitions for the components we'll be coordinating
interface SettingsPersistence {
  toastMessage: any;
  prompts: Map<string, any>;
  loadPresetsFromStorage(): void;
  mergePresets(importedPresets: Map<string, Map<string, any>>): void;
  presetData: {
    savedKnobPresets: Map<string, Map<string, any>>;
    selectedPresetName: string;
    newPresetName: string;
  };
}

interface ConnectionController {
  toastMessage: any;
  statusMessage: any;
}

interface PlaybackController {
  toastMessage: any;
  statusMessage: any;
  getPromptsToSend: () => any;
  handleDisconnection: () => void;
  addEventListener(event: string, handler: (e: Event) => void): void;
  settingsPersistence: any;
}

interface PromptManager {
  prompts: Map<string, any>;
  toastMessage: any;
  backgroundGenerator: any;
  hostElement: any;
  session: any;
}

interface PlaybackDurationController {
  toastMessage: any;
  playbackState: string;
}

interface MusicConfigController {
  session: any;
  toastMessage: any;
}

interface AudioLevelMonitor {
  waveformVisualizer: any;
  addEventListener(event: string, handler: (e: Event) => void): void;
}

interface FrequencyHistoryManager {
  addEventListener(event: string, handler: (e: Event) => void): void;
}

interface AudioBufferHandler {
  statusMessage: any;
  addEventListener(event: string, handler: (e: Event) => void): void;
}

interface MasterVolumeController {
  outputNode: any;
  settingsPersistence: any;
  fadeController: any;
  addEventListener(event: string, handler: (e: Event) => void): void;
}

@customElement('dependency-initializer')
export class DependencyInitializer extends LitElement {
  // Component references
  @property({ type: Object }) settingsPersistence!: SettingsPersistence;
  @property({ type: Object }) connectionController!: ConnectionController;
  @property({ type: Object }) playbackController!: PlaybackController;
  @property({ type: Object }) promptManager!: PromptManager;
  @property({ type: Object }) playbackDurationController!: PlaybackDurationController;
  @property({ type: Object }) musicConfigController!: MusicConfigController;
  @property({ type: Object }) audioLevelMonitor!: AudioLevelMonitor;
  @property({ type: Object }) frequencyHistoryManager!: FrequencyHistoryManager;
  @property({ type: Object }) audioBufferHandler!: AudioBufferHandler;
  @property({ type: Object }) masterVolumeController!: MasterVolumeController;

  // UI component references (passed from parent)
  @property({ type: Object }) toastMessage!: any;
  @property({ type: Object }) statusMessageComponent!: any;
  @property({ type: Object }) waveformVisualizer!: any;

  // Audio component references (passed from parent)
  @property({ type: Object }) outputNode!: any;
  @property({ type: Object }) fadeController!: any;

  // Data references
  @property({ type: Object }) prompts!: Map<string, any>;
  @property({ type: Object }) backgroundGenerator!: any;
  @property({ type: Object }) hostElement!: any;
  @property({ type: Object }) session!: any;
  @property({ type: String }) playbackState!: string;

  // Callback functions
  @property({ type: Function }) connectToSession!: () => Promise<void>;
  @property({ type: Function }) setSessionPrompts!: () => Promise<void>;
  @property({ type: Function }) getPromptsToSend!: () => any;
  @property({ type: Function }) handleDisconnection!: () => void;
  @property({ type: Function }) onPresetDataLoaded!: (presetData: any) => void;
  @property({ type: Function }) onPlaybackStateChange!: (state: any) => void;
  @property({ type: Function }) onPlaybackControllerStateChange!: (state: any) => void;
  @property({ type: Function }) onFrequencyHistoryUpdate!: () => void;
  @property({ type: Function }) onMasterVolumeChange!: (volume: number) => void;

  override async firstUpdated() {
    await this.initializeAllDependencies();
  }

  /**
   * Monitor session changes and update PromptManager accordingly
   */
  override updated(changedProperties: Map<string, unknown>) {
    super.updated(changedProperties);
    
    // If session property changed, update PromptManager's session
    if (changedProperties.has('session')) {
      console.log('DependencyInitializer: Session updated, PromptManager now has session:', !!this.session);
      if (this.promptManager) {
        this.promptManager.session = this.session;
      }
    }
  }

  /**
   * Initializes all component dependencies and sets up cross-component communication
   */
  async initializeAllDependencies() {
    // Lazy load ToastMessage component to avoid blocking audio initialization
    import('../../../AudioGenerator-tsx-Components.js');
    
    // Initialize settings
    this.settingsPersistence.toastMessage = this.toastMessage;
    this.settingsPersistence.prompts = this.prompts;
    
    // Setup component dependencies that require UI elements
    this.setupUIComponentDependencies();
    
    // Setup MasterVolumeController dependencies
    this.setupMasterVolumeController();
    
    // Setup data flow between components
    this.setupPromptManagerDependencies();
    
    // Initialize session and configuration
    await this.initializeSessionAndConfig();
    
    // Setup event listeners for cross-component communication
    this.setupEventListeners();
  }

  /**
   * Setup dependencies for components that require UI elements
   */
  private setupUIComponentDependencies() {
    // Set up component dependencies now that @query elements are available
    this.connectionController.toastMessage = this.toastMessage;
    this.connectionController.statusMessage = this.statusMessageComponent;
    
    // Set up PlaybackController dependencies that require @query elements
    this.playbackController.toastMessage = this.toastMessage;
    this.playbackController.statusMessage = this.statusMessageComponent;
    this.playbackController.getPromptsToSend = this.getPromptsToSend;
    this.playbackController.handleDisconnection = this.handleDisconnection;
    this.playbackController.settingsPersistence = this.settingsPersistence;
    
    // Set up PlaybackDurationController dependencies
    this.playbackDurationController.toastMessage = this.toastMessage;
    this.playbackDurationController.playbackState = this.playbackState;
    
    // Set up AudioBufferHandler with statusMessage dependency
    this.audioBufferHandler.statusMessage = this.statusMessageComponent;
  }

  /**
   * Setup MasterVolumeController dependencies
   */
  private setupMasterVolumeController() {
    // Set up MasterVolumeController with audio nodes and persistence
    this.masterVolumeController.outputNode = this.outputNode;
    this.masterVolumeController.settingsPersistence = this.settingsPersistence;
    this.masterVolumeController.fadeController = this.fadeController;
  }

  /**
   * Setup PromptManager dependencies
   */
  private setupPromptManagerDependencies() {
    this.promptManager.prompts = this.prompts;
    this.promptManager.toastMessage = this.toastMessage;
    this.promptManager.backgroundGenerator = this.backgroundGenerator;
    this.promptManager.hostElement = this.hostElement;
  }

  /**
   * Initialize session and music configuration
   */
  private async initializeSessionAndConfig() {
    console.log('DependencyInitializer: Initializing session and config...');
    
    // Connect to session and set prompts
    await this.connectToSession();
    
    // The session will be updated via the updated() method when the property changes
    // No need to manually set it here since it might still be null
    console.log('DependencyInitializer: Session connection completed, session available:', !!this.session);
    
    // Set initial session prompts
    await this.setSessionPrompts();
    
    // Initialize music config controller with session and toast message
    // Note: MusicConfigController will get session via property binding in main component
    this.musicConfigController.toastMessage = this.toastMessage;
  }

  /**
   * Setup event listeners for cross-component communication
   */
  private setupEventListeners() {
    // Set up AudioLevelMonitor with waveform visualizer dependency
    this.audioLevelMonitor.waveformVisualizer = this.waveformVisualizer;
    
    // Set up FrequencyHistoryManager connection
    this.frequencyHistoryManager.addEventListener('frequency-history-updated', () => {
      if (this.onFrequencyHistoryUpdate) {
        this.onFrequencyHistoryUpdate();
      }
    });
    
    // Listen for playback state changes from the buffer handler
    this.audioBufferHandler.addEventListener('playback-state-change', (e: Event) => {
      const customEvent = e as CustomEvent<any>;
      if (this.onPlaybackStateChange) {
        this.onPlaybackStateChange(customEvent.detail);
      }
    });
    
    // Listen for playback state changes from the PlaybackController
    this.playbackController.addEventListener('playback-state-change', (e: Event) => {
      const customEvent = e as CustomEvent<{playbackState: any, lastPlaybackTime: number}>;
      if (this.onPlaybackControllerStateChange) {
        this.onPlaybackControllerStateChange(customEvent.detail);
      }
    });

    // Listen for master volume updates from the MasterVolumeController
    this.masterVolumeController.addEventListener('master-volume-updated', (e: Event) => {
      const customEvent = e as CustomEvent<number>;
      if (this.onMasterVolumeChange) {
        this.onMasterVolumeChange(customEvent.detail);
      }
    });
  }

  override render() {
    // This component doesn't render UI directly, it's a dependency coordinator
    return null;
  }
} 