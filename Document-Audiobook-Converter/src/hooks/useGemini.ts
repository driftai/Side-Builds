import { useState, useRef, useCallback, useEffect } from 'react';
import { GeminiApiConfig } from '../components/GeminiConfig';

// A turn is one request/response cycle on the shared socket. The server marks
// the end of every turn with an `is_transcription` message.
const TURN_TIMEOUT_MS = 60000;
const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 2000;
const PCM_SAMPLE_RATE = 24000;

/**
 * Narrated passages per Live session before the socket is recycled.
 *
 * A Live session keeps every turn's audio in its context window, and audio
 * accrues at roughly 25 tokens per second against a 128k limit. Google's own
 * guidance is that as this history builds the model "may hallucinate, slow
 * down, or the session may be forcibly terminated" - audible here as the voice
 * being clean for the first few passages and degrading after that.
 *
 * Narration has no need of conversation history: each passage is independent.
 * So rather than compress the window (which discards history anyway), the
 * socket is dropped after this many turns. The server opens a fresh Gemini
 * session for the next connection, and context starts empty again.
 *
 * The reconnect costs roughly two seconds, which the look-ahead queue absorbs.
 */
const MAX_TURNS_PER_SESSION = 6;

/**
 * How many passages may be generated at the same time.
 *
 * Generation runs at roughly 1.38x real time - a passage takes longer to make
 * than it takes to hear. On a single lane that is a hard ceiling: playback
 * drains the queue faster than one socket can fill it, so the look-ahead can
 * never actually get ahead however deep the queue is, and long passages are
 * heard as waiting. Depth alone cannot fix a throughput problem.
 *
 * Two independent sessions generate two passages at once, putting production
 * comfortably ahead of playback so the buffer grows during the opening
 * passages and stays full afterwards. It costs no extra tokens - the same
 * turns are run, just not one after another.
 *
 * Two and not more: the server allows three concurrent sessions (measured, see
 * session_manager.py) and the config panel's test connection can hold one.
 */
const LANE_COUNT = 2;

/**
 * One narrated passage: the audio, plus what the model reported actually
 * saying. The spoken text lets the app compare narration against the source and
 * flag passages that drifted - it is empty if the session reported nothing.
 */
export interface NarrationResult {
    buffer: AudioBuffer;
    spokenText: string;
}

/**
 * One generation lane: its own socket, its own Gemini session, and its own
 * serialised turn chain.
 *
 * Turns must stay strictly ordered *within* a lane - the server's messages
 * carry no request id, so two overlapping turns on one socket cannot be told
 * apart (see runTurn). Across lanes there is no such problem: separate sockets
 * mean separate message streams, so they can safely run at once.
 */
interface Lane {
    /** Live socket, or null when this lane has none open. */
    socket: WebSocket | null;
    /** Connection attempt in progress, shared by whatever is waiting on it. */
    connecting: Promise<WebSocket> | null;
    /** Turns narrated on the current socket; reset when it is recycled. */
    turns: number;
    /** Serialises turns on this lane's socket. */
    chain: Promise<unknown>;
    /** Turns queued or running here, used to pick the emptiest lane. */
    depth: number;
    /** This lane's connection state, aggregated into the hook's wsState. */
    state: 'disconnected' | 'connecting' | 'connected' | 'error';
}

const makeLane = (): Lane => ({
    socket: null,
    connecting: null,
    turns: 0,
    chain: Promise.resolve(),
    depth: 0,
    state: 'disconnected',
});

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

const decodeAudioChunk = (base64: string): ArrayBuffer => {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
};

