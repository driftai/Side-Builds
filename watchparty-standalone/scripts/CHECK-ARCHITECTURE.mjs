import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const MAX_LINES = 450;
const SOURCE_EXTENSIONS = new Set(['.js', '.mjs', '.cjs', '.ts', '.tsx']);
const EXCLUDED_PARTS = new Set([
  'node_modules', '.git', '.runtime', 'test-results', 'playwright-report', 'blob-report'
]);

function isExcluded(relativePath) {
  return relativePath.split(/[\\/]+/).some(part => EXCLUDED_PARTS.has(part));
}

function sourceFiles(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    const rel = path.relative(ROOT, full);
    if (isExcluded(rel)) continue;
    if (entry.isDirectory()) {
      sourceFiles(full, out);
      continue;
    }
    if (SOURCE_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) out.push(rel);
  }
  return out;
}

const violations = [];
for (const relativePath of sourceFiles(ROOT)) {
  const full = path.join(ROOT, relativePath);
  const text = fs.readFileSync(full, 'utf8');
  const lines = text === '' ? 0 : text.split(/\r?\n/).length;
  if (lines > MAX_LINES) violations.push({ file: relativePath, lines });
}

if (violations.length === 0) {
  console.log(`WATCHPARTY ARCHITECTURE: PASS | max ${MAX_LINES} lines | no source violations`);
  process.exit(0);
}

console.error(`WATCHPARTY ARCHITECTURE: FAIL | ${violations.length} source file(s) exceed ${MAX_LINES} lines`);
for (const item of violations.sort((a, b) => b.lines - a.lines)) {
  console.error(`ARCH-${String(item.lines).padStart(4, ' ')} ${item.file}`);
}
console.error('Refactor oversized modules before adding more responsibilities.');
process.exit(1);
