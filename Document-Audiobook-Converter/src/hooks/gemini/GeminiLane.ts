import type { NarrationResult } from '../../types/gemini';
import { createNarrationAudioBuffer, decodeAudioChunk } from '../../services/gemini/liveAudio';
import {
    createDisconnectMessage,
    createInitMessage,
    createTurnMessage,
    isSessionReadyMessage,
    parseServerMessage,
} from '../../services/gemini/liveProtocol';
import type { GeminiLaneDependencies, LaneConnectionState, LaneJob } from './types';

const TURN_IDLE_TIMEOUT_MS = 15000;
const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 2000;
const MAX_TURNS_PER_SESSION = 6;

const delay = (milliseconds: number) => new Promise(resolve => setTimeout(resolve, milliseconds));

/**
 * Owns one socket and its strictly serial turn stream. Server messages have no
 * request id, so no other object is allowed to run or drain a turn on this lane.
 */
export class GeminiLane {
    public running = false;
    private socket: WebSocket | null = null;
    private connecting: Promise<WebSocket> | null = null;
    private turns = 0;
    private lastText?: string;
    private continueFrom?: string;
    private state: LaneConnectionState = 'disconnected';

    constructor(private readonly dependencies: GeminiLaneDependencies) { }

    get connectionState(): LaneConnectionState {
        return this.state;
    }

    async run(job: LaneJob): Promise<void> {
        try {
            for (let attempt = 0; ; attempt++) {
                if (job.signal?.aborted) throw new DOMException('Aborted', 'AbortError');

                let socket: WebSocket;
                try {
                    socket = await this.getOrCreateSocket();
                } catch (error) {
                    if (this.dependencies.isBlocked()) throw error;
                    if (attempt < MAX_RETRIES) {
                        console.log(
                            `WebSocket creation failed, retrying (${attempt + 1}/${MAX_RETRIES}) in 2 seconds...`,
                        );
                        await delay(RETRY_DELAY_MS);
                        continue;
                    }
                    console.error(`WebSocket creation failed after ${attempt} retries`);
                    throw error;
                }

                try {
                    const result = await this.runTurn(socket, job);
                    this.lastText = job.text;
                    this.retireSessionIfExhausted();
                    job.resolve(result);
                    return;
                } catch (error) {
                    const typedError = error as Error;
                    const socketDropped = typedError.message
                        ?.includes('WebSocket closed during audio generation');
                    if (typedError.name !== 'AbortError' && socketDropped && attempt < MAX_RETRIES) {
                        console.log(
                            `WebSocket closed during generation, retrying (${attempt + 1}/${MAX_RETRIES}) in 2 seconds...`,
                        );
                        await delay(RETRY_DELAY_MS);
                        continue;
                    }
                    throw error;
                }
            }
        } catch (error) {
            job.reject(error);
        }
    }

    disconnect(): void {
        const socket = this.socket;
        this.socket = null;
        this.connecting = null;
        this.turns = 0;
        // The scheduler updates the aggregate once after all lanes have been
        // torn down, matching the original all-at-once disconnect transition.
        this.state = 'disconnected';
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        try {
            socket.send(JSON.stringify(createDisconnectMessage()));
        } catch {
            // The socket is already going away.
        }
        setTimeout(() => {
            try { socket.close(1000, 'disconnected by user'); } catch { /* already closed */ }
        }, 150);
    }

    resetContinuity(): void {
        this.lastText = undefined;
        this.continueFrom = undefined;
    }

    private setState(state: LaneConnectionState): void {
        this.state = state;
        this.dependencies.onStateChange();
    }

