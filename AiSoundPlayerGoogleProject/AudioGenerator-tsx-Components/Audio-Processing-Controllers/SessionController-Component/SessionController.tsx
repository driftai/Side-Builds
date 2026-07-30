/**
 * @fileoverview Session Controller Component
 * @description Manages LiveMusicSession lifecycle including connection, disconnection, 
 * timeout handling, and reconnection logic
 * @license SPDX-License-Identifier: Apache-2.0
 */

import { LitElement, html } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { LiveMusicSession, LiveMusicServerMessage } from '@google/genai';

interface ToastMessage {
  show(message: string): void;
}

interface StatusMessage {
  show(message: string, duration?: number): void;
}

interface GoogleAIConfig {
  createLiveMusicSession(callbacks: {
    onmessage: (e: LiveMusicServerMessage) => Promise<void>;
    onerror: (e: ErrorEvent) => void;
    onclose: () => Promise<void>;
  }): Promise<LiveMusicSession>;
}

interface ConnectionController {
  connectionState: {
    isReconnecting: boolean;
    reconnectAttempts: number;
  };
  getReconnectDelay(): number;
  showReconnectionStatus(): void;
  markConnectionSuccessful(): void;
  markConnectionFailed(): void;
  resetConnectionState(): void;
  handleDisconnection(): Promise<boolean>;
  handleSessionTimeout(): Promise<boolean>;
}

interface SessionTimer {
  isSessionActive: boolean;
  getSessionDuration(): string;
  startSession(): void;
  stopSession(): void;
  resetSession(): void;
}

interface AudioBufferHandler {
  playbackState: string;
  processAudioChunk(data: string): Promise<void>;
  getAudioBufferHistory(): AudioBuffer[];
  reset(): void;
}

interface FilteredPromptsController {
  handleServerFilteredPrompt(filteredPrompt: { text?: string; filteredReason?: string }): void;
}

interface MusicConfigController {
  session: LiveMusicSession | null;
}

interface SettingsPersistence {
  loadPlaybackState(): 'stopped' | 'playing' | 'loading' | 'paused';
  savePlaybackState(state: 'stopped' | 'playing' | 'loading' | 'paused'): void;
  clearPlaybackState(): void;
}

interface PromptManager {
  session: LiveMusicSession | null;
}

@customElement('session-controller')
export class SessionController extends LitElement {
  @property({ type: Object }) toastMessage!: ToastMessage;
  @property({ type: Object }) statusMessage!: StatusMessage;
  @property({ type: Object }) googleAIConfig!: GoogleAIConfig;
  @property({ type: Object }) connectionController!: ConnectionController;
  @property({ type: Object }) sessionTimer!: SessionTimer;
  @property({ type: Object }) audioBufferHandler!: AudioBufferHandler;
  @property({ type: Object }) filteredPromptsController!: FilteredPromptsController;
  @property({ type: Object }) musicConfigController!: MusicConfigController;
  @property({ type: Object }) promptManager!: PromptManager;
  @property({ type: Object }) audioContext!: AudioContext;
  @property({ type: Object }) settingsPersistence!: SettingsPersistence;

  // Callback functions passed from parent
  @property({ type: Function }) setSessionPrompts!: () => Promise<void>;
  @property({ type: Function }) onSessionCreated!: (session: LiveMusicSession) => void;
  @property({ type: Function }) onPlaybackStateChange!: (state: string) => void;
  @property({ type: Function }) onAudioBufferHistoryUpdate!: (history: AudioBuffer[]) => void;

  @state() private session: LiveMusicSession | null = null;

  override connectedCallback() {
    super.connectedCallback();

    // Listen for close session event
    this.addEventListener('close-session', async () => {
      console.log('Received close-session event, closing session...');
      await this.closeSession();
      console.log('Session closed via event');
    });

    // Listen for reconnect session event
    this.addEventListener('reconnect-session', () => {
      this.handleReconnectSession();
    });
  }

