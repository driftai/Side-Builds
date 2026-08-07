import React, { useState, useEffect } from 'react';
import { useGeminiConnectionTest } from '../hooks/useGeminiConnectionTest';
import type { GeminiApiConfig } from '../types/gemini';

// Preserve the component module's established type export.
export type { GeminiApiConfig } from '../types/gemini';

interface GeminiAudiobookApiConfigProps {
  onConfigChange: (config: GeminiApiConfig) => void;
  /** Stop the tool using Gemini until it is deliberately allowed back. */
  onDisconnect?: () => void;
  /** Allow it again, after a disconnect. */
  onAllowConnections?: () => void;
  /** True once Disconnect has been pressed and nothing may connect. */
  connectionsBlocked?: boolean;
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
  onAllowConnections,
  connectionsBlocked = false,
  isConnected = false,
  initialConfig
}) => {
  const [config, setConfig] = useState<GeminiApiConfig>(initialConfig || DEFAULT_CONFIG);
  const [isExpanded, setIsExpanded] = useState(false);

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

  const {
    testStatus,
    testMessage,
    ttsText,
    setTtsText,
    isSpeaking,
    handleTestConnection,
    handleTestTTS
  } = useGeminiConnectionTest({ config, onAllowConnections });

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

              {onDisconnect && (
                // A stop rather than a tidy-up, so it does not wait for
                // something to be connected: pressing it closes whatever is open
                // and bars anything from opening after. Test Connection lifts it.
                <button
                  onClick={onDisconnect}
                  disabled={connectionsBlocked}
                  title={connectionsBlocked
                    ? 'Gemini is disconnected. Test Connection allows it again.'
                    : 'Close any live session and block further use of the Gemini API until you reconnect.'}
                  className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${connectionsBlocked
                    ? 'border border-gray-700 text-gray-600 cursor-not-allowed'
                    : 'border border-red-700 text-red-300 hover:bg-red-900/30'
                    }`}
                >
                  {connectionsBlocked ? 'Disconnected' : 'Disconnect'}
                </button>
              )}

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
