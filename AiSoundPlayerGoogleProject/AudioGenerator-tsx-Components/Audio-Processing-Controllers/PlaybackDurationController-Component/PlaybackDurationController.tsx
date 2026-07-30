import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

interface ToastMessage {
  show(message: string): void;
}

@customElement('playback-duration-controller')
export class PlaybackDurationController extends LitElement {
  @property({ type: Object }) toastMessage!: ToastMessage;
  @property({ type: String }) playbackState: 'stopped' | 'playing' | 'loading' | 'paused' = 'stopped';

  @state() playbackDurationMode: 'indefinite' | 'timed' = 'indefinite';
  @state() playbackDurationMinutes = 30;
  @state() fadeOutDurationSec = 5; // Default fade-out duration
  
  private sessionTimerId: number | null = null;

  /**
   * Starts a timed session if in timed mode
   * @param onSessionEnd Callback to execute when session ends
   */
  startTimedSession(onSessionEnd: () => void) {
    // Clear any existing timer before starting a new one
    if (this.sessionTimerId) {
      clearTimeout(this.sessionTimerId);
      this.sessionTimerId = null;
    }

    // Start timer if in timed mode
    if (this.playbackDurationMode === 'timed') {
      const totalDurationSec = this.playbackDurationMinutes * 60;
      // Schedule stop call earlier by the fade out duration
      const stopCallTimeSec = Math.max(0, totalDurationSec - this.fadeOutDurationSec);

      this.sessionTimerId = window.setTimeout(() => {
        this.toastMessage?.show(`Session ending after ${this.playbackDurationMinutes} minutes.`);
        onSessionEnd();
      }, stopCallTimeSec * 1000);

      this.toastMessage?.show(`Playback started. Session will end in ${this.playbackDurationMinutes} minutes with a ${this.fadeOutDurationSec} second fade out.`);
    } else {
      this.toastMessage?.show('Playback started (indefinite duration).');
    }
  }

  /**
   * Stops the current timed session
   */
  stopTimedSession() {
    if (this.sessionTimerId) {
      clearTimeout(this.sessionTimerId);
      this.sessionTimerId = null;
    }
  }

  /**
   * Updates playback duration mode
   */
  updateDurationMode(mode: 'indefinite' | 'timed') {
    this.playbackDurationMode = mode;
    this.dispatchEvent(new CustomEvent('duration-mode-change', { 
      detail: mode,
      bubbles: true,
      composed: true 
    }));
  }

  /**
   * Updates playback duration in minutes
   */
  updateDurationMinutes(minutes: number) {
    this.playbackDurationMinutes = minutes;
    this.dispatchEvent(new CustomEvent('duration-minutes-change', { 
      detail: minutes,
      bubbles: true,
      composed: true 
    }));
  }

  /**
   * Updates fade out duration
   */
  updateFadeOutDuration(seconds: number) {
    this.fadeOutDurationSec = seconds;
    this.dispatchEvent(new CustomEvent('fade-out-duration-change', { 
      detail: seconds,
      bubbles: true,
      composed: true 
    }));
  }

  /**
   * Applies settings and restarts timer if needed during playback
   * @param onSessionEnd Callback to execute when session ends
   */
  applySettings(onSessionEnd: () => void) {
    // If currently playing and mode changed to timed, or duration changed for timed mode,
    // we need to reset the timer.
    if (this.playbackState === 'playing' && this.playbackDurationMode === 'timed') {
      this.stopTimedSession();
      this.startTimedSession(onSessionEnd);
    } else if (this.playbackDurationMode === 'indefinite') {
      this.stopTimedSession();
    }
  }

  /**
   * Gets current duration settings
   */
  get durationSettings() {
    return {
      playbackDurationMode: this.playbackDurationMode,
      playbackDurationMinutes: this.playbackDurationMinutes,
      fadeOutDurationSec: this.fadeOutDurationSec,
      hasActiveTimer: this.sessionTimerId !== null
    };
  }

  override disconnectedCallback() {
    super.disconnectedCallback();
    this.stopTimedSession();
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 