  /**
   * Main method to establish connection to the music generation session
   */
  async connectToSession(): Promise<void> {
    // Reset AudioBufferHandler before new connection to clear old buffers
    if (this.audioBufferHandler) {
      console.log('SessionController: Resetting AudioBufferHandler before new connection');
      this.audioBufferHandler.reset();
    }

    if (this.connectionController.connectionState.isReconnecting && this.connectionController.connectionState.reconnectAttempts > 0) {
      // If reconnecting, apply delay before attempting to connect
      const delay = this.connectionController.getReconnectDelay();
      this.connectionController.showReconnectionStatus();
      await new Promise(resolve => setTimeout(resolve, delay));
    }

    this.onPlaybackStateChange('loading');

    try {
      this.session = await this.googleAIConfig.createLiveMusicSession({
        onmessage: async (e: LiveMusicServerMessage) => {
          console.log('Received message from the server: %s\\n');
          console.log(e);

          // Check if AudioContext is suspended and resume it
          if (this.audioContext.state === 'suspended') {
            try {
              await this.audioContext.resume();
              console.log('AudioContext resumed during message processing');
            } catch (err) {
              console.error('Error resuming AudioContext:', err);
            }
          }

          if (e.setupComplete) {
            this.connectionController.markConnectionSuccessful();
          }
          if (e.filteredPrompt) {
            // Use FilteredPromptsController to handle filtered prompts
            this.filteredPromptsController?.handleServerFilteredPrompt(e.filteredPrompt);
          }
          if (e.serverContent?.audioChunks !== undefined && e.serverContent.audioChunks.length > 0) {
            // Process all chunks concurrently to avoid blocking and improve buffer fill rate
            const promises: Promise<void>[] = [];
            for (const chunk of e.serverContent.audioChunks) {
              if (chunk?.data) {
                if ((this.audioBufferHandler as any).processAudioChunkWithMeta) {
                  promises.push((this.audioBufferHandler as any).processAudioChunkWithMeta(chunk as any));
                } else {
                  promises.push(this.audioBufferHandler.processAudioChunk(chunk.data));
                }
              }
            }
            // Don't await here; let decoding/scheduling proceed without blocking incoming messages
            Promise.allSettled(promises).then(() => {
              const audioBufferHistory = this.audioBufferHandler.getAudioBufferHistory();
              this.onAudioBufferHistoryUpdate(audioBufferHistory);
            });
          }
        },
        onerror: (e: ErrorEvent) => {
          console.error('Connection error:', e);
          this.connectionController.markConnectionFailed();
          this.handleDisconnection();
          this.statusMessage?.show('Connection Error');
        },
        onclose: async (event?: any) => {
          console.log('Connection closed.', event);
          if (event && typeof event === 'object') {
            console.log(`Close Code: ${event.code}, Reason: ${event.reason}, WasClean: ${event.wasClean}`);
          }

          // Immediately null out session and notify parent to avoid stale usage
          if (this.session) {
            this.session = null;
            this.dispatchEvent(new CustomEvent('session-closed', { bubbles: true, composed: true }));
          }

          // Check if this was a session timeout (around 10 minutes) vs actual connection failure
          const sessionDuration = this.sessionTimer.isSessionActive ? this.sessionTimer.getSessionDuration() : '';
          const isSessionTimeout = sessionDuration.includes('10 minute');

          if (isSessionTimeout) {
            console.log('Detected 10-minute session timeout');
            this.statusMessage?.show('Session Timeout - Reconnecting...');
          } else {
            this.connectionController.markConnectionFailed();
            this.statusMessage?.show('Connection Closed');
          }

          // Differentiate between user-initiated close and unexpected close
          if (this.sessionTimer.isSessionActive) {
            console.log(`Session lasted for: ${this.sessionTimer.getSessionDuration()}`);
            this.sessionTimer.resetSession();
          }

          if (this.audioBufferHandler.playbackState !== 'stopped') { // If not stopped by user, it's unexpected
            if (isSessionTimeout) {
              // Handle session timeout with immediate reconnection
              await this.handleSessionTimeout();
            } else {
              // Handle as regular disconnection with retry logic
              this.handleDisconnection();
            }
          } else {
            this.toastMessage?.show('Music session ended.');
          }
        }
      });

      // Successfully connected or reconnected
      console.log('Connection established successfully - waiting for stability...');
      this.statusMessage?.show('Connected - stabilizing...');
      this.toastMessage?.show('Connected. Stabilizing connection...');

      // CRITICAL FIX: Do NOT mark successful immediately. Wait for 5s stability period.
      // This prevents infinite loops where it connects -> closes immediately -> resets retry count -> connects...
      setTimeout(() => {
        if (this.session) {
          // console.log('Connection stabilized (5s passed). Marking as successful.');
          this.connectionController.markConnectionSuccessful();
          this.connectionController.resetConnectionState();
          this.statusMessage?.show('Connected');
        }
      }, 5000);

      if (!this.sessionTimer.isSessionActive) {
        // Only start timer on the initial connection
        this.sessionTimer.startSession();
      }
      this.statusMessage?.show('Connected');
      this.toastMessage?.show('Connected to music generation server.');

      // Update controllers with new session
      this.musicConfigController.session = this.session;
      this.promptManager.session = this.session;

      // Notify parent component
      console.log('SessionController: Notifying parent component about new session');
      this.onSessionCreated(this.session);

      // Wait a moment for the session to be fully established before sending commands
      await new Promise(resolve => setTimeout(resolve, 500));
      console.log('SessionController: Session establishment wait completed');

      // Check both current state and persisted state to determine if auto-resume should happen
      const currentPlaybackState = this.audioBufferHandler.playbackState;
      const persistedPlaybackState = this.settingsPersistence?.loadPlaybackState() || 'stopped';

      // CRITICAL FIX: Ensure session is still valid after the wait
      if (!this.session) {
        console.warn('SessionController: Session became null during establishment wait - aborting auto-resume');
        return;
      }

      // Auto-resume if either:
      // 1. Currently in loading state (reconnection scenario)
      // 2. Persisted state indicates user was listening before reload (playing/paused/loading)
      const shouldAutoResume = currentPlaybackState === 'loading' ||
        (persistedPlaybackState === 'playing' || persistedPlaybackState === 'paused' || persistedPlaybackState === 'loading');

      if (shouldAutoResume) {
        console.log('=== AUTO-RESUME TRIGGERED ===');
        console.log('Current state:', currentPlaybackState, 'Persisted state:', persistedPlaybackState);
        console.log('Reason: User was actively listening before reload, resuming playback...');
        try {
          await this.setSessionPrompts();
          // Add another small delay before starting playback
          await new Promise(resolve => setTimeout(resolve, 200));

          // Dispatch event to trigger play in parent component
          console.log('SessionController: Dispatching resume-playback event to main component');
          this.dispatchEvent(new CustomEvent('resume-playback', {
            bubbles: true,
            composed: true
          }));

          console.log('SessionController: Resume-playback event dispatched, auto-resume completed');
        } catch (error: any) {
          console.error('Error auto-resuming playback after connection:', error);
          this.toastMessage?.show('Failed to resume playback after connection. Please try manually.');
        }
      } else {
        console.log('=== NO AUTO-RESUME ===');
        console.log('Current state:', currentPlaybackState, 'Persisted state:', persistedPlaybackState);
        console.log('Reason: User was not actively listening before reload (both states are stopped)');
      }

    } catch (error: any) {
      console.error('Failed to connect to session:', error);
      this.connectionController.markConnectionFailed();
      // Avoid showing generic connect failure if a more specific one from reconnect is already up
      if (!this.connectionController.connectionState.isReconnecting || this.connectionController.connectionState.reconnectAttempts <= 1) {
        this.toastMessage?.show(`Failed to connect: ${error.message || 'Unknown error'}`);
      }
      this.handleDisconnection(); // Treat connect failure as a disconnection
    }
  }

