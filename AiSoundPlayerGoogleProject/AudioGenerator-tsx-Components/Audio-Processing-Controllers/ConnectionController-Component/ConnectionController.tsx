import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

interface ToastMessage {
  show(message: string): void;
}

interface StatusMessage {
  show(message: string, duration?: number): void;
}

interface LiveMusicSession {
  close(): Promise<void>;
}

@customElement('connection-controller')
export class ConnectionController extends LitElement {
  @property({ type: Object }) toastMessage!: ToastMessage;
  @property({ type: Object }) statusMessage!: StatusMessage;
  @property({ type: Object }) session: LiveMusicSession | null = null;

  @state() connectionError = true;
  @state() isReconnecting = false;
  @state() reconnectAttempts = 0;

  private readonly MAX_RECONNECT_ATTEMPTS = 5;
  private readonly RECONNECT_DELAY_BASE_MS = 2000;

  /**
   * Handles disconnection and initiates reconnection process
   */
  async handleDisconnection(): Promise<boolean> {
    if (this.isReconnecting && this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
      if (this.toastMessage) {
        this.toastMessage.show('Failed to reconnect after multiple attempts. Please try again manually.');
      }
      this.stopReconnectionProcess();
      if (this.statusMessage) {
        this.statusMessage.show('Connection Failed. Stopped.');
      }
      return false;
    }

    if (!this.isReconnecting) {
      this.isReconnecting = true;
      if (this.statusMessage) {
        this.statusMessage.show('Connection lost. Attempting to reconnect...');
      }
    }
    
    this.reconnectAttempts++;
    
    // Clean up existing session before trying to reconnect
    if (this.session) {
        try {
            await this.session.close();
        } catch (closeError: any) {
            console.warn('Error closing session during reconnect attempt:', closeError.message);
        }
        this.session = null;
    }
    
    return true; // Indicates that reconnection should be attempted
  }

  /**
   * Handles expected session timeouts (e.g., 10-minute limit) differently from connection failures
   */
  async handleSessionTimeout(): Promise<boolean> {
    console.log('Handling session timeout (expected disconnection)');
    
    // Don't treat session timeouts as connection failures
    this.isReconnecting = true;
    this.reconnectAttempts = 0; // Reset attempts for session timeouts
    
    if (this.statusMessage) {
      this.statusMessage.show('Session timeout. Reconnecting...');
    }
    
    // Clean up existing session
    if (this.session) {
        try {
            await this.session.close();
        } catch (closeError: any) {
            console.warn('Error closing session during timeout reconnect:', closeError.message);
        }
        this.session = null;
    }
    
    return true; // Always attempt reconnection for session timeouts
  }

  /**
   * Gets the delay for the next reconnection attempt
   */
  getReconnectDelay(): number {
    return this.RECONNECT_DELAY_BASE_MS * Math.pow(2, this.reconnectAttempts - 1);
  }

  /**
   * Shows reconnection status message
   */
  showReconnectionStatus() {
    if (this.isReconnecting && this.reconnectAttempts > 0) {
      const delay = this.getReconnectDelay();
      const message = `Connection lost. Retrying in ${delay / 1000}s... (Attempt ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS})`;
      if (this.toastMessage) {
        this.toastMessage.show(message);
      }
      if (this.statusMessage) {
        this.statusMessage.show(message);
      }
    }
  }

  /**
   * Marks connection as successful and resets reconnection state
   */
  markConnectionSuccessful() {
    this.connectionError = false;
    this.isReconnecting = false;
    this.reconnectAttempts = 0;
    if (this.statusMessage) {
      this.statusMessage.show('Connected');
    }
    if (this.toastMessage) {
      this.toastMessage.show('Connected to music generation server.');
    }
  }

  /**
   * Marks connection as failed
   */
  markConnectionFailed(error?: string) {
    this.connectionError = true;
    if (!this.isReconnecting || this.reconnectAttempts <= 1) {
      if (this.toastMessage) {
        this.toastMessage.show(`Failed to connect: ${error || 'Unknown error'}`);
      }
    }
  }

  /**
   * Stops the reconnection process and resets state
   */
  stopReconnectionProcess() {
    this.isReconnecting = false;
    this.reconnectAttempts = 0;
  }

  /**
   * Resets all connection state
   */
  resetConnectionState() {
    this.connectionError = true;
    this.isReconnecting = false;
    this.reconnectAttempts = 0;
    this.session = null;
  }

  /**
   * Gets current connection state
   */
  get connectionState() {
    return {
      connectionError: this.connectionError,
      isReconnecting: this.isReconnecting,
      reconnectAttempts: this.reconnectAttempts,
      maxReconnectAttempts: this.MAX_RECONNECT_ATTEMPTS,
      hasSession: this.session !== null
    };
  }

  /**
   * Checks if should attempt reconnection
   */
  get shouldAttemptReconnection(): boolean {
    return this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS;
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 