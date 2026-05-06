/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React from 'react';
import { AudioLogEntry } from '../types';
import { encodeWAV } from '../utils/audio';

type PlayingAudio = {
  index: number;
  element: HTMLAudioElement;
  url: string;
} | null;

type UseAudioLogActionsArgs = {
  audioLog: AudioLogEntry[];
  playingAudio: PlayingAudio;
  setPlayingAudio: React.Dispatch<React.SetStateAction<PlayingAudio>>;
};

export function useAudioLogActions({
  audioLog,
  playingAudio,
  setPlayingAudio,
}: UseAudioLogActionsArgs) {
  const toggleAudioPlayback = (index: number, blob: Blob) => {
    if (playingAudio && playingAudio.index === index) {
      playingAudio.element.pause();
      URL.revokeObjectURL(playingAudio.url);
      setPlayingAudio(null);
    } else {
      if (playingAudio) {
        playingAudio.element.pause();
        URL.revokeObjectURL(playingAudio.url);
      }
      const url = URL.createObjectURL(encodeWAV(blob as any, 24000));
      const audio = new Audio(url);
      audio.onended = () => setPlayingAudio(null);
      audio.play();
      setPlayingAudio({ index, element: audio, url });
    }
  };

  const handleSaveAudioLog = async () => {
    const blobs = audioLog.map(entry => entry.blob);
    const combinedBlob = new Blob(blobs);
    const arrayBuffer = await combinedBlob.arrayBuffer();
    const wavBlob = encodeWAV(arrayBuffer, 24000);
    const url = URL.createObjectURL(wavBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `scribe_audio_log_${new Date().toISOString()}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return {
    handleSaveAudioLog,
    toggleAudioPlayback,
  };
}
