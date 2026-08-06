import React, { useState, useEffect, useCallback, useRef } from 'react';

export interface GeminiApiConfig {
  apiKey: string;
  model: string;
  allowModelOverride: boolean;
  temperature: number;
  maxTokens: number;
  timeout: number;
  websocketUrl: string;
  voice: string;
  instructions: string;
}

interface GeminiAudiobookApiConfigProps {
  onConfigChange: (config: GeminiApiConfig) => void;
  /** Close the narration sessions. Omitted where there is nothing to close. */
  onDisconnect?: () => void;
  /** Whether a narration session is currently open. */
  isConnected?: boolean;
  initialConfig?: GeminiApiConfig;
}

const DEFAULT_CONFIG: GeminiApiConfig = {
  apiKey: '',
  model: 'gemini-2.5-flash-native-audio-preview-09-2025',
  allowModelOverride: false,
  temperature: 0.7,
  maxTokens: 4096,
  timeout: 30000,
  websocketUrl: 'ws://localhost:9083',
  voice: 'Aoede',
  instructions: ''
};

// Verified against the Live API on 2026-08-03. Models are only usable here if
// they support bidiGenerateContent; the previous entries (2.0-flash-live-001,
// 2.0-flash-exp, 1.5-flash, 1.5-pro) have all been retired from the Live API.
const AVAILABLE_MODELS = [
  'gemini-2.5-flash-native-audio-preview-09-2025',
  'gemini-2.5-flash-native-audio-preview-12-2025',
  'gemini-2.5-flash-native-audio-latest',
  'gemini-3.1-flash-live-preview'
];

