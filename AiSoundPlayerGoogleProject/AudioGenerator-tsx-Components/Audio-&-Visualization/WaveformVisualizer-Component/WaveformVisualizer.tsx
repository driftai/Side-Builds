import { css, html, LitElement } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import type { AudioAnalyser } from '../AudioAnalyser-Component/AudioAnalyser.js';
import { ColorBlender } from '../../Visual-Effects/ColorBlender-Component/ColorBlender.js';
import type { VisualizationMode } from '../../Audio-Processing-Controllers/Utilities-&-Initialization/TypeDefinitions-Component/TypeDefinitions.tsx';

export interface Prompt {
  readonly promptId: string;
  text: string;
  weight: number;
  cc: number;
  color: string;
}

@customElement('waveform-visualizer')
export class WaveformVisualizer extends LitElement {
  static override styles = css`
    #waveformCanvas {
      width: 100%;
      height: 100%;
      display: block;
      cursor: pointer;
      pointer-events: all;
    }
  `;

  @property({ type: String }) visualizationMode: VisualizationMode = 'frequency';
  @property({ type: Number }) audioLevel = 0;
  @property({ type: Object }) audioAnalyser!: AudioAnalyser;
  @property({ type: Array }) frequencyHistory: Uint8Array[] = [];
  @property({ type: Array }) audioBufferHistory: AudioBuffer[] = [];
  @property({ type: Number }) lastPlaybackTime = 0;
  @property({ type: String }) playbackState: 'stopped' | 'playing' | 'loading' | 'paused' = 'stopped';
  @property({ type: Object }) audioContext!: AudioContext;
  @property({ type: Object }) prompts!: Map<string, Prompt>;

  @state() private currentPeaks: { x: number, y: number, bin: number, intensity: number }[] = [];
  @query('#waveformCanvas') private waveformCanvas!: HTMLCanvasElement;

  private readonly frequencyHistoryLength = 100;
  private colorBlender = new ColorBlender();

