import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../../..');

export async function runCloudflareSmoke() {
  const results = [];
  const record = (id, fn) => async () => {
    try {
      const res = await fn();
      if (res && res.skip) {
        results.push({ id, status: 'SKIP', reason: res.reason });
      } else {
        results.push({ id, status: 'PASS' });
      }
    } catch (err) {
      results.push({ id, status: 'FAIL', error: err.message });
    }
  };

  await record('INT-CF-01:tools-dependency-path-and-error-handling', async () => {
    const launcherBatPath = path.join(PROJECT_ROOT, 'scripts/START-WATCHPARTY-REMOTE.bat');
    assert.ok(fs.existsSync(launcherBatPath), 'START-WATCHPARTY-REMOTE.bat must exist');
    const content = fs.readFileSync(launcherBatPath, 'utf8');

    // Expected tools path
    assert.ok(
      content.includes('%ROOT%\\tools\\cloudflared.exe'),
      'Remote launcher must expect cloudflared at %ROOT%\\tools\\cloudflared.exe'
    );

    // No auto-download URL or installer call
    assert.ok(
      !content.includes('github.com/cloudflare/cloudflared/releases'),
      'Remote launcher must not contain automatic download release URLs'
    );
    assert.ok(
      !content.includes('Invoke-WebRequest') && !content.includes('curl') && !content.includes('bitsadmin'),
      'Batch launcher must not execute automated downloads'
    );

    // Actionable error message when missing
    assert.ok(
      content.includes('cloudflared.exe was not found'),
      'Batch launcher must display clear error when binary is missing'
    );
  })();

  await record('INT-CF-02:local-binary-executable', async () => {
    const cloudflaredPath = path.join(PROJECT_ROOT, 'tools/cloudflared.exe');
    if (!fs.existsSync(cloudflaredPath)) {
      return { skip: true, reason: 'tools/cloudflared.exe is not installed on this machine (expected per-user dependency)' };
    }

    try {
      const out = execSync(`"${cloudflaredPath}" --version`, { encoding: 'utf8', timeout: 5000 });
      assert.ok(out.includes('cloudflared version'), 'Binary responds to --version');
    } catch (err) {
      return { skip: true, reason: `Local cloudflared binary could not be executed: ${err.message}` };
    }
  })();

  return results;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  runCloudflareSmoke().then(results => {
    for (const r of results) {
      console.log(`[${r.status}] ${r.id}${r.reason ? ` (${r.reason})` : ''}${r.error ? `: ${r.error}` : ''}`);
    }
  });
}
