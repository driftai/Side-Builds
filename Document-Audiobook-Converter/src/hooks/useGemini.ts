import { useState, useRef, useCallback, useEffect } from 'react';
import { GeminiApiConfig } from '../components/GeminiConfig';

// A turn is one request/response cycle on the shared socket. The server marks
// the end of every turn with an `is_transcription` message.
const TURN_TIMEOUT_MS = 60000;
const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 2000;
const PCM_SAMPLE_RATE = 24000;

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
    const sharedWebSocketRef = useRef<WebSocket | null>(null);
    const wsConnectionPromiseRef = useRef<Promise<WebSocket> | null>(null);
    const geminiConfigRef = useRef<GeminiApiConfig | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);

    // Serialises turns on the shared socket. The Live API runs one turn per
    // session at a time and the responses carry no request id, so two overlapping
    // requests cannot be told apart - see runTurn for the full explanation.
    const turnChainRef = useRef<Promise<unknown>>(Promise.resolve());

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

    const getOrCreateWebSocket = useCallback(async (): Promise<WebSocket> => {
        const currentConfig = geminiConfigRef.current;
        // Only the socket URL is required. The key sent here is an optional
        // override - the server resolves its own from the environment, .env.local
        // or its fallback, and reports a clear auth error if none works. Demanding
        // one here blocked the app on a field it does not actually need.
        if (!currentConfig?.websocketUrl) {
            throw new Error('Gemini WebSocket URL must be configured.');
        }

        // If we have an active connection, reuse it
        if (sharedWebSocketRef.current && sharedWebSocketRef.current.readyState === WebSocket.OPEN) {
            return sharedWebSocketRef.current;
        }

        // If a connection is already being established, wait for it
        if (wsConnectionPromiseRef.current) {
            return wsConnectionPromiseRef.current;
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
                setWsState('connecting');
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
                        setWsState('connected');
                        sharedWebSocketRef.current = ws;
                        wsConnectionPromiseRef.current = null;
                        resolve(ws);
                    }
                } catch (e) {
                    console.error("Failed to parse server message:", e);
                }
            };

            ws.onerror = () => {
                clearTimeout(initTimeout);
                setWsState('error');
                sharedWebSocketRef.current = null;
                wsConnectionPromiseRef.current = null;
                reject(new Error("WebSocket connection error"));
            };

            ws.onclose = () => {
                setWsState('disconnected');
                if (sharedWebSocketRef.current === ws) {
                    sharedWebSocketRef.current = null;
                    wsConnectionPromiseRef.current = null;
                }
            };
        });

        wsConnectionPromiseRef.current = connectionPromise;
        return connectionPromise;
    }, []);

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
    const runTurn = useCallback((ws: WebSocket, text: string, signal?: AbortSignal): Promise<AudioBuffer> => {
        return new Promise<AudioBuffer>((resolve, reject) => {
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
                        chunks.push(decodeAudioChunk(data.audio));
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
                    resolve(buildAudioBuffer(chunks, text));
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

    const generateAudioForSentence = useCallback((text: string, signal?: AbortSignal): Promise<AudioBuffer> => {
        if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));

        // Retries live inside the queued task. Re-entering generateAudioForSentence
        // to retry would queue the attempt behind the very turn that is waiting on
        // it, deadlocking the chain.
        const run = async (): Promise<AudioBuffer> => {
            for (let attempt = 0; ; attempt++) {
                if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');

                let ws: WebSocket;
                try {
                    ws = await getOrCreateWebSocket();
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
                    return await runTurn(ws, text, signal);
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

        // Queue behind whatever turn is already in flight, whether it succeeded or
        // not, and keep the chain itself un-rejectable so one failure cannot break
        // every later sentence.
        const queued = turnChainRef.current.then(run, run);
        turnChainRef.current = queued.then(() => { }, () => { });
        return queued;
    }, [getOrCreateWebSocket, runTurn]);

    return {
        wsState,
        generateAudioForSentence
    };
};
