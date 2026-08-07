import { describe, it, expect, vi } from 'vitest';
import { PcmStreamPlayer } from '../src/utils/streamingPlayer';

/**
 * The bypass plays a passage while it is still being generated. It is only safe
 * if fragments are scheduled back-to-back with no gap, and if falling behind is
 * noticed rather than silently scheduling audio into the past.
 */
const RATE = 24000;
const secondsOfPcm = (s: number) => new ArrayBuffer(Math.round(s * RATE) * 2);

class FakeSource {
    buffer: any = null;
    onended: (() => void) | null = null;
    startedAt: number | null = null;
    stopped = false;
    connect() { }
    start(when: number) { this.startedAt = when; }
    stop() { this.stopped = true; }
}

class FakeContext {
    currentTime = 100;
    destination = {};
    sources: FakeSource[] = [];
    createBuffer(_channels: number, length: number, sampleRate: number) {
        return {
            length, sampleRate, duration: length / sampleRate,
            getChannelData: () => new Float32Array(length),
        };
    }
    createBufferSource() { const s = new FakeSource(); this.sources.push(s); return s; }
}

const makePlayer = (context: FakeContext, onFinished = () => { }, onStarved?: () => void) =>
    new PcmStreamPlayer({ context: context as any, sampleRate: RATE, onFinished, onStarved });

describe('PcmStreamPlayer', () => {
    it('waits for a cushion before starting', () => {
        const ctx = new FakeContext();
        const player = makePlayer(ctx);
        player.push(secondsOfPcm(0.3));
        expect(player.hasStarted).toBe(false);
        expect(ctx.sources).toHaveLength(0);

        player.push(secondsOfPcm(0.7));      // over the lead-in
        expect(player.hasStarted).toBe(true);
        expect(ctx.sources).toHaveLength(1);
        expect(ctx.sources[0].startedAt!).toBeGreaterThan(ctx.currentTime);
    });

    it('schedules fragments back to back, with no gap', () => {
        const ctx = new FakeContext();
        const player = makePlayer(ctx);
        player.push(secondsOfPcm(1.0));
        const firstEnd = ctx.sources[0].startedAt! + ctx.sources[0].buffer.duration;

        player.push(secondsOfPcm(0.5));
        expect(ctx.sources[1].startedAt!).toBeCloseTo(firstEnd, 9);
    });

    it('plays a passage shorter than the cushion instead of stalling on it', () => {
        const ctx = new FakeContext();
        const player = makePlayer(ctx);
        player.push(secondsOfPcm(0.2));
        player.end();
        expect(ctx.sources).toHaveLength(1);
    });

    it('finishes immediately when a turn produced nothing', () => {
        const ctx = new FakeContext();
        const onFinished = vi.fn();
        makePlayer(ctx, onFinished).end();
        expect(onFinished).toHaveBeenCalled();
    });

    it('keeps sample alignment across oddly sized fragments', () => {
        const ctx = new FakeContext();
        const player = makePlayer(ctx);
        player.push(new ArrayBuffer(48001));      // odd byte count
        player.push(new ArrayBuffer(47999));
        const samples = ctx.sources.reduce((n, s) => n + s.buffer.length, 0);
        expect(samples).toBe(96000 / 2);
    });

    it('reports running dry and resumes from the present, not the past', () => {
        const ctx = new FakeContext();
        const onStarved = vi.fn();
        const player = makePlayer(ctx, () => { }, onStarved);

        player.push(secondsOfPcm(1.0));
        expect(onStarved).not.toHaveBeenCalled();

        ctx.currentTime += 10;                     // playback ran past everything queued
        player.push(secondsOfPcm(0.5));
        expect(onStarved).toHaveBeenCalledTimes(1);
        expect(ctx.sources[1].startedAt!).toBeGreaterThanOrEqual(ctx.currentTime);
    });

    it('stops everything it scheduled, and ignores anything after', () => {
        const ctx = new FakeContext();
        const player = makePlayer(ctx);
        player.push(secondsOfPcm(1.0));
        player.stop();
        expect(ctx.sources.every(s => s.stopped)).toBe(true);

        player.push(secondsOfPcm(1.0));
        expect(ctx.sources).toHaveLength(1);
    });
});
