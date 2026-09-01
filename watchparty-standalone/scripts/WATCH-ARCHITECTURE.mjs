import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const ROOT = process.cwd();
const CHECK = path.join(ROOT, 'scripts', 'CHECK-ARCHITECTURE.mjs');
const DEBOUNCE_MS = 250;

let timer = null;
let running = false;
let pending = false;
let lastSignature = '';

function sourceFiles(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    const rel = path.relative(ROOT, full);
    if (/(^|[\\/])(?:node_modules|\.git|\.runtime|test-results|playwright-report|blob-report)(?:[\\/]|$)/.test(rel)) continue;
    if (entry.isDirectory()) sourceFiles(full, out);
    else if (/\.(?:js|mjs|cjs|ts|tsx)$/i.test(entry.name)) out.push(full);
  }
  return out;
}

function signature() {
  const parts = [];
  for (const full of sourceFiles(ROOT)) {
    try {
      const stat = fs.statSync(full);
      parts.push(`${path.relative(ROOT, full)}:${stat.size}:${stat.mtimeMs}`);
    } catch {}
  }
  return parts.sort().join('|');
}

function runCheck(reason = 'change') {
  if (running) {
    pending = true;
    return;
  }
  running = true;
  const result = spawnSync(process.execPath, [CHECK], {
    cwd: ROOT,
    stdio: 'inherit',
    shell: false
  });
  running = false;
  if (pending) {
    pending = false;
    schedule(`queued-${reason}`);
  }
  if (result.error) {
    console.error(`WATCHPARTY ARCHITECTURE WATCH: ERROR | ${result.error.message}`);
  }
}

function schedule(reason) {
  clearTimeout(timer);
  timer = setTimeout(() => runCheck(reason), DEBOUNCE_MS);
}

console.log('WATCHPARTY ARCHITECTURE WATCH: ACTIVE | quiet background ceiling monitor');
console.log('WATCHPARTY ARCHITECTURE WATCH: violations are emitted only when detected');
lastSignature = signature();
runCheck('initial');

const watched = [
  path.join(ROOT, 'public'),
  path.join(ROOT, 'src'),
  path.join(ROOT, 'scripts')
];

const watchers = [];
for (const dir of watched) {
  if (!fs.existsSync(dir)) continue;
  watchers.push(fs.watch(dir, { recursive: true }, () => {
    const next = signature();
    if (next === lastSignature) return;
    lastSignature = next;
    schedule('file-change');
  }));
}

const stop = () => {
  clearTimeout(timer);
  for (const watcher of watchers) watcher.close();
  process.exit(0);
};
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
process.on('exit', () => { for (const watcher of watchers) watcher.close(); });
