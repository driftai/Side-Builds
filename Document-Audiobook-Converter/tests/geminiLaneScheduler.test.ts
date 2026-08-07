import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GeminiLaneScheduler } from '../src/hooks/gemini/GeminiLaneScheduler';
import type { GeminiApiConfig } from '../src/types/gemini';

class FakeWebSocket {
    static readonly CONNECTING = 0;
    static readonly OPEN = 1;
    static readonly CLOSING = 2;
    static readonly CLOSED = 3;
    static instances: FakeWebSocket[] = [];

    readyState = FakeWebSocket.CONNECTING;
    sent: string[] = [];
    onopen: ((event: Event) => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    onclose: ((event: Event) => void) | null = null;
    private listeners = new Map<string, Set<(event: any) => void>>();

    constructor(public readonly url: string) {
        FakeWebSocket.instances.push(this);
        setTimeout(() => this.open(), 0);
    }

    send(data: string): void {
        this.sent.push(data);
    }

    close(): void {
        this.readyState = FakeWebSocket.CLOSED;
        const event = {} as Event;
        this.onclose?.(event);
        this.emit('close', event);
    }

    addEventListener(type: string, listener: (event: any) => void): void {
        const listeners = this.listeners.get(type) ?? new Set();
        listeners.add(listener);
        this.listeners.set(type, listeners);
    }

    removeEventListener(type: string, listener: (event: any) => void): void {
        this.listeners.get(type)?.delete(listener);
    }

    message(payload: Record<string, unknown>): void {
        const event = { data: JSON.stringify(payload) } as MessageEvent;
        this.onmessage?.(event);
        this.emit('message', event);
    }

    private open(): void {
        this.readyState = FakeWebSocket.OPEN;
        this.onopen?.({} as Event);
        this.message({ text: 'Connected to Gemini API', is_system_message: true });
    }

    private emit(type: string, event: any): void {
        for (const listener of this.listeners.get(type) ?? []) listener(event);
    }
}

class FakeAudioContext {
    createBuffer(_channels: number, length: number, sampleRate: number) {
        const channel = new Float32Array(length);
        return { duration: length / sampleRate, getChannelData: () => channel };
    }
}

const config: GeminiApiConfig = {
    apiKey: 'test-key',
    model: 'test-model',
    allowModelOverride: true,
    temperature: 0.5,
    maxTokens: 100,
    timeout: 1000,
    websocketUrl: 'ws://localhost:9084',
    voice: 'Aoede',
    instructions: 'Narrate clearly.',
};

const turnTexts = (socket: FakeWebSocket): string[] => socket.sent
    .map(message => JSON.parse(message))
    .filter(message => message.realtime_input)
    .map(message => message.realtime_input.media_chunks[0].data);

describe('GeminiLaneScheduler', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        FakeWebSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeWebSocket);
        vi.stubGlobal('window', { dispatchEvent: vi.fn() });
    });

    afterEach(() => {
        vi.clearAllTimers();
        vi.useRealTimers();
        vi.unstubAllGlobals();
    });

    it('keeps one turn per socket and gives a free lane the lowest queued priority', async () => {
        const scheduler = new GeminiLaneScheduler({
            getAudioContext: () => new FakeAudioContext() as unknown as AudioContext,
            onStateChange: vi.fn(),
            onBlockedChange: vi.fn(),
        });
        scheduler.setConfig(config);

        const first = scheduler.generateAudioForSentence('first', undefined, undefined, 100);
        void scheduler.generateAudioForSentence('second', undefined, undefined, 101).catch(() => { });
        void scheduler.generateAudioForSentence('later', undefined, undefined, 50).catch(() => { });
        void scheduler.generateAudioForSentence('urgent', undefined, undefined, 3).catch(() => { });

        await vi.advanceTimersByTimeAsync(301);
        expect(FakeWebSocket.instances).toHaveLength(2);
        const firstLane = FakeWebSocket.instances[0];
        expect(turnTexts(firstLane)).toEqual(['first']);

        firstLane.message({ audio: 'AAA=' });
        firstLane.message({ is_transcription: true, text: 'first' });
        await first;
        await Promise.resolve();
        await Promise.resolve();

        expect(turnTexts(firstLane)).toEqual(['first', 'urgent']);
    });
});
