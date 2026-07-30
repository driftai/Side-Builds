import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

interface ToastMessage {
  show(message: string): void;
}

interface LiveMusicSession {
  setMusicGenerationConfig(config: { musicGenerationConfig: any }): Promise<void>;
}

@customElement('music-config-controller')
export class MusicConfigController extends LitElement {
  @property({ type: Object }) session: LiveMusicSession | null = null;
  @property({ type: Object }) toastMessage!: ToastMessage;

  /**
   * Monitor session changes and send config when session becomes available
   */
  override updated(changedProperties: Map<string, unknown>) {
    super.updated(changedProperties);

    // If session property changed to a valid session, send the current config
    if (changedProperties.has('session') && this.session) {
      console.log('MusicConfigController: Session attached, sending initial config');
      this.sendMusicConfig();
    }
  }

  // Music Generation Config States
  @state() private currentBpm: number = 90; // Default BPM
  @state() private currentDensity: number = 0.5; // Default Density
  @state() private currentBrightness: number = 0.5; // Default Brightness
  @state() private currentGuidance: number = 4.0; // Default Guidance
  @state() private currentTemperature: number = 1.5; // Default Temperature (slightly higher for more variation)
  @state() private muteBass: boolean = false; // Default mute bass
  @state() private muteDrums: boolean = false; // Default mute drums
  @state() private muteOther: boolean = false; // Default mute other (harmonics/melodics)
  @state() private currentScale: string = 'SCALE_UNSPECIFIED'; // Default musical key/scale

  // Music Generation Config Default States
  @state() private useDefaultBpm: boolean = true; // Use model default for BPM
  @state() private useDefaultDensity: boolean = true; // Use model default for Density
  @state() private useDefaultBrightness: boolean = true; // Use model default for Brightness
  @state() private useDefaultGuidance: boolean = true; // Use model default for Guidance
  @state() private useDefaultTemperature: boolean = true; // Model decides chaos/temperature by default

  // Throttle function for config updates
  private sendMusicConfig = this.throttle(async () => {
    if (!this.session) return;
    try {
      await this.session.setMusicGenerationConfig({
        musicGenerationConfig: {
          bpm: this.useDefaultBpm ? undefined : this.currentBpm,
          density: this.useDefaultDensity ? undefined : this.currentDensity,
          brightness: this.useDefaultBrightness ? undefined : this.currentBrightness,
          guidance: this.useDefaultGuidance ? undefined : this.currentGuidance,
          temperature: this.useDefaultTemperature ? undefined : this.currentTemperature,
          muteBass: this.muteBass,
          muteDrums: this.muteDrums,
          onlyBassAndDrums: this.muteOther, // "Only Bass & Drums" mode
          scale: this.currentScale === 'SCALE_UNSPECIFIED' ? undefined : this.currentScale as any,
        }
      });
      console.log('Sent music config update:', {
        bpm: this.currentBpm,
        density: this.currentDensity,
        brightness: this.currentBrightness,
        guidance: this.currentGuidance,
        temperature: this.currentTemperature,
        muteBass: this.muteBass,
        muteDrums: this.muteDrums,
        muteOther: this.muteOther,
        scale: this.currentScale
      });
    } catch (e: any) {
      console.error('Error sending music config:', e);
      this.toastMessage.show(`Error sending music config: ${e.message}`);
    }
  }, 50); // Reduced throttle for more responsive music parameter updates

  // Simple throttle implementation
  private throttle<T extends (...args: any[]) => any>(func: T, delay: number): (...args: Parameters<T>) => ReturnType<T> {
    let lastCall = -Infinity;
    let lastResult: ReturnType<T>;
    return (...args: Parameters<T>) => {
      const now = Date.now();
      const timeSinceLastCall = now - lastCall;
      if (timeSinceLastCall >= delay) {
        lastResult = func(...args);
        lastCall = now;
      }
      return lastResult;
    };
  }

  // Getters for external access to config values
  get musicConfig() {
    return {
      currentBpm: this.currentBpm,
      currentDensity: this.currentDensity,
      currentBrightness: this.currentBrightness,
      currentGuidance: this.currentGuidance,
      currentTemperature: this.currentTemperature,
      muteBass: this.muteBass,
      muteDrums: this.muteDrums,
      muteOther: this.muteOther,
      currentScale: this.currentScale,
      useDefaultBpm: this.useDefaultBpm,
      useDefaultDensity: this.useDefaultDensity,
      useDefaultBrightness: this.useDefaultBrightness,
      useDefaultGuidance: this.useDefaultGuidance,
      useDefaultTemperature: this.useDefaultTemperature
    };
  }

  // Methods for updating individual config values
  updateBpm(value: number) {
    this.currentBpm = value;
    this.sendMusicConfig();
  }

  updateDensity(value: number) {
    this.currentDensity = value;
    this.sendMusicConfig();
  }

  updateBrightness(value: number) {
    this.currentBrightness = value;
    this.sendMusicConfig();
  }

  updateGuidance(value: number) {
    this.currentGuidance = value;
    this.sendMusicConfig();
  }

  updateTemperature(value: number) {
    this.currentTemperature = value;
    this.sendMusicConfig();
  }

  updateMuteBass(value: boolean) {
    this.muteBass = value;
    this.sendMusicConfig();
  }

  updateMuteDrums(value: boolean) {
    this.muteDrums = value;
    this.sendMusicConfig();
  }

  updateMuteOther(value: boolean) {
    this.muteOther = value;
    this.sendMusicConfig();
  }

  updateScale(value: string) {
    this.currentScale = value;
    this.sendMusicConfig();
  }

  updateUseDefaultBpm(value: boolean) {
    this.useDefaultBpm = value;
    this.sendMusicConfig();
  }

  updateUseDefaultDensity(value: boolean) {
    this.useDefaultDensity = value;
    this.sendMusicConfig();
  }

  updateUseDefaultBrightness(value: boolean) {
    this.useDefaultBrightness = value;
    this.sendMusicConfig();
  }

  updateUseDefaultGuidance(value: boolean) {
    this.useDefaultGuidance = value;
    this.sendMusicConfig();
  }

  updateUseDefaultTemperature(value: boolean) {
    this.useDefaultTemperature = value;
    this.sendMusicConfig();
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 