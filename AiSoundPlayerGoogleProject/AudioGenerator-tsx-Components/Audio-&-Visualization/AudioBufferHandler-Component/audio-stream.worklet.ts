class PcmStreamerProcessor extends AudioWorkletProcessor {
  private queue: { channels: Float32Array[]; offset: number }[] = [];
  private framesQueued: number = 0;
  private channels: number;

  constructor(options: any) {
    super();
    this.channels = (options?.outputChannelCount && options.outputChannelCount[0]) || 1;
    this.port.onmessage = (ev: MessageEvent) => {
      const data = ev.data;
      if (data && data.type === 'append') {
        const chCount = Math.min(this.channels, Array.isArray(data.channelBuffers) ? data.channelBuffers.length : 1);
        const channels: Float32Array[] = [];
        for (let c = 0; c < chCount; c++) {
          const buf = new Float32Array(data.channelBuffers[c]);
          channels.push(buf);
        }
        this.queue.push({ channels, offset: 0 });
        this.framesQueued += channels[0]?.length || 0;
      } else if (data && data.type === 'clear') {
        this.queue = [];
        this.framesQueued = 0;
      }
    };
  }

  process(_inputs: Float32Array[][], outputs: Float32Array[][]): boolean {
    const output = outputs[0];
    const frames = output[0]?.length || 128;
    // Clear outputs first
    for (let c = 0; c < output.length; c++) {
      const channel = output[c];
      for (let i = 0; i < frames; i++) channel[i] = 0;
    }

    let remaining = frames;
    while (remaining > 0 && this.queue.length > 0) {
      const head = this.queue[0];
      const available = (head.channels[0]?.length || 0) - head.offset;
      if (available <= 0) {
        this.queue.shift();
        continue;
      }
      const toCopy = Math.min(available, remaining);
      const start = head.offset;
      const end = start + toCopy;
      for (let c = 0; c < output.length; c++) {
        const outCh = output[c];
        const src = head.channels[Math.min(c, head.channels.length - 1)];
        outCh.set(src.subarray(start, end), frames - remaining);
      }
      head.offset += toCopy;
      remaining -= toCopy;
      this.framesQueued -= toCopy;
      if (head.offset >= (head.channels[0]?.length || 0)) {
        this.queue.shift();
      }
    }

    return true;
  }
}

registerProcessor('pcm-streamer', PcmStreamerProcessor as unknown as typeof AudioWorkletProcessor);

