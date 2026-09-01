import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const PROJECT_ROOT = path.resolve(__dirname, '../..');
export const PUBLIC = path.join(PROJECT_ROOT, 'public');
export const PORT = Number(process.env.PORT || 9085);
export const LAN_MODE = process.argv.includes('--lan');
export const HOST = process.env.HOST || (LAN_MODE ? '0.0.0.0' : '127.0.0.1');

export const MAX_MESSAGES = 100;
export const ROOM_TTL_MS = 5 * 60 * 1000;
export const MEMBER_STALE_MS = 120 * 1000;
export const DELETED_ROOM_TTL_MS = 120 * 1000;