export const useGemini = (geminiConfig: GeminiApiConfig | null) => {
    const [wsState, setWsState] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
    const geminiConfigRef = useRef<GeminiApiConfig | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);

    const lanesRef = useRef<Lane[] | null>(null);
    const getLanes = useCallback((): Lane[] => {
        if (!lanesRef.current) {
            lanesRef.current = Array.from({ length: LANE_COUNT }, makeLane);
        }
        return lanesRef.current;
    }, []);

    /** Roll the lanes' individual states into the single one the UI shows. */
    const syncWsState = useCallback(() => {
        const lanes = getLanes();
        if (lanes.some(lane => lane.state === 'connected')) setWsState('connected');
        else if (lanes.some(lane => lane.state === 'connecting')) setWsState('connecting');
        else if (lanes.some(lane => lane.state === 'error')) setWsState('error');
        else setWsState('disconnected');
    }, [getLanes]);

    useEffect(() => { geminiConfigRef.current = geminiConfig; }, [geminiConfig]);

    // One AudioContext for the lifetime of the hook. This used to allocate a new
    // context per sentence, and browsers cap how many a page may hold - a long
    // document would eventually fail to decode anything at all.
    const getAudioContext = useCallback(() => {
        if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
            const Ctor = window.AudioContext || (window as any).webkitAudioContext;
            audioContextRef.current = new Ctor();
        }
        return audioContextRef.current;
    }, []);

    useEffect(() => () => {
        audioContextRef.current?.close().catch(() => { });
        audioContextRef.current = null;
    }, []);

    const getOrCreateWebSocket = useCallback(async (lane: Lane): Promise<WebSocket> => {
        const currentConfig = geminiConfigRef.current;
        // Only the socket URL is required. The key sent here is an optional
        // override - the server resolves its own from the environment, .env.local
        // or its fallback, and reports a clear auth error if none works. Demanding
        // one here blocked the app on a field it does not actually need.
        if (!currentConfig?.websocketUrl) {
            throw new Error('Gemini WebSocket URL must be configured.');
        }

        // If this lane has an active connection, reuse it
        if (lane.socket && lane.socket.readyState === WebSocket.OPEN) {
            return lane.socket;
        }

        // If a connection is already being established, wait for it
        if (lane.connecting) {
            return lane.connecting;
        }

        // Ask GeminiConfig to drop its test socket. This used to be followed by a
        // 1.5s sleep because the server only allowed one concurrent session and the
        // slot had to be released first; the limit is no longer 1, so a short pause
        // for the close frame to flush is enough.
        window.dispatchEvent(new CustomEvent('closeGeminiTestConnection'));
        await delay(300);

        // Create new connection
        const connectionPromise = new Promise<WebSocket>((resolve, reject) => {
            const ws = new WebSocket(currentConfig.websocketUrl);
            let isSessionReady = false;

            const initTimeout = setTimeout(() => {
                if (!isSessionReady) {
                    console.warn("WebSocket initialization timed out, closing socket");
                    ws.close();
                    reject(new Error('WebSocket initialization timeout'));
                }
            }, 15000); // 15 second timeout for initialization

            ws.onopen = () => {
                lane.state = 'connecting';
                syncWsState();
                const setupMessage = {
                    type: 'init',
                    voice: currentConfig.voice,
                    model: currentConfig.model,
                    allowModelOverride: true,
                    apiKey: currentConfig.apiKey,
                    instructions: currentConfig.instructions,
                    sequentialAudioPlay: false
                };
                ws.send(JSON.stringify(setupMessage));
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.text && data.text.includes("Connected to Gemini API") && data.is_system_message && !isSessionReady) {
                        clearTimeout(initTimeout);
                        isSessionReady = true;
                        lane.state = 'connected';
                        lane.socket = ws;
                        lane.connecting = null;
                        // Fresh session, fresh context: count from zero however
                        // this connection came about, not only after a recycle.
                        lane.turns = 0;
                        syncWsState();
                        resolve(ws);
                    }
                } catch (e) {
                    console.error("Failed to parse server message:", e);
                }
            };

            ws.onerror = () => {
                clearTimeout(initTimeout);
                lane.state = 'error';
                lane.socket = null;
                lane.connecting = null;
                syncWsState();
                reject(new Error("WebSocket connection error"));
            };

            ws.onclose = () => {
                // Only this lane's own socket closing says anything about it; a
                // stale socket from a recycle finishing its close must not mark
                // the lane down while a fresh one is already serving turns.
                if (lane.socket === ws || lane.socket === null) {
                    lane.state = 'disconnected';
                    syncWsState();
                }
                if (lane.socket === ws) {
                    lane.socket = null;
                    lane.connecting = null;
                }
            };
        });

        lane.connecting = connectionPromise;
        // A failed attempt must not be cached, or the lane would hand the same
        // rejected promise to every later turn and never reconnect.
        connectionPromise.catch(() => {
            if (lane.connecting === connectionPromise) lane.connecting = null;
        });
        return connectionPromise;
    }, [syncWsState]);

    const buildAudioBuffer = useCallback((chunks: ArrayBuffer[], text: string): AudioBuffer => {
        const totalLength = chunks.reduce((acc, value) => acc + value.byteLength, 0);
        const concatenated = new Uint8Array(totalLength);
        let offset = 0;
        for (const chunk of chunks) {
            concatenated.set(new Uint8Array(chunk), offset);
            offset += chunk.byteLength;
        }

        const audioContext = getAudioContext();
        const pcmData = new Int16Array(concatenated.buffer);
        const audioBuffer = audioContext.createBuffer(1, pcmData.length, PCM_SAMPLE_RATE);
        const channelData = audioBuffer.getChannelData(0);
        for (let i = 0; i < pcmData.length; i++) {
            channelData[i] = pcmData[i] / 32768.0;
        }

        // Validation: Check if audio is suspiciously short for the text length.
        // This catches truncated generations where only the opening words are read.
        const textLength = text.length;
        const duration = audioBuffer.duration;

        if (textLength > 10) {
            const expectedMinDuration = (textLength / 25); // Conservative: 25 chars/sec

            if (duration < expectedMinDuration) {
                console.warn(`⚠️ Generated audio too short: ${duration.toFixed(2)}s for ${textLength} chars (text: "${text.substring(0, 30)}..."). Expected > ${expectedMinDuration.toFixed(2)}s.`);

                let shouldReject = false;
                if (textLength <= 20) {
                    shouldReject = duration < 0.3;
                } else if (textLength <= 50) {
                    shouldReject = duration < expectedMinDuration * 0.4;
                } else {
                    shouldReject = duration < expectedMinDuration * 0.5 || duration < 1.0;
                }

                if (shouldReject) {
                    console.error(`❌ Rejecting truncated audio: ${duration.toFixed(2)}s for ${textLength} chars (text: "${text.substring(0, 50)}...")`);
                    throw new Error(`Generated audio is too short (${duration.toFixed(2)}s) for text length (${textLength} chars)`);
                }
            }
        }

        console.log(`🎵 Audio buffer created: ${audioBuffer.duration.toFixed(2)}s`);
        return audioBuffer;
    }, [getAudioContext]);

    /**
     * Run exactly one turn on the shared socket.
     *
     * The promise settles at the turn boundary - the server's `is_transcription`
     * message - and never before, including when the caller aborts.
     *
     * That matters because the socket is shared and the server's messages carry no
     * request id. Previously an abort detached the message listener immediately
     * while the server was still streaming that turn; its remaining audio then
     * arrived on the *next* request's listener, which saw a stray `is_transcription`
     * and finalised with almost no chunks. Every later sentence stayed offset by
     * one turn, surfacing as "Generated audio is too short" and "No audio data
     * received". Draining to the boundary keeps the stream aligned.
     */
    const runTurn = useCallback((
        ws: WebSocket, text: string, signal?: AbortSignal, onChunk?: (pcm: ArrayBuffer) => void,
    ): Promise<NarrationResult> => {
        return new Promise<NarrationResult>((resolve, reject) => {
            const chunks: ArrayBuffer[] = [];
            let aborted = false;
            let finished = false;

            const finish = () => {
                finished = true;
                clearTimeout(timer);
                ws.removeEventListener('message', onMessage);
                ws.removeEventListener('close', onClose);
                signal?.removeEventListener('abort', onAbort);
            };

            // Stop collecting, but keep listening until the boundary arrives.
            const onAbort = () => {
                aborted = true;
                chunks.length = 0;
            };

            const timer = setTimeout(() => {
                if (finished) return;
                finish();
                reject(new Error("Timeout waiting for audio response"));
            }, TURN_TIMEOUT_MS);

            const onClose = () => {
                if (finished) return;
                finish();
                reject(new Error("WebSocket closed during audio generation"));
            };

            const onMessage = (event: MessageEvent) => {
                if (finished) return;

                let data: any;
                try {
                    data = JSON.parse(event.data);
                } catch (e) {
                    console.error("Failed to parse server message:", e);
                    return;
                }

                if (data.audio) {
                    if (!aborted) {
                        const pcm = decodeAudioChunk(data.audio);
                        chunks.push(pcm);
                        // Hand it straight on as well, for callers that play the
                        // passage as it arrives rather than waiting for the end.
                        // Never allowed to break the turn: a listener that throws
                        // would otherwise lose the whole passage.
                        if (onChunk) {
                            try { onChunk(pcm); } catch (error) {
                                console.warn('Streaming chunk listener failed:', error);
                            }
                        }
                    }
                    return;
                }

                if (!data.is_transcription) return;

                // Turn boundary reached - the socket is clean for the next request.
                finish();

                if (aborted) {
                    reject(new DOMException('Aborted', 'AbortError'));
                    return;
                }
                if (chunks.length === 0) {
                    console.error("❌ No audio chunks were received before transcription");
                    reject(new Error("No audio data received."));
                    return;
                }
                try {
                    // `text` on the boundary message is the session's own output
                    // transcription: the words the model actually spoke.
                    const spokenText = typeof data.text === 'string' ? data.text.trim() : '';
                    resolve({ buffer: buildAudioBuffer(chunks, text), spokenText });
                } catch (error) {
                    reject(error as Error);
                }
            };

            signal?.addEventListener('abort', onAbort);
            ws.addEventListener('message', onMessage);
            ws.addEventListener('close', onClose);

            ws.send(JSON.stringify({
                realtime_input: {
                    media_chunks: [{ mime_type: "text/plain", data: text.trim() }],
                    turn_complete: true
                }
            }));
        });
    }, [buildAudioBuffer]);

    /**
     * Close this lane's socket once it has narrated its quota, so its next turn
     * starts a clean Gemini session with no accumulated audio context.
     *
     * Done between turns, never during one: each lane's chain is serialised, so
     * by the time this runs the turn has reached its boundary and nothing is
     * streaming. Lanes count and recycle independently - each one's context is
     * its own, so retiring one leaves the other mid-session and untouched.
     */
    const retireSessionIfExhausted = useCallback((lane: Lane) => {
        lane.turns += 1;
        if (lane.turns < MAX_TURNS_PER_SESSION) return;

        const ws = lane.socket;
        lane.turns = 0;
        lane.socket = null;
        lane.connecting = null;
        if (ws && ws.readyState === WebSocket.OPEN) {
            console.log(`♻️ Recycling Live session after ${MAX_TURNS_PER_SESSION} passages to keep context clean`);
            try { ws.close(1000, 'context refresh'); } catch { /* already closing */ }
        }
    }, []);

    const generateAudioForSentence = useCallback((
        text: string, signal?: AbortSignal, onChunk?: (pcm: ArrayBuffer) => void,
    ): Promise<NarrationResult> => {
        if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));

        // Send this turn down the emptiest lane. Ties go to the first lane, so
        // two requests made back to back land on different lanes and genuinely
        // overlap rather than queueing behind one another.
        const lanes = getLanes();
        const lane = lanes.reduce((best, next) => (next.depth < best.depth ? next : best), lanes[0]);
        lane.depth += 1;

        // Retries live inside the queued task. Re-entering generateAudioForSentence
        // to retry would queue the attempt behind the very turn that is waiting on
        // it, deadlocking the chain.
        const run = async (): Promise<NarrationResult> => {
            for (let attempt = 0; ; attempt++) {
                if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');

                let ws: WebSocket;
                try {
                    ws = await getOrCreateWebSocket(lane);
                } catch (error) {
                    if (attempt < MAX_RETRIES) {
                        console.log(`🔄 WebSocket creation failed, retrying (${attempt + 1}/${MAX_RETRIES}) in 2 seconds...`);
                        await delay(RETRY_DELAY_MS);
                        continue;
                    }
                    console.error(`❌ WebSocket creation failed after ${attempt} retries`);
                    throw error;
                }

                try {
                    const result = await runTurn(ws, text, signal, onChunk);
                    retireSessionIfExhausted(lane);
                    return result;
                } catch (error) {
                    const name = (error as Error).name;
                    const message = (error as Error).message ?? '';
                    const isSocketDrop = message.includes('WebSocket closed during audio generation');

                    if (name !== 'AbortError' && isSocketDrop && attempt < MAX_RETRIES) {
                        console.log(`🔄 WebSocket closed during generation, retrying (${attempt + 1}/${MAX_RETRIES}) in 2 seconds...`);
                        await delay(RETRY_DELAY_MS);
                        continue;
                    }
                    throw error;
                }
            }
        };

        // Queue behind whatever turn is already in flight *on this lane*, whether
        // it succeeded or not, and keep the chain itself un-rejectable so one
        // failure cannot break every later sentence.
        const queued = lane.chain.then(run, run);
        lane.chain = queued.then(() => { }, () => { });
        // Release the lane's slot once the turn settles, however it settled, so
        // balancing keeps working after a failed or aborted passage.
        queued.then(
            () => { lane.depth -= 1; },
            () => { lane.depth -= 1; },
        );
        return queued;
    }, [getLanes, getOrCreateWebSocket, runTurn, retireSessionIfExhausted]);

    return {
        wsState,
        generateAudioForSentence
    };
};
