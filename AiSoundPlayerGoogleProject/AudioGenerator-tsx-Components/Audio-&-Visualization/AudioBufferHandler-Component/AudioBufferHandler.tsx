import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { decode, decodeAudioData } from '../../../utils.ts';

type PlaybackState = 'stopped' | 'playing' | 'loading' | 'paused';

interface StatusMessage {
  show(message: string): void;
}

interface BufferHealth {
  bufferedSeconds: number;
  scheduledBuffers: number;
  isHealthy: boolean;
  status: 'healthy' | 'low' | 'critical' | 'empty';
}

@customElement('audio-buffer-handler')
export class AudioBufferHandler extends LitElement {
  @property({ type: Object }) audioContext!: AudioContext;
  @property({ type: Object }) outputNode!: GainNode;
  @property({ type: String }) playbackState: PlaybackState = 'stopped';
  @property({ type: Object }) statusMessage!: StatusMessage;

  private nextStartTime = 0;
  private pendingBuffers: AudioBuffer[] = [];
  private scheduledSources: { source: AudioBufferSourceNode; endTime: number }[] = [];
  private isScheduling = false;

  // === CONFIGURABLE CONSTANTS ===
  // Default sample rate for Gemini audio output
  private readonly DEFAULT_SAMPLE_RATE = 24000;

  // Scheduling lookahead - how far ahead to schedule buffers (seconds)
  private readonly SCHEDULE_LOOKAHEAD = 0.2;



  // Initial buffer time on underrun recovery (seconds)
  private readonly UNDERRUN_RECOVERY_BUFFER = 0.5;

  // Fade-in duration after underrun recovery (seconds)
  private readonly RECOVERY_FADE_IN = 0.05;

  // Buffer health thresholds (seconds)
  private readonly BUFFER_HEALTHY_THRESHOLD = 0.5;
  private readonly BUFFER_LOW_THRESHOLD = 0.2;

  /**
   * Processes incoming audio chunk data (base64)
   * Falls back to default sample rate if not specified
   */
  async processAudioChunk(audioChunkData: string): Promise<void> {
    if (this.playbackState === 'stopped') return;
    await this.handleDecode(audioChunkData, this.DEFAULT_SAMPLE_RATE, 1);
  }

  /**
   * Processes audio chunk with metadata (preserving rate/channels)
   */
  async processAudioChunkWithMeta(chunk: { data: string; mimeType?: string; sampleRate?: number; channels?: number }): Promise<void> {
    if (!chunk || !chunk.data) return;
    if (this.playbackState === 'stopped') return;

    let sampleRate = this.DEFAULT_SAMPLE_RATE;
    let channels = 1;

    // Try to derive format from mimeType or properties
    if (chunk.mimeType) {
      const rateMatch = chunk.mimeType.match(/rate=([0-9]+)/);
      if (rateMatch) {
        sampleRate = parseInt(rateMatch[1], 10);
      }
      const chMatch = chunk.mimeType.match(/channels=([0-9]+)/);
      if (chMatch) {
        channels = parseInt(chMatch[1], 10);
      }
    }

    // Explicit overrides
    if (typeof chunk.sampleRate === 'number') sampleRate = chunk.sampleRate;
    if (typeof chunk.channels === 'number') channels = chunk.channels;

    await this.handleDecode(chunk.data, sampleRate, channels);
  }

  private async handleDecode(base64: string, sampleRate: number, channels: number) {
    try {
      // Warn if sample rate mismatch (can cause resampling artifacts)
      if (this.audioContext && sampleRate !== this.audioContext.sampleRate) {
        // Only warn once per session to avoid spam
        if (!this._hasWarnedSampleRate) {
          console.warn(
            `AudioBufferHandler: Sample rate mismatch - incoming: ${sampleRate}Hz, context: ${this.audioContext.sampleRate}Hz. ` +
            `This may cause resampling artifacts.`
          );
          this._hasWarnedSampleRate = true;
        }
      }

      // Decode base64 to bytes
      const bytes = decode(base64);

      // Decode audio data using our utility wrapper
      const audioBuffer = await decodeAudioData(
        bytes,
        this.audioContext,
        sampleRate,
        channels
      );

      this.pendingBuffers.push(audioBuffer);
      this.scheduleBuffers();
    } catch (e) {
      console.error('AudioBufferHandler: Error decoding chunk', e);
    }
  }

  private _hasWarnedSampleRate = false;

