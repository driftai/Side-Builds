/** Simple class for getting the current level from our audio element. */
export class AudioAnalyser {
  readonly node: AnalyserNode;
  private readonly freqData: Uint8Array;
  constructor(context: AudioContext) {
    this.node = context.createAnalyser();
    // Adjusted smoothingTimeConstant for potentially less erratic waveform
    this.node.smoothingTimeConstant = 0.6;
    this.freqData = new Uint8Array(this.node.frequencyBinCount);
  }
  getCurrentLevel() {
    this.node.getByteFrequencyData(this.freqData);
    const avg = this.freqData.reduce((a, b) => a + b, 0) / this.freqData.length;
    return avg / 0xff;
  }
  getTimeDomainData() {
    const dataArray = new Uint8Array(this.node.frequencyBinCount);
    this.node.getByteTimeDomainData(dataArray);
    return dataArray;
  }
  getByteFrequencyData(data: Uint8Array) {
    this.node.getByteFrequencyData(data);
  }
  get frequencyBinCount(): number {
    return this.node.frequencyBinCount;
  }
} 