const GeminiAudiobookApiConfig: React.FC<GeminiAudiobookApiConfigProps> = ({
  onConfigChange,
  onDisconnect,
  isConnected = false,
  initialConfig
}) => {
  const [config, setConfig] = useState<GeminiApiConfig>(initialConfig || DEFAULT_CONFIG);
  const [isExpanded, setIsExpanded] = useState(false);

  // Testing State
  const [testStatus, setTestStatus] = useState<'idle' | 'connecting' | 'success' | 'error'>('idle');
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

  // Update local config when initialConfig prop changes
  useEffect(() => {
    if (initialConfig) {
      setConfig(initialConfig);
    }
  }, [initialConfig]);

  // Load configuration from localStorage on mount
  useEffect(() => {
    try {
      const savedConfig = localStorage.getItem('geminiAudiobookConfig');
      if (savedConfig) {
        const parsedConfig = JSON.parse(savedConfig);
        const mergedConfig = { ...DEFAULT_CONFIG, ...parsedConfig };

        // A saved model outlives the model itself. Anything no longer in
        // AVAILABLE_MODELS has been retired from the Live API and would fail
        // every session, so fall back to the current default instead.
        if (!AVAILABLE_MODELS.includes(mergedConfig.model)) {
          console.warn(
            `Saved model "${mergedConfig.model}" is no longer available; ` +
            `falling back to ${DEFAULT_CONFIG.model}`
          );
          mergedConfig.model = DEFAULT_CONFIG.model;
          mergedConfig.allowModelOverride = DEFAULT_CONFIG.allowModelOverride;
          localStorage.setItem('geminiAudiobookConfig', JSON.stringify(mergedConfig));
        }

        setConfig(mergedConfig);
        onConfigChange(mergedConfig);
      } else {
        onConfigChange(DEFAULT_CONFIG);
      }
    } catch (error) {
      console.error('Failed to load saved config from localStorage:', error);
      onConfigChange(DEFAULT_CONFIG);
    }
  }, [onConfigChange]);

  const handleConfigChange = (field: keyof GeminiApiConfig, value: string | number | boolean) => {
    // Special handling for API key to prevent corruption
    if (field === 'apiKey' && typeof value === 'string') {
      if (value.includes('\n') || value.length > 100) {
        return;
      }
    }

    const newConfig = { ...config, [field]: value };

    // Auto-enable model override when user selects a non-default model
    if (field === 'model' && typeof value === 'string' && value !== DEFAULT_CONFIG.model) {
      newConfig.allowModelOverride = true;
    }

    // Reset model to server default when override is turned off
    if (field === 'allowModelOverride' && value === false) {
      newConfig.model = DEFAULT_CONFIG.model;
    }

    setConfig(newConfig);
    onConfigChange(newConfig);

    try {
      localStorage.setItem('geminiAudiobookConfig', JSON.stringify(newConfig));
    } catch (error) {
      console.error('Failed to save configuration to localStorage:', error);
    }
  };

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
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'disconnect' }));
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
      // Cleanup on unmount
      if (testWsRef.current) {
        testWsRef.current.close();
      }
    };
  }, []);

  // Test Connection Function
  const handleTestConnection = useCallback(() => {
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
        const initMessage = {
          type: 'init',
          voice: config.voice,
          model: config.model,
          allowModelOverride: config.allowModelOverride,
          apiKey: config.apiKey,
          instructions: "Test connection",
          sequentialAudioPlay: false
        };
        ws.send(JSON.stringify(initMessage));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.is_system_message) {
            setTestMessage(`Server: ${data.text}`);
            // Left open deliberately. It used to close itself a second after the
            // handshake, which contradicted both the server's own message and
            // the Disconnect button beside it: the panel said the session would
            // remain active while the socket had already gone, so there was
            // never anything for Disconnect to close. Narration still takes the
            // slot back when it needs one - it asks for this socket to close
            // before opening its own.
            setTestConnected(true);
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
        ws.send(JSON.stringify({
          type: 'init',
          voice: config.voice,
          model: config.model,
          allowModelOverride: config.allowModelOverride,
          apiKey: config.apiKey,
          instructions: "You are a helpful assistant.",
          sequentialAudioPlay: false
        }));

        // Then send text
        setTimeout(() => {
          ws.send(JSON.stringify({
            realtime_input: {
              media_chunks: [{ mime_type: "text/plain", data: ttsText }],
              turn_complete: true
            }
          }));
        }, 500);
      };

      const audioChunks: ArrayBuffer[] = [];

      ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("TTS Test: Received message", data); // DEBUG LOG

          if (data.audio) {
            console.log("TTS Test: Received audio chunk"); // DEBUG LOG
            setTestStatus('Receiving audio...');

            try {
              const audioData = atob(data.audio);
              const arrayBuffer = new ArrayBuffer(audioData.length);
              const view = new Uint8Array(arrayBuffer);
              for (let i = 0; i < audioData.length; i++) {
                view[i] = audioData.charCodeAt(i);
              }
              audioChunks.push(arrayBuffer);
              console.log(`TTS Test: Chunk buffered. Total chunks: ${audioChunks.length}`);

            } catch (e) {
              console.error("TTS Test: Error buffering audio", e);
            }
          } else if (data.is_transcription || data.turn_complete) {
            console.log("TTS Test: Turn complete, processing full audio...");
            setTestStatus('Processing audio...');

            if (audioChunks.length === 0) {
              console.log("TTS Test: No audio chunks to play.");
              setTestStatus('No audio received.');
              ws.close();
              return;
            }

            try {
              // Calculate total length
              const totalLength = audioChunks.reduce((acc, chunk) => acc + chunk.byteLength, 0);
              const combinedBuffer = new Uint8Array(totalLength);
              let offset = 0;
              for (const chunk of audioChunks) {
                combinedBuffer.set(new Uint8Array(chunk), offset);
                offset += chunk.byteLength;
              }

              console.log("TTS Test: Full PCM data assembled", combinedBuffer.byteLength);

              if (audioContext.state === 'suspended') {
                await audioContext.resume();
              }

              // Manual PCM Decoding (Int16 -> Float32)
              const pcmData = new Int16Array(combinedBuffer.buffer);
              const audioBuffer = audioContext.createBuffer(1, pcmData.length, 24000);
              const channelData = audioBuffer.getChannelData(0);

              for (let i = 0; i < pcmData.length; i++) {
                channelData[i] = pcmData[i] / 32768.0;
              }

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

  return (
    <div className="w-full bg-gray-800/50 rounded-lg border border-gray-600">
      {/* Compact Header - Always Visible */}
      <div
        className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-700/30 transition-colors rounded-lg"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-medium text-white">Gemini Live Audio</h3>
          {/* API Key Status */}
          {config.apiKey && config.apiKey.startsWith('AIza') && (
            <span className="text-xs text-green-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-green-400 rounded-full"></span>
              Configured
            </span>
          )}
          {/* Model Status */}
          <span className={`text-xs flex items-center gap-1 ${config.allowModelOverride ? 'text-green-400' : 'text-blue-400'
            }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${config.allowModelOverride ? 'bg-green-400' : 'bg-blue-400'
              }`}></span>
            {config.allowModelOverride ? 'Override' : 'Default'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {!isExpanded && !config.apiKey && (
            <span className="text-xs text-gray-400">Using server key</span>
          )}
          <button className="text-gray-400 hover:text-white transition-colors text-sm">
            {isExpanded ? '▼' : '▶'}
          </button>
        </div>
      </div>

      {/* Expandable Content */}
      {isExpanded && (
        <div className="px-3 pb-3 border-t border-gray-600/50">
          {/* API Key Input */}
          <div className="mt-3 mb-3">
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs font-medium text-gray-400">
                Gemini API Key *
              </label>
              <div className="flex items-center gap-2">
                {config.apiKey && config.apiKey.startsWith('AIza') && (
                  <span className="text-xs text-green-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 bg-green-400 rounded-full"></span>
                    Saved
                  </span>
                )}
                {config.apiKey && (
                  <button
                    onClick={() => handleConfigChange('apiKey', '')}
                    className="text-xs text-red-400 hover:text-red-300 transition-colors px-1.5 py-0.5 border border-red-600 rounded-sm"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
            <form onSubmit={(e) => e.preventDefault()}>
              <input
                type="password"
                placeholder="Enter your Gemini API key (starts with AIza)"
                value={config.apiKey}
                onChange={(e) => handleConfigChange('apiKey', e.target.value)}
                className="w-full bg-gray-700 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </form>
            <p className="text-xs text-gray-500 mt-1">
              Required for speech generation. Key is stored locally in your browser.
            </p>
          </div>

          {/* WebSocket URL */}
          <div className="mb-3">
            <label className="block text-xs font-medium text-gray-400 mb-1">
              WebSocket URL
            </label>
            <input
              type="text"
              value={config.websocketUrl}
              onChange={(e) => handleConfigChange('websocketUrl', e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Model Selection */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-medium text-gray-400">
                Model Selection
              </label>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="allowModelOverride"
                  checked={config.allowModelOverride}
                  onChange={(e) => handleConfigChange('allowModelOverride', e.target.checked)}
                  className="w-3 h-3 text-blue-600 bg-gray-700 border-gray-600 rounded-sm focus:ring-blue-600 ring-offset-gray-800"
                />
                <label htmlFor="allowModelOverride" className="ml-2 text-xs text-gray-400">
                  Override Server Default
                </label>
              </div>
            </div>

            <select
              value={config.model}
              onChange={(e) => handleConfigChange('model', e.target.value)}
              disabled={!config.allowModelOverride}
              className={`w-full bg-gray-700 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent ${!config.allowModelOverride ? 'opacity-50 cursor-not-allowed' : ''
                }`}
            >
              {AVAILABLE_MODELS.map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>

          {/* Connection Testing Section */}
          <div className="mt-4 pt-3 border-t border-gray-600/50">
            <h4 className="text-xs font-medium text-gray-300 mb-2">Connection Test</h4>

            <div className="flex gap-2 mb-2">
              <button
                onClick={handleTestConnection}
                disabled={testStatus === 'connecting'}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${testStatus === 'connecting'
                  ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-500 text-white'
                  }`}
              >
                {testStatus === 'connecting' ? 'Connecting...' : 'Test Connection'}
              </button>

              {onDisconnect && (() => {
                // Anything holding a session counts, whether it was opened by
                // narration or from this panel.
                const anythingConnected = isConnected || testConnected;
                return (
                  <button
                    onClick={onDisconnect}
                    disabled={!anythingConnected}
                    title={anythingConnected
                      ? 'Close every live session and free the API. Narration reconnects on the next passage.'
                      : 'Nothing is connected'}
                    className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${anythingConnected
                      ? 'border border-red-700 text-red-300 hover:bg-red-900/30'
                      : 'border border-gray-700 text-gray-600 cursor-not-allowed'
                      }`}
                  >
                    Disconnect
                  </button>
                );
              })()}

              <div className="grow">
                <input
                  type="text"
                  value={ttsText}
                  onChange={(e) => setTtsText(e.target.value)}
                  placeholder="Text to speak..."
                  className="w-full bg-gray-700 border border-gray-600 text-white rounded-sm px-2 py-1.5 text-xs focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <button
                onClick={handleTestTTS}
                disabled={isSpeaking || !ttsText}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${isSpeaking
                  ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                  : 'bg-green-600 hover:bg-green-500 text-white'
                  }`}
              >
                {isSpeaking ? 'Speaking...' : 'Speak'}
              </button>
            </div>

            {testMessage && (
              <div className={`text-xs p-2 rounded ${testStatus === 'error' ? 'bg-red-900/30 text-red-300' :
                testStatus === 'success' ? 'bg-green-900/30 text-green-300' :
                  'bg-gray-700/50 text-gray-300'
                }`}>
                {testMessage}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default GeminiAudiobookApiConfig;