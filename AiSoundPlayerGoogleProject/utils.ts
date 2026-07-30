/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/

import {Blob} from '@google/genai';

function encode(bytes) {
  let binary = '';
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function decode(base64) {
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

function createBlob(data: Float32Array): Blob {
  const l = data.length;
  const int16 = new Int16Array(l);
  for (let i = 0; i < l; i++) {
    // convert float32 -1 to 1 to int16 -32768 to 32767
    int16[i] = data[i] * 32768;
  }

  return {
    data: encode(new Uint8Array(int16.buffer)),
    mimeType: 'audio/pcm;rate=16000',
  };
}

async function decodeAudioData(
  data: Uint8Array,
  ctx: AudioContext,
  sampleRate: number,
  numChannels: number,
): Promise<AudioBuffer> {
  const channels = Math.max(1, numChannels);
  const totalFrames = Math.floor((data.length / 2) / channels);
  const buffer = ctx.createBuffer(channels, totalFrames, sampleRate);

  const dataInt16 = new Int16Array(data.buffer, data.byteOffset, data.byteLength / 2);
  const totalSamples = dataInt16.length;

  // Convert to float32 in-place style and deinterleave directly into channel buffers
  for (let ch = 0; ch < channels; ch++) {
    const channelData = buffer.getChannelData(ch);
    let writeIndex = 0;
    for (let readIndex = ch; readIndex < totalSamples; readIndex += channels) {
      channelData[writeIndex++] = dataInt16[readIndex] / 32768.0;
    }
  }

  return buffer;
}

export {createBlob, decode, decodeAudioData, encode};
