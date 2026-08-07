import { afterEach, describe, expect, it, vi } from 'vitest';
import {
    concatenateAudioChunks,
    createNarrationAudioBuffer,
    createPcmAudioBuffer,
    decodeAudioChunk,
} from '../src/services/gemini/liveAudio';

class FakeAudioContext {
    createBuffer(_channels: number, length: number, sampleRate: number) {
        const channel = new Float32Array(length);
        return {
            duration: length / sampleRate,
            getChannelData: () => channel,
        };
    }
}

afterEach(() => vi.restoreAllMocks());

describe('Gemini Live PCM helpers', () => {
    it('decodes and concatenates base64 chunks without changing byte order', () => {
        const first = decodeAudioChunk('AQI=');
        const second = decodeAudioChunk('AwQ=');
        expect([...concatenateAudioChunks([first, second])]).toEqual([1, 2, 3, 4]);
    });

    it('converts signed PCM16 samples to Web Audio float samples', () => {
        const pcm = new Int16Array([-32768, 0, 16384, 32767]);
        const buffer = createPcmAudioBuffer(
            new FakeAudioContext() as unknown as AudioContext,
            [pcm.buffer],
        );
        const samples = [...buffer.getChannelData(0)];
        expect(samples[0]).toBe(-1);
        expect(samples[1]).toBe(0);
        expect(samples[2]).toBe(0.5);
        expect(samples[3]).toBeCloseTo(32767 / 32768, 6);
    });

    it('retains the narration truncation guard', () => {
        vi.spyOn(console, 'warn').mockImplementation(() => { });
        vi.spyOn(console, 'error').mockImplementation(() => { });
        const veryShort = new Int16Array(100).buffer;
        expect(() => createNarrationAudioBuffer(
            new FakeAudioContext() as unknown as AudioContext,
            [veryShort],
            'This passage is intentionally much too long for the supplied audio buffer.',
        )).toThrow('Generated audio is too short');
    });
});