  override firstUpdated() {
    // Set canvas dimensions
    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());
  }

  private resizeCanvas() {
    if (!this.waveformCanvas) return;
    const rect = this.waveformCanvas.getBoundingClientRect();
    this.waveformCanvas.width = rect.width;
    this.waveformCanvas.height = rect.height;
  }

  drawWaveform() {
    const canvas = this.waveformCanvas;
    if (!canvas || !this.audioAnalyser) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear the canvas
    ctx.clearRect(0, 0, width, height);

    // Reset peaks for the current frame (used in frequency-peaks mode)
    this.currentPeaks = [];

    // Get the blended color for drawing
    this.colorBlender.prompts = this.prompts;
    const blendedColor = this.colorBlender.getBlendedActivePromptColor();
    const outlineColor = blendedColor.replace(', 0.7)', ', 0.8)'); // Slightly less transparent for outline/stroke

    if (this.visualizationMode === 'frequency') {
      this.drawFrequencyBars(ctx, width, height, blendedColor);
    } else if (this.visualizationMode === 'circle') {
      this.drawExpandingCircle(ctx, width, height, blendedColor, outlineColor);
    } else if (this.visualizationMode === 'spectrogram') {
      this.drawSpectrogram(ctx, width, height);
    } else if (this.visualizationMode === 'frequency-peaks') {
      this.drawFrequencyPeaks(ctx, width, height, blendedColor);
    } else if (this.visualizationMode === 'audio-track') {
      this.drawAudioTrack(ctx, width, height, blendedColor);
    } else { // Default Waveform mode
      this.drawWaveformMode(ctx, width, height, blendedColor, outlineColor);
    }
  }

  private drawFrequencyBars(ctx: CanvasRenderingContext2D, width: number, height: number, blendedColor: string) {
    const freqData = new Uint8Array(this.audioAnalyser.frequencyBinCount);
    this.audioAnalyser.getByteFrequencyData(freqData);

    const centerX = width / 2;
    const numSourceBins = Math.min(64, Math.floor(this.audioAnalyser.frequencyBinCount / 4));

    if (numSourceBins === 0) return;

    const spacePerBar = (width / 2) / numSourceBins;
    const barWidth = Math.max(1, spacePerBar * 0.75);
    const gap = Math.max(0, spacePerBar * 0.25);

    ctx.fillStyle = blendedColor;

    for (let i = 0; i < numSourceBins; i++) {
      const barHeight = (freqData[i] / 255) * height;

      // Draw bar on the right side
      const rightBarX = centerX + i * (barWidth + gap);
      ctx.fillRect(rightBarX, height - barHeight, barWidth, barHeight);

      // Draw mirrored bar on the left side
      const leftBarX = centerX - (i * (barWidth + gap)) - barWidth;
      ctx.fillRect(leftBarX, height - barHeight, barWidth, barHeight);
    }
  }

  private drawExpandingCircle(ctx: CanvasRenderingContext2D, width: number, height: number, blendedColor: string, outlineColor: string) {
    const centerX = width / 2;
    const centerY = height / 2;
    const maxRadius = Math.min(width, height) / 2;
    const minDisplayRadius = maxRadius * 0.1;
    const radius = minDisplayRadius + (maxRadius - minDisplayRadius) * this.audioLevel;

    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2, false);
    ctx.fillStyle = blendedColor;
    ctx.fill();

    ctx.lineWidth = 2;
    ctx.strokeStyle = outlineColor;
    ctx.stroke();
  }

  private drawSpectrogram(ctx: CanvasRenderingContext2D, width: number, height: number) {
    const historyLength = this.frequencyHistory.length;
    const barWidth = width / historyLength;
    const frequencyBinHeight = height / this.audioAnalyser.frequencyBinCount;

    for (let i = 0; i < historyLength; i++) {
      const freqData = this.frequencyHistory[i];
      const x = i * barWidth;

      for (let j = 0; j < freqData.length; j++) {
        const intensity = freqData[j];
        const color = `rgb(${intensity}, ${intensity}, ${intensity})`;

        ctx.fillStyle = color;
        const y = height - j * frequencyBinHeight - frequencyBinHeight;
        ctx.fillRect(x, y, barWidth, frequencyBinHeight);
      }
    }
  }

  private drawFrequencyPeaks(ctx: CanvasRenderingContext2D, width: number, height: number, blendedColor: string) {
    const freqData = new Uint8Array(this.audioAnalyser.frequencyBinCount);
    this.audioAnalyser.getByteFrequencyData(freqData);

    ctx.fillStyle = blendedColor.replace(', 0.7)', ')');

    const peakThreshold = 150;
    const peakNeighbors = 2;

    for (let i = peakNeighbors; i < freqData.length - peakNeighbors; i++) {
      const intensity = freqData[i];

      if (intensity > peakThreshold) {
        let isPeak = true;
        for (let j = 1; j <= peakNeighbors; j++) {
          if (intensity < freqData[i - j] || intensity < freqData[i + j]) {
            isPeak = false;
            break;
          }
        }

        if (isPeak) {
          const x = i * (width / freqData.length) + (width / freqData.length) / 2;
          const y = height - (intensity / 255) * height;
          const radius = (intensity / 255) * 5 + 2;

          ctx.beginPath();
          ctx.arc(x, y, radius, 0, Math.PI * 2, false);
          ctx.fill();

          this.currentPeaks.push({ x, y, bin: i, intensity });
        }
      }
    }
  }

  private drawAudioTrack(ctx: CanvasRenderingContext2D, width: number, height: number, blendedColor: string) {
    const audioData = this.audioBufferHistory;

    if (audioData.length === 0 || width === 0) {
      return;
    }

    const totalDuration = audioData.reduce((sum, buffer) => sum + buffer.duration, 0);
    if (totalDuration === 0) {
        return;
    }

    let timeToUseForScrolling = 0;
    if (this.playbackState === 'playing' || this.playbackState === 'loading') {
        timeToUseForScrolling = this.audioContext.currentTime;
    } else if (this.playbackState === 'paused') {
        timeToUseForScrolling = this.lastPlaybackTime;
    }

    const displayDuration = 10;
    const windowStartTimeInHistory = Math.max(0, timeToUseForScrolling - displayDuration);

    let r = 255, g = 255, b = 255, baseAlpha = 0.7;
    const colorMatch = blendedColor.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)/);
    if (colorMatch) {
      r = parseInt(colorMatch[1]);
      g = parseInt(colorMatch[2]);
      b = parseInt(colorMatch[3]);
      baseAlpha = parseFloat(colorMatch[4]);
    }
    const minVizAlpha = 0.1;
    const maxVizAlpha = baseAlpha;

    ctx.lineWidth = 1;
    let cumulativeBufferDuration = 0;

    for (let i = 0; i < width; i++) {
       const timeInWindow = (i / width) * displayDuration;
       const absoluteTimeInHistory = windowStartTimeInHistory + timeInWindow;

       if (absoluteTimeInHistory > totalDuration) {
           ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${minVizAlpha * 0.5})`;
           ctx.beginPath();
           ctx.moveTo(i, height / 2);
           ctx.lineTo(i, height / 2);
           ctx.stroke();
           continue;
       }

       let foundDataForPixel = false;
       cumulativeBufferDuration = 0;

       for (const buffer of audioData) {
          const bufferStartTimeInHistory = cumulativeBufferDuration;
          const bufferEndTimeInHistory = cumulativeBufferDuration + buffer.duration;

          if (absoluteTimeInHistory >= bufferStartTimeInHistory && absoluteTimeInHistory < bufferEndTimeInHistory) {
             const timeInCurrentBuffer = absoluteTimeInHistory - bufferStartTimeInHistory;
             const timePerPixel = displayDuration / width;
             const sampleStartIndex = Math.floor(timeInCurrentBuffer * buffer.sampleRate);
             const sampleEndIndex = Math.floor((timeInCurrentBuffer + timePerPixel) * buffer.sampleRate);

             const clampedSampleStart = Math.min(Math.max(sampleStartIndex, 0), buffer.length - 1);
             const clampedSampleEnd = Math.min(Math.max(sampleEndIndex, 0), buffer.length - 1);

             let minSample = 0;
             let maxSample = 0;

             if (clampedSampleStart <= clampedSampleEnd && clampedSampleStart < buffer.length && clampedSampleEnd < buffer.length) {
                 minSample = Infinity;
                 maxSample = -Infinity;
                 const channelData = buffer.getChannelData(0);
                 for (let j = clampedSampleStart; j <= clampedSampleEnd; j++) {
                    const sample = channelData[j];
                    minSample = Math.min(minSample, sample);
                    maxSample = Math.max(maxSample, sample);
                 }
             } else if (clampedSampleStart >= 0 && clampedSampleStart < buffer.length) {
                 const channelData = buffer.getChannelData(0);
                 const singleSample = channelData[clampedSampleStart];
                 minSample = singleSample;
                 maxSample = singleSample;
             }

             const centerY = height / 2;
             const amplitudeScale = height / 2;
             const yMaxAmplitude = centerY - maxSample * amplitudeScale;
             const yMinAmplitude = centerY - minSample * amplitudeScale;

             const normalizedI = Math.min(Math.max(i, 0), width - 1);
             const progressInWindow = (width > 1) ? (normalizedI / (width - 1)) : 1.0;
             const currentSegmentAlpha = minVizAlpha + progressInWindow * (maxVizAlpha - minVizAlpha);

             ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${currentSegmentAlpha})`;
             ctx.lineWidth = 1;

             ctx.beginPath();
             ctx.moveTo(i, yMinAmplitude);
             ctx.lineTo(i, yMaxAmplitude);
             ctx.stroke();

             foundDataForPixel = true;
             break;
          }

          cumulativeBufferDuration += buffer.duration;
       }

       if (!foundDataForPixel && absoluteTimeInHistory >= 0 && absoluteTimeInHistory <= totalDuration) {
           ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${minVizAlpha})`;
           ctx.lineWidth = 1;
           ctx.beginPath();
           ctx.moveTo(i, height / 2);
           ctx.lineTo(i, height / 2);
           ctx.stroke();
       }
    }
  }

  private drawWaveformMode(ctx: CanvasRenderingContext2D, width: number, height: number, blendedColor: string, outlineColor: string) {
    const dataArray = this.audioAnalyser.getTimeDomainData();
    const bufferLength = dataArray.length;

    ctx.fillStyle = blendedColor;
    ctx.strokeStyle = outlineColor;
    ctx.lineWidth = 2;
    ctx.beginPath();

    const sliceWidth = width * 1.0 / bufferLength;
    let x = 0;

    ctx.moveTo(0, height / 2);

    const centerY = height / 2;
    const amplitudeScale = height / 2;
    const boostFactor = 1.5;

    for(let i = 0; i < bufferLength; i++) {
      const v = dataArray[i] / 128.0;
      const deviation = v - 1.0;
      const boostedDeviation = Math.sign(deviation) * Math.pow(Math.abs(deviation), 0.7) * boostFactor;
      const y = centerY - boostedDeviation * amplitudeScale;

      ctx.lineTo(x, y);
      x += sliceWidth;
    }

    ctx.lineTo(width, height / 2);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }



  handleCanvasClick(event: MouseEvent) {
    if (this.visualizationMode !== 'frequency-peaks') {
      return;
    }

    const canvas = this.waveformCanvas;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const clickY = event.clientY - rect.top;

    const hitRadius = 10;
    let hitPeak = null;

    for (const peak of this.currentPeaks) {
      const distance = Math.sqrt(Math.pow(clickX - peak.x, 2) + Math.pow(clickY - peak.y, 2));
      const peakDrawnRadius = (peak.intensity / 255) * 5 + 2;
      if (distance <= peakDrawnRadius + hitRadius) {
        hitPeak = peak;
        break;
      }
    }

    if (hitPeak) {
      this.dispatchEvent(new CustomEvent('peak-click', {
        detail: { peak: hitPeak },
        bubbles: true,
        composed: true
      }));
    }
  }

  updateFrequencyHistory() {
    if (!this.audioAnalyser) return;

    const freqData = new Uint8Array(this.audioAnalyser.frequencyBinCount);
    this.audioAnalyser.getByteFrequencyData(freqData);
    
    this.frequencyHistory.push(freqData);
    if (this.frequencyHistory.length > this.frequencyHistoryLength) {
      this.frequencyHistory.shift();
    }
  }

  override render() {
    return html`<canvas 
      id="waveformCanvas" 
      @click=${this.handleCanvasClick}
    ></canvas>`;
  }
} 