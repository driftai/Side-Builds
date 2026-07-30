// Lightweight PCM16 base64 decode and deinterleave in a Web Worker

type DecodeRequest = {
  id: number;
  base64: string;
  sampleRate: number;
  channels: number; // 1 or 2
};

type DecodeResponse = {
  id: number;
  sampleRate: number;
  channels: number;
  lengthFrames: number;
  // One ArrayBuffer per channel containing Float32 samples
  channelBuffers: ArrayBuffer[];
};

// Efficient base64 decode to Uint8Array
function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

self.onmessage = (ev: MessageEvent<DecodeRequest>) => {
  const { id, base64, sampleRate, channels } = ev.data;
  try {
    const bytes = base64ToBytes(base64);
    const dataInt16 = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2);
    const totalSamples = dataInt16.length;
    const ch = Math.max(1, Math.min(2, channels | 0));
    const frames = Math.floor(totalSamples / ch);

    const channelBuffers: ArrayBuffer[] = [];
    for (let c = 0; c < ch; c++) {
      const f32 = new Float32Array(frames);
      let w = 0;
      for (let r = c; r < totalSamples; r += ch) {
        f32[w++] = dataInt16[r] / 32768.0;
      }
      channelBuffers.push(f32.buffer);
    }

    const resp: DecodeResponse = {
      id,
      sampleRate,
      channels: ch,
      lengthFrames: frames,
      channelBuffers,
    };
    // Transfer Float32Array buffers to avoid copying back to main thread
    (self as unknown as Worker).postMessage(resp, channelBuffers);
  } catch (err) {
    (self as unknown as Worker).postMessage({ id, error: String(err) });
  }
};

