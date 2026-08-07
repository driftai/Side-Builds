import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const SOURCE_LINE_LIMIT = 450;
const SOURCE_EXTENSIONS = new Set([
  '.cjs', '.css', '.html', '.js', '.jsx', '.mjs', '.py', '.ts', '.tsx',
]);
const EXCLUDED_DIRECTORIES = new Set([
  '.git', '.vite', '.venv', 'coverage', 'dist', 'node_modules', 'venv', '__pycache__',
]);

const projectRoot = process.cwd();
const sourceFiles = [];

const collectSourceFiles = async (directory) => {
  const entries = await readdir(directory, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith('.') && entry.isDirectory() && entry.name !== '.openai') continue;
    if (entry.isDirectory() && EXCLUDED_DIRECTORIES.has(entry.name)) continue;

    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      await collectSourceFiles(absolutePath);
    } else if (SOURCE_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
      sourceFiles.push(absolutePath);
    }
  }
};

const countLines = (source) => {
  if (!source) return 0;
  const normalized = source.replace(/\r\n/g, '\n');
  const lineCount = normalized.split('\n').length;
  return normalized.endsWith('\n') ? lineCount - 1 : lineCount;
};

await collectSourceFiles(projectRoot);

const measured = await Promise.all(sourceFiles.map(async (absolutePath) => ({
  file: path.relative(projectRoot, absolutePath),
  lines: countLines(await readFile(absolutePath, 'utf8')),
})));
const oversized = measured
  .filter(({ lines }) => lines > SOURCE_LINE_LIMIT)
  .sort((left, right) => right.lines - left.lines);

if (oversized.length > 0) {
  console.error(`Source files must stay at or below ${SOURCE_LINE_LIMIT} physical lines:`);
  for (const { file, lines } of oversized) console.error(`  ${lines}  ${file}`);
  process.exitCode = 1;
} else {
  const largest = measured.sort((left, right) => right.lines - left.lines).slice(0, 5);
  console.log(`Checked ${measured.length} source files; all are <= ${SOURCE_LINE_LIMIT} lines.`);
  for (const { file, lines } of largest) console.log(`  ${lines}  ${file}`);
}
