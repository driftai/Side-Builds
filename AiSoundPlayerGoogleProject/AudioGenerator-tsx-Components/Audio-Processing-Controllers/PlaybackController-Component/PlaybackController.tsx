import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

type PlaybackState = 'stopped' | 'playing' | 'loading' | 'paused';

interface LiveMusicSession {
  play(): void;
  pause(): void;
  stop(): void;
  close(): void;
}

interface ToastMessage {
  show(message: string): void;
}

interface StatusMessage {
  show(message: string): void;
}

interface AudioContextManager {
  playbackState: PlaybackState;
  startAudioContextCheckInterval(): void;
  stopAudioContextCheckInterval(): void;
}

interface FadeController {
  outputNode: GainNode;
  applyFadeIn(masterVolume: number): void;
  applyFadeOut(targetVolume: number): Promise<void>;
}

interface AudioBufferHandler {
  outputNode: GainNode;
  playbackState: PlaybackState;
  reset(): void;
}

interface PlaybackDurationController {
  startTimedSession(callback: () => void): void;
  stopTimedSession(): void;
}

interface SessionTimer {
  stopSession(): void;
}

interface SettingsPersistence {
  savePlaybackState(state: 'stopped' | 'playing' | 'loading' | 'paused'): void;
  clearPlaybackState(): void;
}

@customElement('playback-controller')
export class PlaybackController extends LitElement {
  @property({ type: Object }) session: LiveMusicSession | null = null;
  @property({ type: Object }) audioContext!: AudioContext;
  @property({ type: Object }) outputNode!: GainNode;
  @property({ type: Object }) audioAnalyser!: { node: AnalyserNode };
  @property({ type: Object }) toastMessage!: ToastMessage;
  @property({ type: Object }) statusMessage!: StatusMessage;
  @property({ type: Object }) audioContextManager!: AudioContextManager;
  @property({ type: Object }) fadeController!: FadeController;
  @property({ type: Object }) audioBufferHandler!: AudioBufferHandler;
  @property({ type: Object }) playbackDurationController!: PlaybackDurationController;
  @property({ type: Object }) sessionTimer!: SessionTimer;
  @property({ type: Object }) settingsPersistence!: SettingsPersistence;
  @property({ type: Function }) getPromptsToSend!: () => any[];
  @property({ type: Function }) handleDisconnection!: () => void;
  @property({ type: Number }) masterVolume = 1;
  @property({ type: String }) playbackState: PlaybackState = 'stopped';

  @state() private internalPlaybackState: PlaybackState = 'stopped';
  @state() lastPlaybackTime = 0;

  /**
   * Pauses the current playback session
   */
  pause() {
    console.log('PlaybackController pause() called');

    // Update UI state immediately for instant feedback
    this.internalPlaybackState = 'paused';
    this.dispatchPlaybackStateChange('paused');
    this.statusMessage?.show('Paused');

    if (this.session) {
      // Close server-side generation immediately
      // Prefer direct API if available
      (this.session as any).close?.();
      // Fallback to stop
      this.session.stop();
      console.log('Session stopped/closed on pause');
      this.session = null;
    }

    // Capture the current time before pausing for visualization
    this.lastPlaybackTime = this.audioContext.currentTime;

    // CRITICAL FIX: Immediate volume reduction for pause
    console.log('Setting volume to 0 for pause');
    this.outputNode.gain.setValueAtTime(0, this.audioContext.currentTime);

    // Update AudioBufferHandler state but don't reset - just pause
    this.audioBufferHandler.playbackState = 'paused';

    // Stop AudioContext check interval
    this.audioContextManager.stopAudioContextCheckInterval();

    console.log('PlaybackController pause() completed');
  }

  /**
   * Starts or resumes playback
   */
  async play() {
    console.log('=== PlaybackController play() called ===');
    console.log('Current internal state:', this.internalPlaybackState);
    console.log('Session available:', !!this.session);
    console.log('Master volume:', this.masterVolume);

    const promptsToSend = this.getPromptsToSend();
    console.log('Active prompts count:', promptsToSend.length);

    if (promptsToSend.length === 0) {
      console.log('No active prompts, cannot start playback');
      this.toastMessage?.show('There needs to be one active prompt to play. Turn up a knob to resume playback.')
      if (this.session) {
        this.pause();
      }
      this.statusMessage?.show('Action Required: Adjust a knob to play.');
      return;
    }

    // Ensure AudioContext is resumed
    if (this.audioContext.state === 'suspended') {
      try { await this.audioContext.resume(); } catch { }
    }

    // Ensure session is available
    if (!this.session) {
      console.log('No active session, attempting reconnection via handleDisconnection');
      this.toastMessage?.show('Reconnecting...');
      this.handleDisconnection();
      return;
    }

    console.log('PlaybackController.play() - Session is available:', !!this.session);

    // Start regular checking of AudioContext state
    this.audioContextManager.playbackState = 'loading';
    this.audioContextManager.startAudioContextCheckInterval();

    try {
      // Check if we're resuming from pause
      const wasResuming = this.internalPlaybackState === 'paused';

      try {
        this.session.play();
      } catch (err: any) {
        const msg = err?.message || String(err);
        console.warn('Session.play() failed:', msg);
        if (msg.includes('CLOSING') || msg.includes('CLOSED')) {
          // WebSocket is closed; trigger reconnection
          this.toastMessage?.show('Reconnecting session...');
          this.session = null;
          this.handleDisconnection();
          return;
        }
        throw err;
      }
      this.internalPlaybackState = 'loading';
      this.dispatchPlaybackStateChange('loading');
      this.statusMessage?.show(wasResuming ? 'Resuming audio...' : 'Loading audio...');

      // Apply fade-in using FadeController for smooth entry
      if (this.fadeController) {
        console.log('Applying fade-in via FadeController');
        this.fadeController.applyFadeIn(this.masterVolume);
      } else {
        console.warn('FadeController not available, applying master volume directly');
        this.outputNode.gain.setValueAtTime(this.masterVolume, this.audioContext.currentTime);
      }

      // Always reset the buffer handler on play to avoid stale schedule baselines
      this.audioBufferHandler.reset();
      this.audioBufferHandler.playbackState = 'loading';

      // Start timed session using PlaybackDurationController
      this.playbackDurationController.startTimedSession(() => {
        // This callback will be executed when the session ends
        this.gracefulStop();
      });

      console.log('PlaybackController play() completed, wasResuming:', wasResuming);
    } catch (error: any) {
      console.error('Error starting playback:', error);
      this.toastMessage?.show('Failed to start playback. Retrying connection...');
      this.handleDisconnection();
    }
  }

