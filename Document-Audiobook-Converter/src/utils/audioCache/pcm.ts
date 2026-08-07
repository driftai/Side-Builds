/** AudioBuffer (float) to the 16-bit PCM the server originally sent. */
export const audioBufferToPcm16 = (buffer: AudioBuffer): ArrayBuffer => {
    const channel = buffer.getChannelData(0);
    const out = new Int16Array(channel.length);
    for (let i = 0; i < channel.length; i++) {
        const clamped = Math.max(-1, Math.min(1, channel[i]));
        out[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    }
    return out.buffer;
};

/** 16-bit PCM to a playable AudioBuffer. */
export const pcm16ToAudioBuffer = (
    pcm: ArrayBuffer, sampleRate: number, context: BaseAudioContext,
): AudioBuffer => {
    const samples = new Int16Array(pcm);
    const buffer = context.createBuffer(1, samples.length, sampleRate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 32768;
    return buffer;
};
