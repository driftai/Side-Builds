// Import necessary types and interfaces
import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';

type PlaybackState = 'stopped' | 'playing' | 'loading' | 'paused';

interface LiveMusicSession {
  // Add minimal interface if needed
}

interface PlaybackController {
  session: LiveMusicSession | null;
  masterVolume: number;
  handlePlayPause(): Promise<void>;
}

interface ToastMessage {
  show(message: string): void;
}

// Add new interfaces if needed
interface StatusMessage {
  show(message: string): void;
}

@customElement('play-pause-handler')
export class PlayPauseHandler extends LitElement {
  // Existing properties
  @property({ type: Object }) session: LiveMusicSession | null = null;
  @property({ type: Object }) playbackController!: PlaybackController;
  @property({ type: Number }) masterVolume = 1;
  @property({ type: String }) playbackState: PlaybackState = 'stopped';
  @property({ type: Object }) toastMessage!: ToastMessage;
  @property({ type: Function }) handleDisconnection!: () => void;

  // New properties
  @property({ type: Object }) audioContext!: AudioContext;
  @property({ type: Function }) getPromptsToSend!: () => any[];
  @property({ type: Object }) statusMessage!: StatusMessage;

  async handlePlayPause() {
    console.log('handlePlayPause called in main component, session:', !!this.session);
    console.log('PlaybackController available:', !!this.playbackController);
    console.log('Current playbackState in main component:', this.playbackState);
    
    // Ensure AudioContext is resumed by user gesture
    if (this.audioContext.state === 'suspended') {
      try {
        await this.audioContext.resume();
        console.log('AudioContext resumed by user gesture.');
      } catch (err: any) {
        console.error('Error resuming AudioContext:', err);
        this.toastMessage?.show('Could not start audio. Please try again.');
        return; // Don't proceed if context can't be resumed
      }
    }

    // Handle connection errors by attempting reconnection
    if (this.session === null) {
      console.log('No session available, attempting reconnection...');
      this.handleDisconnection();
      return;
    }

    // Update PlaybackController with current session and master volume
    this.playbackController.session = this.session;
    this.playbackController.masterVolume = this.masterVolume;
    
    // Delegate to PlaybackController
    await this.playbackController.handlePlayPause();
  }

  private async play() {
    // This would be extracted if needed, but for now assume PlaybackController handles it
  }

  override render() {
    // This is a controller component, no UI
    return null;
  }
} 