  /**
   * Stops playback gracefully with a fade-out
   */
  async gracefulStop() {
    console.log('PlaybackController gracefulStop() called');
    if (this.fadeController) {
      await this.fadeController.applyFadeOut(0);
    }
    this.stop();
  }

  /**
   * Stops the current playback session
   */
  stop() {
    console.log('PlaybackController stop() called');

    if (this.session) {
      // If we are loading, the socket may be closing/closed.
      // Avoid calling stop() which sends a control message and logs a red error.
      if (this.internalPlaybackState === 'loading') {
        (this.session as any).close?.();
        console.log('Session closed during loading');
      } else {
        try {
          this.session.stop();
        } catch (err: any) {
          const msg = err?.message || String(err);
          console.warn('Session.stop() failed:', msg);
        }
        (this.session as any).close?.();
        console.log('Session stopped/closed on stop');
      }
      this.session = null;
    }

    this.internalPlaybackState = 'stopped';
    this.dispatchPlaybackStateChange('stopped');
    this.statusMessage?.show('Stopped');
    this.lastPlaybackTime = 0; // Reset last playback time on stop

    // CRITICAL FIX: Don't recreate output node - just reset volume
    console.log('Resetting volume to 0 for stop');
    this.outputNode.gain.setValueAtTime(0, this.audioContext.currentTime);

    // Reset AudioBufferHandler state
    this.audioBufferHandler.playbackState = 'stopped';
    this.audioBufferHandler.reset();

    // Stop AudioContext check interval
    this.audioContextManager.stopAudioContextCheckInterval();

    this.playbackDurationController.stopTimedSession();
    this.sessionTimer.stopSession();
    console.log('PlaybackController stop() completed');
  }

  /**
   * Toggles between play and pause states
   */
  async handlePlayPause() {
    console.log('=== PlaybackController handlePlayPause START ===');
    console.log('External playback state:', this.playbackState);
    console.log('Internal playback state:', this.internalPlaybackState);
    console.log('Session available:', !!this.session);
    console.log('AudioContext state:', this.audioContext.state);

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

    // Use internal state for more accurate state tracking
    const currentState = this.internalPlaybackState;
    console.log('Using internal state for decision:', currentState);

    // Handle different playback states
    if (currentState === 'playing') {
      console.log('Currently playing, switching to pause...');
      this.pause();
    } else if (currentState === 'stopped' || currentState === 'paused') {
      console.log('Currently stopped/paused, switching to play...');
      await this.play();
    } else if (currentState === 'loading') {
      console.log('Currently loading, switching to stop...');
      this.stop();
    }

    console.log('=== PlaybackController handlePlayPause END ===');
  }

  /**
   * Dispatches playback state change event and persists state to localStorage
   */
  private dispatchPlaybackStateChange(state: PlaybackState) {
    console.log('PlaybackController: Dispatching state change from', this.internalPlaybackState, 'to', state);

    // Update internal state
    this.internalPlaybackState = state;

    // Save state to localStorage for persistence across page reloads
    if (this.settingsPersistence) {
      if (state === 'stopped') {
        // Clear persisted state when explicitly stopped
        this.settingsPersistence.clearPlaybackState();
      } else {
        // Save active states (playing, paused, loading) for auto-resume
        this.settingsPersistence.savePlaybackState(state);
      }
    }

    this.dispatchEvent(new CustomEvent('playback-state-change', {
      detail: {
        playbackState: state,
        lastPlaybackTime: this.lastPlaybackTime
      },
      bubbles: true,
      composed: true
    }));
  }



  /**
   * Gets the current playback state
   */
  getPlaybackState(): PlaybackState {
    return this.playbackState;
  }

  /**
   * Gets the last playback time for visualization
   */
  getLastPlaybackTime(): number {
    return this.lastPlaybackTime;
  }

  /**
   * Sets the playback state (for external updates)
   */
  setPlaybackState(state: PlaybackState) {
    this.internalPlaybackState = state;
    this.dispatchPlaybackStateChange(state);
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 