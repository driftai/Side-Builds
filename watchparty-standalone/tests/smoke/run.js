import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { detectScope } from './helpers/git-scope.js';
import { runNodeSmokes } from './node/server.smoke.js';
import { runPlaybackStateSmokes } from './node/playback-state.smoke.js';
import { runMediaSmokes } from './node/media.smoke.js';
import { runMediaResolverSmokes } from './node/media-resolver.smoke.js';
import { runRealtimeSmokes } from './node/realtime.smoke.js';
import { runSecuritySmokes } from './node/security.smoke.js';
import { runLanSmoke } from './integration/lan.smoke.js';
import { runCloudflareSmoke } from './integration/cloudflare.smoke.js';
import { runYouTubeSmoke } from './integration/youtube-live.smoke.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../..');
const RESULTS_DIR = path.join(PROJECT_ROOT, 'test-results');

async function main() {
  const args = process.argv.slice(2);
  const isFull = args.includes('--full') || args.includes('all');
  const isBrowserOnly = args.includes('--browser');
  const isIntegrationOnly = args.includes('--integration');
  const isNodeOnly = args.includes('--node');
  const { changedFiles, scopes } = detectScope();
  const allResults = [];
  const runNode = isFull || isNodeOnly || (!isBrowserOnly && !isIntegrationOnly);
  const runBrowser = isFull || isBrowserOnly || (!isNodeOnly && !isIntegrationOnly);
  const runIntegration = isFull || isIntegrationOnly;

  if (runNode) {
    allResults.push(...await runNodeSmokes());
    allResults.push(...await runPlaybackStateSmokes());
    allResults.push(...await runMediaSmokes());
    allResults.push(...await runMediaResolverSmokes());
    allResults.push(...await runRealtimeSmokes());
    allResults.push(...await runSecuritySmokes());
  }

  if (runIntegration || isFull) {
    for (const [id, runner] of [['INT-LAN', runLanSmoke], ['INT-CF', runCloudflareSmoke], ['INT-YT', runYouTubeSmoke]]) {
      try { allResults.push(...await runner()); }
      catch (err) { allResults.push({ id, status: 'FAIL', error: err.message }); }
    }
  }

  if (runBrowser) {
    try {
      execSync('npx playwright test', { cwd: PROJECT_ROOT, stdio: 'pipe', encoding: 'utf8' });
      const reportFile = path.join(RESULTS_DIR, 'playwright-report.json');
      if (fs.existsSync(reportFile)) {
        try {
          const report = JSON.parse(fs.readFileSync(reportFile, 'utf8'));
          for (const suite of report.suites || []) for (const spec of suite.specs || []) {
            allResults.push({ id: `BROWSER:${spec.title}`, status: spec.ok ? 'PASS' : 'FAIL', error: spec.ok ? null : 'Browser assertion failed (check trace in test-results)' });
          }
        } catch { allResults.push({ id: 'BROWSER:playwright-suite', status: 'PASS' }); }
      } else allResults.push({ id: 'BROWSER:playwright-suite', status: 'PASS' });
    } catch (err) {
      allResults.push({ id: 'BROWSER:playwright-suite', status: 'FAIL', error: err.stdout?.split('\n').filter(line => /Error:|failed/i.test(line)).join('\n') || err.message });
    }
  }

  if (!fs.existsSync(RESULTS_DIR)) fs.mkdirSync(RESULTS_DIR, { recursive: true });
  const passCount = allResults.filter(r => r.status === 'PASS').length;
  const failCount = allResults.filter(r => r.status === 'FAIL').length;
  const skipCount = allResults.filter(r => r.status === 'SKIP').length;
  const scopeStr = scopes.length ? scopes.join(',') : 'all';
  fs.writeFileSync(path.join(RESULTS_DIR, 'smoke-summary.json'), JSON.stringify({ timestamp: new Date().toISOString(), pass: passCount, fail: failCount, skip: skipCount, changed: changedFiles.length, scopes, changedFiles, results: allResults }, null, 2), 'utf8');
  console.log(`WATCHPARTY SMOKE: PASS ${passCount} | FAIL ${failCount} | SKIP ${skipCount} | CHANGED ${changedFiles.length} | SCOPE ${scopeStr}`);
  if (failCount > 0) {
    console.error('\nFAILURES:');
    for (const r of allResults.filter(r => r.status === 'FAIL')) console.error(`  [FAIL] ${r.id}: ${r.error || 'Unknown error'}`);
    console.error(`\nArtifacts written to: ${RESULTS_DIR}`);
    process.exit(1);
  }
}

main().catch(err => { console.error(`Runner crashed: ${err.message}`); process.exit(1); });
