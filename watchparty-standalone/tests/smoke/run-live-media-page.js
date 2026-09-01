import { spawnSync } from 'node:child_process';

if (!process.env.LIVE_MEDIA_PAGE_URL) {
  console.error('Set LIVE_MEDIA_PAGE_URL to a public watch-page URL before running the live media-page smoke.');
  process.exit(2);
}

const command = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const result = spawnSync(command, ['playwright', 'test', 'tests/smoke/browser/media-page-live.spec.js'], {
  stdio: 'inherit',
  env: { ...process.env },
  shell: process.platform === 'win32',
  windowsHide: false
});

if (result.error) {
  console.error(`Failed to start Playwright: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
