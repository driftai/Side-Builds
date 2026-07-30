import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

@customElement('session-timer')
export class SessionTimer extends LitElement {
  @state() private sessionStartTime: number | null = null;
  @state() private _sessionDurationDisplay: string = '00:00';
  @state() private currentSessionDurationDisplayIntervalId: number | null = null;

  // Start the session timer
  startSession() {
    if (!this.sessionStartTime) {
      this.sessionStartTime = Date.now();
    }
    
    // Clear any existing interval
    if (this.currentSessionDurationDisplayIntervalId) {
      clearInterval(this.currentSessionDurationDisplayIntervalId);
      this.currentSessionDurationDisplayIntervalId = null;
    }

    // Start new interval to update display every second
    this.currentSessionDurationDisplayIntervalId = window.setInterval(() => {
      if (this.sessionStartTime) {
        const currentDurationMs = Date.now() - this.sessionStartTime;
        const totalMinutes = Math.floor(currentDurationMs / (1000 * 60));
        const totalSeconds = Math.floor(currentDurationMs / 1000);
        const displaySeconds = totalSeconds % 60;
        
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        const formattedMinutes = minutes.toString().padStart(2, '0');
        const formattedSeconds = displaySeconds.toString().padStart(2, '0');
        
        // Use MM:SS format for shorter sessions, HH:MM:SS for longer sessions
        if (hours > 0) {
          const formattedHours = hours.toString().padStart(2, '0');
          this._sessionDurationDisplay = `${formattedHours}:${formattedMinutes}:${formattedSeconds}`;
        } else {
          this._sessionDurationDisplay = `${formattedMinutes}:${formattedSeconds}`;
        }
        
        console.log(`Current session uptime: ${this.sessionDurationDisplay}`);
        
        // Trigger update for reactive properties
        this.requestUpdate();
        
        // Dispatch session duration update event to notify parent components
        this.dispatchEvent(new CustomEvent('session-duration-updated', {
          detail: this._sessionDurationDisplay,
          bubbles: true,
          composed: true
        }));
      }
    }, 1000);
  }

  // Stop the session timer
  stopSession() {
    if (this.currentSessionDurationDisplayIntervalId) {
      clearInterval(this.currentSessionDurationDisplayIntervalId);
      this.currentSessionDurationDisplayIntervalId = null;
    }
    this._sessionDurationDisplay = '00:00';
  }

  // Reset the session timer
  resetSession() {
    this.stopSession();
    this.sessionStartTime = null;
  }

  // Get session duration for external use
  getSessionDuration(): string {
    if (this.sessionStartTime) {
      const durationMs = Date.now() - this.sessionStartTime;
      const seconds = Math.floor((durationMs / 1000) % 60);
      const minutes = Math.floor((durationMs / (1000 * 60)) % 60);
      const hours = Math.floor((durationMs / (1000 * 60 * 60)) % 24);
      
      let durationString = '';
      if (hours > 0) durationString += `${hours} hour(s) `;
      if (minutes > 0) durationString += `${minutes} minute(s) `;
      durationString += `${seconds} second(s)`;
      
      return durationString.trim();
    }
    return '0 seconds';
  }

  // Get current session duration display
  get sessionDurationDisplay(): string {
    return this._sessionDurationDisplay;
  }

  // Check if session is active
  get isSessionActive(): boolean {
    return this.sessionStartTime !== null;
  }

  override disconnectedCallback() {
    super.disconnectedCallback();
    this.stopSession();
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 