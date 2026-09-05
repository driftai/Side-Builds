import assert from 'node:assert/strict';
import {
  DEFAULT_YOUTUBE_QUALITY,
  buildYoutubeStrategies,
  getYoutubeQualityProfiles,
  normalizeYoutubeQuality
} from '../youtube-import.js';

assert.equal(DEFAULT_YOUTUBE_QUALITY, '1080');
assert.equal(normalizeYoutubeQuality('1080'), '1080');
assert.equal(normalizeYoutubeQuality('bogus'), '1080');
assert.equal(getYoutubeQualityProfiles().length, 5);

const noFfmpeg = buildYoutubeStrategies('1080');
assert.equal(noFfmpeg.length, 1);
assert.equal(noFfmpeg[0].name, 'combined-stream');
assert.match(noFfmpeg[0].format, /height<=1080/);

const withFfmpeg = buildYoutubeStrategies('1080', { ffmpegCommand: 'ffmpeg' });
assert.equal(withFfmpeg[0].name, 'adaptive-merge');
assert.match(withFfmpeg[0].format, /bestvideo\[height<=1080\]/);
assert.deepEqual(withFfmpeg[0].extraArgs.slice(0, 2), ['--merge-output-format', 'mp4']);

const fourK = buildYoutubeStrategies('2160', { ffmpegCommand: 'ffmpeg' });
assert.match(fourK[0].format, /height<=2160/);

const sourceMax = buildYoutubeStrategies('max', { ffmpegCommand: 'ffmpeg' });
assert.doesNotMatch(sourceMax[0].format, /height<=/);

console.log('VoxelVision YouTube quality smoke: PASS');
