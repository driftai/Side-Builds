import { spawnSync } from 'node:child_process';

const command = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const result = spawnSync(command, ['playwright', 'test', 'tests/smoke/browser/media-live.spec.js', '-g', 'Browser HLS certification fixture'], {
  stdio: 'inherit',
  env: { ...process.env, RUN_HLS_FIXTURE: '1' },
  shell: process.platform === 'win32',
  windowsHide: false
});

if (result.error) {
  console.error(`Failed to start Playwright: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
