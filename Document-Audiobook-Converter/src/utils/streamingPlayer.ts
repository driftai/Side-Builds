/**
 * Play 16-bit PCM as it arrives, instead of waiting for the whole passage.
 *
 * The Live API streams a passage's audio in fragments. Normally those are
 * collected and turned into one buffer, which is what makes ordinary playback
 * reliable - the audio cannot run out mid-sentence because all of it is already
 * there. The cost is that a passage which has not finished generating cannot
 * start at all, so when the look-ahead falls behind you wait in silence.
 *
 * This schedules each fragment onto the audio clock the moment it arrives,
 * back-to-back with the one before it, so playback can begin part-way through
 * generation. Scheduling is sample-accurate as long as fragments keep arriving
 * ahead of the play head; if they do not, the audio runs dry and there is an
 * audible gap. Hence the lead-in below, and the caller's choice to opt in.
 */

/** Seconds of audio to gather before starting, as a cushion against arrival jitter. */
const LEAD_IN_SECONDS = 0.9;

/** Small offset for the first fragment so scheduling is never already late. */
const SCHEDULING_MARGIN = 0.05;

export interface StreamPlayerOptions {
    context: AudioContext;
    sampleRate: number;
    /** All scheduled audio has finished playing. */
    onFinished: () => void;
    /** Fragments arrived too late and playback ran dry. Reported once. */
    onStarved?: () => void;
}

export class PcmStreamPlayer {
    private readonly context: AudioContext;
    private readonly sampleRate: number;
    private readonly onFinished: () => void;
    private readonly onStarved?: () => void;

    private pending: Uint8Array[] = [];
    private pendingBytes = 0;
    /** A trailing odd byte: samples are 16-bit and must not be split. */
    private carry: Uint8Array | null = null;

    private sources: AudioBufferSourceNode[] = [];
    private playHeadTime = 0;
    private startedAt: number | null = null;
    private started = false;
    private ended = false;
    private stopped = false;
    private starvedReported = false;
    private finishTimer: number | null = null;

    constructor(options: StreamPlayerOptions) {
        this.context = options.context;
        this.sampleRate = options.sampleRate;
        this.onFinished = options.onFinished;
        this.onStarved = options.onStarved;
    }

    /** Seconds of audio scheduled so far, including what is still queued. */
    get scheduledSeconds(): number {
        const pendingSeconds = this.pendingBytes / 2 / this.sampleRate;
        const scheduled = this.startedAt === null ? 0 : this.playHeadTime - this.startedAt;
        return scheduled + pendingSeconds;
    }

    /** How far into the passage playback has reached, in seconds. */
    get elapsedSeconds(): number {
        if (this.startedAt === null) return 0;
        return Math.max(0, this.context.currentTime - this.startedAt);
    }

    get hasStarted(): boolean {
        return this.started;
    }

    push(pcm: ArrayBuffer): void {
        if (this.stopped || this.ended) return;
        this.pending.push(new Uint8Array(pcm));
        this.pendingBytes += pcm.byteLength;

        if (!this.started) {
            // Hold back until there is a cushion worth playing against.
            if (this.pendingBytes / 2 / this.sampleRate >= LEAD_IN_SECONDS) this.begin();
            return;
        }
        this.flush();
    }

    /** No more fragments are coming. Plays out whatever is left. */
    end(): void {
        if (this.stopped || this.ended) return;
        this.ended = true;
        if (!this.started) {
            // Short passage that finished before the cushion filled - play it all.
            if (this.pendingBytes === 0) {
                this.onFinished();
                return;
            }
            this.begin();
        } else {
            this.flush();
        }
        this.scheduleFinish();
    }

    stop(): void {
        if (this.stopped) return;
        this.stopped = true;
        if (this.finishTimer !== null) {
            clearTimeout(this.finishTimer);
            this.finishTimer = null;
        }
        for (const source of this.sources) {
            source.onended = null;
            try { source.stop(); } catch { /* already stopped */ }
        }
        this.sources = [];
        this.pending = [];
        this.pendingBytes = 0;
    }

    private begin(): void {
        this.started = true;
        this.playHeadTime = this.context.currentTime + SCHEDULING_MARGIN;
        this.startedAt = this.playHeadTime;
        this.flush();
    }

    /** Turn everything buffered into one scheduled source. */
    private flush(): void {
        if (this.stopped || this.pendingBytes === 0) return;

        let total = this.pendingBytes;
        const parts = this.pending;
        this.pending = [];
        this.pendingBytes = 0;

        if (this.carry) {
            parts.unshift(this.carry);
            total += this.carry.length;
            this.carry = null;
        }

        const joined = new Uint8Array(total);
        let offset = 0;
        for (const part of parts) {
            joined.set(part, offset);
            offset += part.length;
        }

        // Keep a dangling byte back for the next fragment rather than dropping
        // it, which would shift every following sample by half a word.
        const usable = total - (total % 2);
        if (usable !== total) this.carry = joined.slice(usable);
        if (usable === 0) return;

        const samples = new Int16Array(joined.buffer, 0, usable / 2);
        const buffer = this.context.createBuffer(1, samples.length, this.sampleRate);
        const channel = buffer.getChannelData(0);
        for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 32768;

        const source = this.context.createBufferSource();
        source.buffer = buffer;
        source.connect(this.context.destination);

        // If the play head has slipped into the past the stream ran dry; resume
        // from now rather than scheduling audio that would be skipped.
        const now = this.context.currentTime;
        if (this.playHeadTime < now) {
            if (!this.starvedReported) {
                this.starvedReported = true;
                this.onStarved?.();
            }
            this.playHeadTime = now;
        }

        source.start(this.playHeadTime);
        this.playHeadTime += buffer.duration;
        this.sources.push(source);

        // Drop finished sources so a long passage does not accumulate them.
        source.onended = () => {
            const at = this.sources.indexOf(source);
            if (at >= 0) this.sources.splice(at, 1);
        };

        if (this.ended) this.scheduleFinish();
    }

    /** Fire onFinished when the last scheduled fragment has played out. */
    private scheduleFinish(): void {
        if (this.stopped) return;
        if (this.finishTimer !== null) clearTimeout(this.finishTimer);
        const remaining = Math.max(0, this.playHeadTime - this.context.currentTime);
        this.finishTimer = window.setTimeout(() => {
            this.finishTimer = null;
            if (!this.stopped) this.onFinished();
        }, remaining * 1000 + 30);
    }
}
