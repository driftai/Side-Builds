/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { AudioLogEntry } from '../types';

export type AudioLogTabViewProps = {
  handleSaveAudioLog: () => void;
  audioLog: AudioLogEntry[];
  getAudioDuration: (blob: Blob) => string;
  toggleAudioPlayback: (index: number, blob: Blob) => void;
  playingAudioIndex: number | null;
};

export function AudioLogTabView({
  handleSaveAudioLog,
  audioLog,
  getAudioDuration,
  toggleAudioPlayback,
  playingAudioIndex,
}: AudioLogTabViewProps) {
  return (
    <div className="audio-log-view">
      <div className="audio-log-controls">
        <button onClick={handleSaveAudioLog} disabled={audioLog.length === 0}>
          Save Audio Log
        </button>
      </div>
      <div className="audio-log-content">
        <div className="audio-log-header">
          <div>Timestamp</div>
          <div>Speaker</div>
          <div>Duration</div>
          <div className="audio-log-playback">Playback</div>
        </div>
        {audioLog.length > 0 ? (
          audioLog.map((entry, index) => (
            <div key={index} className="audio-log-entry">
              <div>{entry.timestamp.toLocaleTimeString()}</div>
              <div>{entry.speaker}</div>
              <div>{getAudioDuration(entry.blob)}</div>
              <div className="audio-log-playback">
                <button
                  className="play-audio-button"
                  onClick={() => toggleAudioPlayback(index, entry.blob)}
                >
                  <span className="icon">
                    {playingAudioIndex === index ? 'pause_circle' : 'play_circle'}
                  </span>
                </button>
              </div>
            </div>
          ))
        ) : (
          <div className="audio-log-empty">
            <p>No audio has been recorded in this session yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}
