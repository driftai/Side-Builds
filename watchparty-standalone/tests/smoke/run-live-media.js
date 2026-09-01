import { spawnSync } from 'node:child_process';

if (!process.env.LIVE_MEDIA_URL) {
  console.error('Set LIVE_MEDIA_URL to a direct .m3u8 or media URL before running the live media smoke.');
  process.exit(2);
}

const command = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const result = spawnSync(command, ['playwright', 'test', 'tests/smoke/browser/media-live.spec.js'], {
  stdio: 'inherit',
  env: { ...process.env, LIVE_MEDIA_URL: process.env.LIVE_MEDIA_URL },
  shell: process.platform === 'win32',
  windowsHide: false
});

if (result.error) {
  console.error(`Failed to start Playwright: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