    private async getOrCreateSocket(): Promise<WebSocket> {
        if (this.dependencies.isBlocked()) {
            throw new Error(
                'Gemini is disconnected. Reconnect from the Gemini Live Audio panel to use it again.',
            );
        }
        const config = this.dependencies.getConfig();
        if (!config?.websocketUrl) throw new Error('Gemini WebSocket URL must be configured.');
        if (this.socket?.readyState === WebSocket.OPEN) return this.socket;
        if (this.connecting) return this.connecting;

        window.dispatchEvent(new CustomEvent('closeGeminiTestConnection'));
        await delay(300);

        const connectionPromise = new Promise<WebSocket>((resolve, reject) => {
            const socket = new WebSocket(config.websocketUrl);
            let sessionReady = false;
            const initTimeout = setTimeout(() => {
                if (sessionReady) return;
                console.warn('WebSocket initialization timed out, closing socket');
                socket.close();
                reject(new Error('WebSocket initialization timeout'));
            }, 15000);

            socket.onopen = () => {
                this.setState('connecting');
                socket.send(JSON.stringify(createInitMessage(config, {
                    allowModelOverride: true,
                    instructions: config.instructions,
                    continuationHint: this.continueFrom ?? '',
                })));
            };
            socket.onmessage = event => {
                try {
                    const message = parseServerMessage(event.data as string);
                    if (!sessionReady && isSessionReadyMessage(message)) {
                        clearTimeout(initTimeout);
                        sessionReady = true;
                        this.socket = socket;
                        this.connecting = null;
                        this.continueFrom = undefined;
                        this.turns = 0;
                        this.setState('connected');
                        resolve(socket);
                    }
                } catch (error) {
                    console.error('Failed to parse server message:', error);
                }
            };
            socket.onerror = () => {
                clearTimeout(initTimeout);
                this.socket = null;
                this.connecting = null;
                this.setState('error');
                reject(new Error('WebSocket connection error'));
            };
            socket.onclose = () => {
                if (this.socket === socket || this.socket === null) this.setState('disconnected');
                if (this.socket === socket) {
                    this.socket = null;
                    this.connecting = null;
                }
            };
        });

        this.connecting = connectionPromise;
        connectionPromise.catch(() => {
            if (this.connecting === connectionPromise) this.connecting = null;
        });
        return connectionPromise;
    }

    /** Drain through the transcription boundary even after an abort. */
    private runTurn(socket: WebSocket, job: LaneJob): Promise<NarrationResult> {
        return new Promise<NarrationResult>((resolve, reject) => {
            const chunks: ArrayBuffer[] = [];
            let aborted = false;
            let finished = false;
            let timer: ReturnType<typeof setTimeout>;

            const finish = () => {
                finished = true;
                clearTimeout(timer);
                socket.removeEventListener('message', onMessage);
                socket.removeEventListener('close', onClose);
                job.signal?.removeEventListener('abort', onAbort);
            };
            const failIdle = () => {
                if (finished) return;
                finish();
                reject(new Error('Timeout waiting for audio response'));
            };
            const heard = () => {
                clearTimeout(timer);
                timer = setTimeout(failIdle, TURN_IDLE_TIMEOUT_MS);
            };
            const onAbort = () => {
                aborted = true;
                chunks.length = 0;
            };
            const onClose = () => {
                if (finished) return;
                finish();
                reject(new Error('WebSocket closed during audio generation'));
            };
            const onMessage = (event: MessageEvent) => {
                if (finished) return;
                let message;
                try {
                    message = parseServerMessage(event.data as string);
                } catch (error) {
                    console.error('Failed to parse server message:', error);
                    return;
                }
                heard();

                if (message.audio) {
                    if (!aborted) {
                        const pcm = decodeAudioChunk(message.audio);
                        chunks.push(pcm);
                        if (job.onChunk) {
                            try { job.onChunk(pcm); } catch (error) {
                                console.warn('Streaming chunk listener failed:', error);
                            }
                        }
                    }
                    return;
                }
                if (!message.is_transcription) return;

                finish();
                if (aborted) {
                    reject(new DOMException('Aborted', 'AbortError'));
                } else if (chunks.length === 0) {
                    console.error('No audio chunks were received before transcription');
                    reject(new Error('No audio data received.'));
                } else {
                    try {
                        const spokenText = typeof message.text === 'string' ? message.text.trim() : '';
                        const buffer = createNarrationAudioBuffer(
                            this.dependencies.getAudioContext(),
                            chunks,
                            job.text,
                        );
                        resolve({ buffer, spokenText });
                    } catch (error) {
                        reject(error as Error);
                    }
                }
            };

            timer = setTimeout(failIdle, TURN_IDLE_TIMEOUT_MS);
            job.signal?.addEventListener('abort', onAbort);
            socket.addEventListener('message', onMessage);
            socket.addEventListener('close', onClose);
            socket.send(JSON.stringify(createTurnMessage(job.text.trim())));
        });
    }

    private retireSessionIfExhausted(): void {
        this.turns += 1;
        if (this.turns < MAX_TURNS_PER_SESSION) return;
        const socket = this.socket;
        this.turns = 0;
        this.socket = null;
        this.connecting = null;
        this.continueFrom = this.lastText;
        if (socket?.readyState === WebSocket.OPEN) {
            console.log(
                `Recycling Live session after ${MAX_TURNS_PER_SESSION} passages to keep context clean`,
            );
            try { socket.close(1000, 'context refresh'); } catch { /* already closing */ }
        }
    }
}
