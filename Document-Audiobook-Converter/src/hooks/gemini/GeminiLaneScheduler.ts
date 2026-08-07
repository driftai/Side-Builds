import type { GeminiApiConfig, NarrationResult } from '../../types/gemini';
import { normalizeNarrationStyle } from '../../config/narrationPolicy';
import { GeminiLane } from './GeminiLane';
import type { GeminiSchedulerDependencies, LaneConnectionState, LaneJob } from './types';

const LANE_COUNT = 2;
const DISCONNECTED_MESSAGE =
    'Gemini is disconnected. Reconnect from the Gemini Live Audio panel to use it again.';

const sessionIdentity = (config: GeminiApiConfig | null): string | null => config
    ? JSON.stringify([
        config.websocketUrl,
        config.apiKey,
        config.model,
        config.allowModelOverride,
        config.voice,
        normalizeNarrationStyle(config.instructions),
    ])
    : null;

/** Assigns the lowest document position to each free, exclusively owned lane. */
export class GeminiLaneScheduler {
    private config: GeminiApiConfig | null = null;
    private blocked = false;
    private readonly queue: LaneJob[] = [];
    private readonly lanes: GeminiLane[];

    constructor(private readonly dependencies: GeminiSchedulerDependencies) {
        this.lanes = Array.from({ length: LANE_COUNT }, () => new GeminiLane({
            getConfig: () => this.config,
            isBlocked: () => this.blocked,
            getAudioContext: dependencies.getAudioContext,
            onStateChange: () => this.syncConnectionState(),
        }));
    }

    setConfig(config: GeminiApiConfig | null): void {
        const changed = this.config !== null
            && sessionIdentity(this.config) !== sessionIdentity(config);
        this.config = config;
        if (!changed) return;
        for (const lane of this.lanes) lane.reconfigure();
        this.syncConnectionState();
    }

    generateAudioForSentence(
        text: string,
        signal?: AbortSignal,
        onChunk?: (pcm: ArrayBuffer) => void,
        priority: number = Number.MAX_SAFE_INTEGER,
    ): Promise<NarrationResult> {
        if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
        if (this.blocked) return Promise.reject(new Error(DISCONNECTED_MESSAGE));

        return new Promise<NarrationResult>((resolve, reject) => {
            this.queue.push({ text, priority, signal, onChunk, resolve, reject });
            for (const lane of this.lanes) this.pump(lane);
        });
    }

    disconnect(): void {
        this.blocked = true;
        this.dependencies.onBlockedChange(true);
        while (this.queue.length) {
            this.queue.pop()?.reject(new DOMException('Aborted', 'AbortError'));
        }
        window.dispatchEvent(new CustomEvent('closeGeminiTestConnection'));
        for (const lane of this.lanes) lane.disconnect();
        this.syncConnectionState();
    }

    allowConnections(): void {
        this.blocked = false;
        this.dependencies.onBlockedChange(false);
    }

    resetContinuity(): void {
        for (const lane of this.lanes) lane.resetContinuity();
    }

    private syncConnectionState(): void {
        const states = this.lanes.map(lane => lane.connectionState);
        let aggregate: LaneConnectionState = 'disconnected';
        if (states.includes('connected')) aggregate = 'connected';
        else if (states.includes('connecting')) aggregate = 'connecting';
        else if (states.includes('error')) aggregate = 'error';
        this.dependencies.onStateChange(aggregate);
    }

    private pump(lane: GeminiLane): void {
        if (lane.running) return;

        for (let index = this.queue.length - 1; index >= 0; index--) {
            if (!this.queue[index].signal?.aborted) continue;
            this.queue[index].reject(new DOMException('Aborted', 'AbortError'));
            this.queue.splice(index, 1);
        }
        if (this.queue.length === 0) return;

        let pick = 0;
        for (let index = 1; index < this.queue.length; index++) {
            if (this.queue[index].priority < this.queue[pick].priority) pick = index;
        }
        const [job] = this.queue.splice(pick, 1);
        lane.running = true;
        void lane.run(job).finally(() => {
            lane.running = false;
            this.pump(lane);
        });
    }
}
