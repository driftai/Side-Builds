import assert from 'node:assert/strict';
import { ForegroundMaskAssist } from '../public/js/foreground-mask-assist.js';
const originalWorker = globalThis.Worker;
const workers = [];
globalThis.Worker = class {
  constructor() { workers.push(this); }
  postMessage(message) {
    if (message.type === 'load') queueMicrotask(() => this.onmessage({ data: { type: 'ready' } }));
    else this.job = message;
  }
  finish() { this.onmessage({ data: { type: 'mask', id: this.job.id, mask: new Uint8Array(64).fill(255), ms: 200 } }); }
  terminate() { this.terminated = true; }
};
const assist = new ForegroundMaskAssist();
try {
  assist.setEnabled(true); await assist.loading;
  const rgba = new Uint8ClampedArray(256).fill(90);
  const first = assist.forFrame(rgba, 8, 8, 0);
  workers[0].finish();
  assert.ok(await first);
  assert.deepEqual(await assist.forFrame(rgba, 8, 8, 0.1), new Uint8Array(64).fill(255), 'unchanged borders and interior can reuse matching evidence');
  const moving = new Uint8ClampedArray(256).fill(180);
  const next = assist.forFrame(moving, 8, 8, 0.2);
  assert.ok(assist.pending, 'meaningful image change must request fresh evidence within the sparse interval');
  assist.reset(); workers[0].finish();
  assert.equal(await next, null, 'results from before a seek/source reset must be discarded');
  const outstanding = assist.forFrame(rgba, 8, 8, 2);
  assist.setEnabled(false);
  assert.equal(await outstanding, null, 'disabling must settle pending work');
  assert.ok(workers[0].terminated);
  workers[0].onmessage({ data: { type: 'ready' } });
  assert.equal(assist.ready, false, 'an obsolete worker must not revive itself');
  console.log('Foreground mask scheduling passed: matching reuse, motion refresh, reset and disable cancellation.');
} finally { assist.setEnabled(false); globalThis.Worker = originalWorker; }