  private scheduleBuffers() {
    if (this.isScheduling) return;
    this.isScheduling = true;

    try {
      const currentTime = this.audioContext.currentTime;

      // Clean up finished sources from tracking array
      this.cleanupFinishedSources(currentTime);

      // Detect underrun: next scheduled time is in the past
      const isUnderrun = this.nextStartTime < currentTime;

      if (isUnderrun && this.nextStartTime > 0) {
        // We fell behind - recover gracefully
        console.warn(`AudioBufferHandler: Buffer underrun detected, recovering...`);
        this.nextStartTime = currentTime + this.UNDERRUN_RECOVERY_BUFFER;
      } else if (this.nextStartTime === 0) {
        // First chunk - start with lookahead
        this.nextStartTime = currentTime + this.SCHEDULE_LOOKAHEAD;

        // Transition from loading to playing now that we have data
        if (this.playbackState === 'loading') {
          console.log('AudioBufferHandler: First buffer received, transitioning to playing');
          this.dispatchEvent(new CustomEvent('playback-state-change', {
            detail: 'playing',
            bubbles: true,
            composed: true
          }));
        }
      }

      while (this.pendingBuffers.length > 0) {
        const buffer = this.pendingBuffers.shift()!;

        // Create source node
        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;

        // Apply fade-in if recovering from underrun
        if (isUnderrun && this.scheduledSources.length === 0) {
          // Create a gain node for fade-in
          const fadeGain = this.audioContext.createGain();
          fadeGain.gain.setValueAtTime(0, this.nextStartTime);
          fadeGain.gain.linearRampToValueAtTime(1, this.nextStartTime + this.RECOVERY_FADE_IN);

          source.connect(fadeGain);
          fadeGain.connect(this.outputNode);
        } else {
          // Normal connection
          source.connect(this.outputNode);
        }

        // Schedule playback
        source.start(this.nextStartTime);

        // Track this source for buffer health monitoring
        const endTime = this.nextStartTime + buffer.duration;
        this.scheduledSources.push({ source, endTime });

        // Advance expected start time for next chunk
        this.nextStartTime += buffer.duration;
      }
    } catch (e) {
      console.error('AudioBufferHandler: Scheduling error', e);
    } finally {
      this.isScheduling = false;
    }
  }

  /**
   * Remove finished sources from tracking array
   */
  private cleanupFinishedSources(currentTime: number) {
    this.scheduledSources = this.scheduledSources.filter(s => s.endTime > currentTime);
  }

  /**
   * Get current buffer health status
   * Useful for UI indicators or adaptive quality
   */
  getBufferHealth(): BufferHealth {
    const currentTime = this.audioContext?.currentTime || 0;
    this.cleanupFinishedSources(currentTime);

    // Calculate total buffered time
    let bufferedSeconds = 0;
    for (const s of this.scheduledSources) {
      const remaining = s.endTime - currentTime;
      if (remaining > 0) {
        bufferedSeconds += remaining;
      }
    }

    // Add pending buffers duration
    for (const buffer of this.pendingBuffers) {
      bufferedSeconds += buffer.duration;
    }

    // Determine health status
    let status: BufferHealth['status'];
    let isHealthy: boolean;

    if (bufferedSeconds >= this.BUFFER_HEALTHY_THRESHOLD) {
      status = 'healthy';
      isHealthy = true;
    } else if (bufferedSeconds >= this.BUFFER_LOW_THRESHOLD) {
      status = 'low';
      isHealthy = true;
    } else if (bufferedSeconds > 0) {
      status = 'critical';
      isHealthy = false;
    } else {
      status = 'empty';
      isHealthy = false;
    }

    return {
      bufferedSeconds,
      scheduledBuffers: this.scheduledSources.length + this.pendingBuffers.length,
      isHealthy,
      status
    };
  }

  reset() {
    // Stop all scheduled sources
    for (const s of this.scheduledSources) {
      try {
        s.source.stop();
      } catch (e) {
        // Ignore errors from already stopped sources
      }
    }

    this.pendingBuffers = [];
    this.scheduledSources = [];
    this.nextStartTime = 0;
    this.isScheduling = false;
    this._hasWarnedSampleRate = false;
    console.log('AudioBufferHandler: Reset completed');
  }

  // Visualization helper (optional, keeps interface compatible)
  getAudioBufferHistory(): AudioBuffer[] {
    return []; // Simplified version doesn't track history to save memory
  }

  override render() {
    return null;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'audio-buffer-handler': AudioBufferHandler;
  }
}