export const PCM_SAMPLE_RATE = 24000;

export const decodeAudioChunk = (base64: string): ArrayBuffer => {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index++) {
        bytes[index] = binary.charCodeAt(index);
    }
    return bytes.buffer;
};

export const concatenateAudioChunks = (chunks: ArrayBuffer[]): Uint8Array => {
    const totalLength = chunks.reduce((total, chunk) => total + chunk.byteLength, 0);
    const combined = new Uint8Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
        combined.set(new Uint8Array(chunk), offset);
        offset += chunk.byteLength;
    }
    return combined;
};

export const createPcmAudioBuffer = (
    audioContext: AudioContext,
    chunks: ArrayBuffer[],
): AudioBuffer => {
    const combined = concatenateAudioChunks(chunks);
    const pcmData = new Int16Array(combined.buffer);
    const audioBuffer = audioContext.createBuffer(1, pcmData.length, PCM_SAMPLE_RATE);
    const channelData = audioBuffer.getChannelData(0);
    for (let index = 0; index < pcmData.length; index++) {
        channelData[index] = pcmData[index] / 32768;
    }
    return audioBuffer;
};

export const createNarrationAudioBuffer = (
    audioContext: AudioContext,
    chunks: ArrayBuffer[],
    text: string,
): AudioBuffer => {
    const audioBuffer = createPcmAudioBuffer(audioContext, chunks);
    const textLength = text.length;
    const duration = audioBuffer.duration;

    if (textLength > 10) {
        const expectedMinDuration = textLength / 25;
        if (duration < expectedMinDuration) {
            console.warn(
                `Generated audio too short: ${duration.toFixed(2)}s for ${textLength} chars `
                + `(text: "${text.substring(0, 30)}..."). Expected > ${expectedMinDuration.toFixed(2)}s.`,
            );
            let shouldReject = false;
            if (textLength <= 20) shouldReject = duration < 0.3;
            else if (textLength <= 50) shouldReject = duration < expectedMinDuration * 0.4;
            else shouldReject = duration < expectedMinDuration * 0.5 || duration < 1;

            if (shouldReject) {
                console.error(
                    `Rejecting truncated audio: ${duration.toFixed(2)}s for ${textLength} chars `
                    + `(text: "${text.substring(0, 50)}...")`,
                );
                throw new Error(
                    `Generated audio is too short (${duration.toFixed(2)}s) `
                    + `for text length (${textLength} chars)`,
                );
            }
        }
    }

    console.log(`Audio buffer created: ${audioBuffer.duration.toFixed(2)}s`);
    return audioBuffer;
};
