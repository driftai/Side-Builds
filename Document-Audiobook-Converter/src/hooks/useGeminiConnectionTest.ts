import { useCallback, useEffect, useRef, useState } from 'react';
import type { GeminiApiConfig } from '../types/gemini';
import { createPcmAudioBuffer, decodeAudioChunk } from '../services/gemini/liveAudio';
import {
  createDisconnectMessage,
  createInitMessage,
  createTurnMessage,
  isTurnBoundaryMessage,
  parseServerMessage
} from '../services/gemini/liveProtocol';

export type GeminiConnectionTestStatus =
  | 'idle'
  | 'connecting'
  | 'success'
  | 'error'
  | 'Receiving audio...'
  | 'Processing audio...'
  | 'No audio received.'
  | 'Playing audio...'
  | 'Audio finished.'
  | `Audio error: ${string}`;

interface UseGeminiConnectionTestOptions {
  config: GeminiApiConfig;
  onAllowConnections?: () => void;
}

/**
 * Owns the short-lived Gemini sessions opened by the configuration panel.
 *
 * Keeping the socket, its close listener, and the TTS playback lifecycle in one
 * hook makes the component a view/configuration facade without changing the
 * messages or timing expected by the local WebSocket service.
 */
export const useGeminiConnectionTest = ({
  config,
  onAllowConnections
}: UseGeminiConnectionTestOptions) => {
  const [testStatus, setTestStatus] = useState<GeminiConnectionTestStatus>('idle');
  const [testMessage, setTestMessage] = useState<string>('');
  const [ttsText, setTtsText] = useState<string>('Hello, this is a test of the Gemini voice engine.');
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);
  const testWsRef = useRef<WebSocket | null>(null);
  /**
   * Whether this panel is holding a session of its own.
   *
   * Separate from the narration state the app passes in: a session opened from
   * here occupies a slot exactly like a narration lane does, so Disconnect has
   * to know about it or it sits greyed out with a live connection behind it.
   */
  const [testConnected, setTestConnected] = useState(false);

  // Listen for request to close test connection (from main app)
  useEffect(() => {
    const handleCloseRequest = () => {
      if (testWsRef.current) {
        console.log("GeminiConfig: Closing test connection due to external request");
        // Same as the narration lanes: ask the server to close the Gemini
        // session rather than just dropping the socket, or the slot for this
        // key stays reserved on the service side after we have gone.
        const ws = testWsRef.current;
        try {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(createDisconnectMessage()));
          }
        } catch { /* socket already going */ }
        setTimeout(() => { try { ws.close(); } catch { /* already closing */ } }, 150);
        testWsRef.current = null;
        setTestStatus('idle');
        setTestMessage('Connection closed by main app');
        setIsSpeaking(false);
        setTestConnected(false);
      }
    };

    window.addEventListener('closeGeminiTestConnection', handleCloseRequest);
    return () => {
      window.removeEventListener('closeGeminiTestConnection', handleCloseRequest);
      // Cleanup on unmount, including React StrictMode's effect replay.
      if (testWsRef.current) {
        testWsRef.current.close();
      }
    };
  }, []);

  // Test Connection Function
  const handleTestConnection = useCallback(() => {
    // Testing is the deliberate act of using the API again, so it lifts a stop.
    onAllowConnections?.();
    setTestStatus('connecting');
    setTestMessage('Connecting to WebSocket...');

    try {
      if (testWsRef.current) {
        testWsRef.current.close();
      }
      const ws = new WebSocket(config.websocketUrl);
      testWsRef.current = ws;

      const timeoutId = setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) {
          ws.close();
          setTestStatus('error');
          setTestMessage('Connection timed out. Is the server running?');
        }
      }, 5000);

      ws.onopen = () => {
        clearTimeout(timeoutId);
        setTestStatus('success');
        setTestMessage('Connected successfully!');

        // Send init message to verify API key
        const initMessage = createInitMessage(config, {
          allowModelOverride: config.allowModelOverride,
          instructions: "Test connection",
        });
        ws.send(JSON.stringify(initMessage));
      };

      ws.onmessage = (event) => {
        try {
          const data = parseServerMessage(event.data);
          if (data.is_system_message) {
            setTestMessage(`Server: ${data.text}`);
            // Closed as soon as it has proved the API answers. Holding it open
            // would keep a session alive for no reason, and a long-lived session
            // is exactly what degrades narration quality.
            setTestConnected(true);
            setTimeout(() => ws.close(), 1000);
          }
        } catch (e) {
          // Ignore parse errors for test
        }
      };

      // Only report the panel as disconnected if this is still the socket the
      // panel is using. Speaking replaces the tested connection with a new one,
      // and the old socket's close arrives *after* the replacement is live - so
      // clearing the flag unconditionally here switched Disconnect off while a
      // connection was genuinely open.
      ws.onclose = () => {
        if (testWsRef.current !== ws) return;
        testWsRef.current = null;
        setTestConnected(false);
      };

      ws.onerror = () => {
        clearTimeout(timeoutId);
        setTestStatus('error');
        setTestMessage('WebSocket connection failed.');
        if (testWsRef.current === ws) setTestConnected(false);
      };

    } catch (error) {
      setTestStatus('error');
      setTestMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }, [config]);

  // Test TTS Function
  const handleTestTTS = useCallback(() => {
    if (!ttsText.trim()) return;

    // Speaking is a deliberate use of the API, so it lifts a stop too. The stop
    // is there to prevent the tool reconnecting on its own, not to argue with a
    // button you just pressed.
    onAllowConnections?.();
    setIsSpeaking(true);
    setTestMessage('Requesting audio...');
    setTestStatus('connecting');

    try {
      if (testWsRef.current) {
        testWsRef.current.close();
      }
      const ws = new WebSocket(config.websocketUrl);
      testWsRef.current = ws;
      setTestConnected(true);
      // Speaking holds a session too, so Disconnect stays live for it and goes
      // back to grey once this socket is gone.
      ws.addEventListener('close', () => {
        // As above: a socket that has already been replaced must not report the
        // panel disconnected on its way out.
        if (testWsRef.current !== ws) return;
        testWsRef.current = null;
        setTestConnected(false);
      });
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();

      ws.onopen = () => {
        // Init first
        ws.send(JSON.stringify(createInitMessage(config, {
          allowModelOverride: config.allowModelOverride,
          instructions: "You are a helpful assistant.",
        })));

        // Then send text
        setTimeout(() => {
          ws.send(JSON.stringify(createTurnMessage(ttsText)));
        }, 500);
      };

      const audioChunks: ArrayBuffer[] = [];

      ws.onmessage = async (event) => {
        try {
          const data = parseServerMessage(event.data);
          console.log("TTS Test: Received message", data); // DEBUG LOG

          if (data.audio) {
            console.log("TTS Test: Received audio chunk"); // DEBUG LOG
            setTestStatus('Receiving audio...');

            try {
              audioChunks.push(decodeAudioChunk(data.audio));
              console.log(`TTS Test: Chunk buffered. Total chunks: ${audioChunks.length}`);

            } catch (e) {
              console.error("TTS Test: Error buffering audio", e);
            }
          } else if (isTurnBoundaryMessage(data)) {
            console.log("TTS Test: Turn complete, processing full audio...");
            setTestStatus('Processing audio...');

            if (audioChunks.length === 0) {
              console.log("TTS Test: No audio chunks to play.");
              setTestStatus('No audio received.');
              ws.close();
              return;
            }

            try {
              if (audioContext.state === 'suspended') {
                await audioContext.resume();
              }

              const audioBuffer = createPcmAudioBuffer(audioContext, audioChunks);

              console.log("TTS Test: Full audio decoded", audioBuffer.duration);

              const source = audioContext.createBufferSource();
              source.buffer = audioBuffer;
              source.connect(audioContext.destination);
              source.start(0);
              setTestStatus('Playing audio...');

              source.onended = () => {
                setTestStatus('Audio finished.');
                console.log("TTS Test: Audio finished");
                ws.close();
                setIsSpeaking(false);
              };

            } catch (e) {
              console.error("TTS Test: Error playing full audio", e);
              setTestStatus(`Audio error: ${e}`);
              ws.close();
              setIsSpeaking(false);
            }
          } else if (data.text) {
            console.log("TTS Test: Received text:", data.text);
          }
        } catch (e) {
          console.error("TTS Test: Error parsing message", e);
        }
      };

      ws.onerror = () => {
        setTestStatus('error');
        setTestMessage('TTS Connection failed');
        setIsSpeaking(false);
      };

    } catch (error) {
      setTestStatus('error');
      setTestMessage('Failed to start TTS test');
      setIsSpeaking(false);
    }
  }, [config, ttsText]);

  return {
    testStatus,
    testMessage,
    ttsText,
    setTtsText,
    isSpeaking,
    testConnected,
    handleTestConnection,
    handleTestTTS
  };
};