  /**
   * Handles disconnection with retry logic
   */
  async handleDisconnection(): Promise<void> {
    // Use ConnectionController to handle the disconnection logic
    const shouldReconnect = await this.connectionController.handleDisconnection();

    // Ensure downstream components know there is no active session
    if (this.session) {
      this.session = null;
      this.dispatchEvent(new CustomEvent('session-closed', { bubbles: true, composed: true }));
    }

    if (!shouldReconnect) {
      // Dispatch event to fully stop everything
      this.dispatchEvent(new CustomEvent('stop-playback', {
        bubbles: true,
        composed: true
      }));
      this.onPlaybackStateChange('stopped');
      return;
    }

    this.onPlaybackStateChange('loading'); // Show loading state during reconnection attempt
    this.connectToSession(); // Attempt to reconnect (which includes delay)
  }

  /**
   * Handles session timeout with immediate reconnection
   */
  private async handleSessionTimeout(): Promise<void> {
    // Use ConnectionController to handle the session timeout
    const shouldReconnect = await this.connectionController.handleSessionTimeout();

    // Ensure downstream components know there is no active session
    if (this.session) {
      this.session = null;
      this.dispatchEvent(new CustomEvent('session-closed', { bubbles: true, composed: true }));
    }

    if (!shouldReconnect) {
      // Dispatch event to fully stop everything
      this.dispatchEvent(new CustomEvent('stop-playback', {
        bubbles: true,
        composed: true
      }));
      this.onPlaybackStateChange('stopped');
      return;
    }

    this.onPlaybackStateChange('loading'); // Show loading state during reconnection attempt
    this.toastMessage?.show('Session timeout detected. Reconnecting automatically...');

    // For session timeouts, reconnect immediately without delay
    await new Promise(resolve => setTimeout(resolve, 1000)); // Brief pause to ensure cleanup
    this.connectToSession(); // Attempt to reconnect
  }

