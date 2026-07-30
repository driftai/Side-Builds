import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

interface ToastMessage {
  show(message: string): void;
}

@customElement('recording-controller')
export class RecordingController extends LitElement {
  @property({ type: Object }) audioContext!: AudioContext;
  @property({ type: Object }) outputNode!: GainNode;
  @property({ type: Object }) toastMessage!: ToastMessage;

  @state() isRecording: boolean = false;
  @state() recordedAudioUrl: string | null = null;

  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];

  // Start audio recording
  async startRecording() {
    if (!this.audioContext) {
      this.toastMessage.show('Audio context not available for recording.');
      return;
    }

    // Ensure AudioContext is running
    if (this.audioContext.state === 'suspended') {
      try {
        await this.audioContext.resume();
        console.log('AudioContext resumed for recording.');
      } catch (err: any) {
        console.error('Error resuming AudioContext for recording:', err);
        this.toastMessage.show('Could not start recording: audio context failed to resume.');
        return;
      }
    }

    this.audioChunks = [];
    this.recordedAudioUrl = null;
    const destination = this.audioContext.createMediaStreamDestination();
    this.outputNode.connect(destination);

    // Check for supported MIME types
    const mimeTypes = ['audio/wav', 'audio/webm', 'audio/ogg', 'audio/mp4'];
    let supportedMimeType = null;
    for (const type of mimeTypes) {
      if (MediaRecorder.isTypeSupported(type)) {
        supportedMimeType = type;
        break;
      }
    }

    if (!supportedMimeType) {
      this.toastMessage.show('No supported audio recording format found.');
      this.outputNode.disconnect(destination);
      return;
    }

    try {
      this.mediaRecorder = new MediaRecorder(destination.stream, { mimeType: supportedMimeType });

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        const audioBlob = new Blob(this.audioChunks, { type: supportedMimeType });
        this.recordedAudioUrl = URL.createObjectURL(audioBlob);
        this.toastMessage.show('Recording stopped. Download available.');
        this.dispatchEvent(new CustomEvent('recording-stopped', { 
          detail: { audioUrl: this.recordedAudioUrl },
          bubbles: true,
          composed: true 
        }));
      };

      this.mediaRecorder.start();
      this.isRecording = true;
      this.toastMessage.show(`Recording started (${supportedMimeType})...`);
      this.dispatchEvent(new CustomEvent('recording-started', { 
        bubbles: true,
        composed: true 
      }));
    } catch (error: any) {
      console.error('Error starting recording:', error);
      this.toastMessage.show(`Error starting recording: ${error.message}`);
      if (destination) {
        this.outputNode.disconnect(destination);
      }
    }
  }

  // Stop audio recording
  stopRecording() {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
    this.isRecording = false;
    this.toastMessage.show('Stopping recording...');
  }

  // Get current recording state
  get recordingState() {
    return {
      isRecording: this.isRecording,
      recordedAudioUrl: this.recordedAudioUrl
    };
  }

  // Reset recording state
  resetRecording() {
    this.isRecording = false;
    this.recordedAudioUrl = null;
    this.audioChunks = [];
    if (this.mediaRecorder) {
      this.mediaRecorder = null;
    }
  }

  override render() {
    // This component doesn't render UI directly, it's a controller
    return null;
  }
} 