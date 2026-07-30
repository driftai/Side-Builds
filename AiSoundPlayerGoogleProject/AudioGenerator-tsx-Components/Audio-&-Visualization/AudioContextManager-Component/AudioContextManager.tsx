import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';

type PlaybackState = 'stopped' | 'playing' | 'loading' | 'paused';

@customElement('audio-context-manager')
export class AudioContextManager extends LitElement {
  @property({ type: Object }) audioContext!: AudioContext;
  @property({ type: String }) playbackState: PlaybackState = 'stopped';

  private audioContextResumeInterval: number | null = null;

  constructor() {
    super();
    this.resumeAudioContext = this.resumeAudioContext.bind(this);
  }

  override connectedCallback() {
    super.connectedCallback();
    // Add document-level click handler to resume AudioContext
    document.addEventListener('click', this.resumeAudioContext, true);
    document.addEventListener('keydown', this.resumeAudioContext, true);
  }

  override disconnectedCallback() {
    super.disconnectedCallback();
    // Remove document event listeners
    document.removeEventListener('click', this.resumeAudioContext, true);
    document.removeEventListener('keydown', this.resumeAudioContext, true);
    // Clean up AudioContext check interval
    this.stopAudioContextCheckInterval();
  }

  startAudioContextCheckInterval() {
    // Clear any existing interval
    if (this.audioContextResumeInterval) {
      clearInterval(this.audioContextResumeInterval);
    }
    
    // Check and resume AudioContext more frequently during playback
    this.audioContextResumeInterval = window.setInterval(async () => {
      if ((this.playbackState === 'playing' || this.playbackState === 'loading') && 
          this.audioContext.state === 'suspended') {
        try {
          await this.audioContext.resume();
          console.log('AudioContext resumed by regular check interval');
        } catch (err) {
          console.error('Failed to resume AudioContext in check interval:', err);
        }
      }
    }, 500); // Check twice per second
  }

  stopAudioContextCheckInterval() {
    if (this.audioContextResumeInterval) {
      clearInterval(this.audioContextResumeInterval);
      this.audioContextResumeInterval = null;
    }
  }

  // Helper method to try resuming AudioContext
  async resumeAudioContext() {
    if (this.audioContext && this.audioContext.state === 'suspended') {
      try {
        await this.audioContext.resume();
        console.log('AudioContext resumed by user interaction');
      } catch (err) {
        console.error('Failed to resume AudioContext:', err);
      }
    }
  }

  // Public method to ensure AudioContext is resumed
  async ensureAudioContextResumed(): Promise<boolean> {
    if (!this.audioContext) {
      console.error('No AudioContext available');
      return false;
    }

    if (this.audioContext.state === 'suspended') {
      try {
        await this.audioContext.resume();
        console.log('AudioContext resumed in ensureAudioContextResumed()');
        return true;
      } catch (err) {
        console.error('Error resuming AudioContext in ensureAudioContextResumed():', err);
        return false;
      }
    }
    return true; // Already running
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 