  /**
   * Handles manual session reconnection from settings
   */
  async handleReconnectSession(): Promise<void> {
    this.toastMessage?.show('Attempting to reconnect to music session...');
    this.statusMessage?.show('Reconnecting...');

    // Close the current session if it exists
    if (this.session) {
      try {
        await this.session.close();
      } catch (e: any) {
        console.warn('Error closing session before reconnect:', e.message);
      }
      this.session = null;
    }

    // Reset reconnection states to ensure a fresh connection attempt
    this.connectionController.resetConnectionState();
    this.sessionTimer.resetSession(); // Reset session timer display

    // Reset AudioBufferHandler before reconnect
    if (this.audioBufferHandler) {
      console.log('SessionController: Resetting AudioBufferHandler before manual reconnect');
      this.audioBufferHandler.reset();
    }

    // Attempt to connect to a new session
    await this.connectToSession();
  }

  /**
   * Gets the current session
   */
  getSession(): LiveMusicSession | null {
    return this.session;
  }

  /**
   * Closes the current session
   */
  async closeSession(): Promise<void> {
    if (this.session) {
      try {
        await this.session.close();
      } catch (e: any) {
        console.warn('Error closing session:', e.message);
      }
      this.session = null;
    }
  }

  override async disconnectedCallback() {
    super.disconnectedCallback();

    // Clean up session when component is disconnected
    if (this.session) {
      try {
        await this.session.close();
      } catch (e: any) {
        console.warn('Error closing session during component disconnection:', e.message);
      }
      this.session = null;
    }

    // Stop the session timer
    this.sessionTimer?.stopSession();
  }

  override render() {
    // This component doesn't render visible content, it's a logic controller
    return html``;
  }
} 