/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import AgentEdit from './components/AgentEdit';
import ControlTray from './components/console/control-tray/ControlTray';
import DebugModal from './components/DebugModal';
import ErrorScreen from './components/demo/ErrorScreen';
import KeynoteCompanion from './components/demo/keynote-companion/KeynoteCompanion';
import Header from './components/Header';
import UserSettings from './components/UserSettings';
import WelcomeScreen from './components/WelcomeScreen';
import { LiveAPIProvider, useLiveAPIContext } from './contexts/LiveAPIContext';
import { useAgent, useUI } from './lib/state';
// Fix: Import React to resolve "Cannot find namespace 'React'" error.
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { themes } from './lib/themes';
import FloatingAvatar from './components/FloatingAvatar';
import HelpModal from './components/HelpModal';
import StorageModal from './components/StorageModal';
import ExportPackageModal from './components/ExportPackageModal';

// Minimum volume level that indicates audio output is occurring.
// This threshold prevents the avatar from reacting to negligible noise.
const AUDIO_OUTPUT_DETECTION_THRESHOLD = 0.05;

// Amount of delay in milliseconds after audio output stops before the avatar
// is considered "not talking". This creates a more natural-looking effect,
// preventing the talking animation from stopping abruptly between words.
const TALKING_STATE_COOLDOWN_MS = 2000;

/**
 * A screen for entering the Gemini API key when none is configured.
 */
function ApiKeyScreen() {
  const { setApiKey } = useUI();
  const [inputValue, setInputValue] = useState('');
  const [isVisible, setIsVisible] = useState(false);
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), 100);
    return () => clearTimeout(timer);
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (trimmed) {
      setApiKey(trimmed);
    }
  }

  return (
    <div className={`api-key-screen ${isVisible ? 'visible' : ''}`}>
      <div className="api-key-card">
        <div className="api-key-icon">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="48" height="48">
            <path
              d="M12 0L14.59 9.41L24 12L14.59 14.59L12 24L9.41 14.59L0 12L9.41 9.41L12 0Z"
              fill="currentColor"
            />
          </svg>
        </div>
        <h1 className="api-key-title">Welcome to Scribe</h1>
        <p className="api-key-subtitle">
          Enter your Gemini API key to get started. Your key is stored locally in your browser and never sent to any server.
        </p>
        <form onSubmit={handleSubmit} className="api-key-form">
          <div className="api-key-input-wrapper">
            <input
              type={showKey ? 'text' : 'password'}
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              placeholder="Paste your Gemini API key here..."
              className="api-key-input"
              autoFocus
              spellCheck={false}
              autoComplete="off"
            />
            <button
              type="button"
              className="api-key-toggle-vis"
              onClick={() => setShowKey(!showKey)}
              title={showKey ? 'Hide key' : 'Show key'}
            >
              <span className="icon">{showKey ? 'visibility_off' : 'visibility'}</span>
            </button>
          </div>
          <button type="submit" className="api-key-submit" disabled={!inputValue.trim()}>
            <span>Get Started</span>
            <span className="icon" style={{ fontSize: 20 }}>arrow_forward</span>
          </button>
        </form>
        <p className="api-key-hint">
          Get a free API key from{' '}
          <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer">
            Google AI Studio
          </a>
        </p>
      </div>
    </div>
  );
}

/**
 * Renders the main content of the application, including the header, modals,
 * the draggable agent avatar, the primary app area (KeynoteCompanion), and the control tray.
 */
function AppContent() {
  const { showUserConfig, showAgentEdit, showDebugModal, showHelpModal, showStorageModal, showExportPackageModal } =
    useUI();

  return (
    <>
      <ErrorScreen />
      <Header />

      <FloatingAvatar />

      {/* Conditionally render modals based on UI state */}
      {showUserConfig && <UserSettings />}
      {showAgentEdit && <AgentEdit />}
      {showDebugModal && <DebugModal />}
      {showHelpModal && <HelpModal />}
      {showStorageModal && <StorageModal />}
      {showExportPackageModal && <ExportPackageModal />}
      <div className="streaming-console">
        <main>
          <div className="main-app-area">
            <KeynoteCompanion />
          </div>

          <ControlTray></ControlTray>
        </main>
      </div>
    </>
  );
}

/**
 * Main application component. It checks for the required API key, sets up the
 * global theme, and provides the LiveAPI context to its children.
 */
function App() {
  const { apiKey, showWelcomeScreen, theme, font } = useUI();

  // This effect applies the selected theme's colors as CSS variables to the root element,
  // allowing for dynamic theming of the entire application.
  useEffect(() => {
    const selectedTheme = themes.find(t => t.name === theme) || themes[0];
    const root = document.documentElement;
    root.style.setProperty('--theme-bg', selectedTheme.colors[0]);
    root.style.setProperty('--theme-surface', selectedTheme.colors[1]);
    root.style.setProperty('--theme-accent', selectedTheme.colors[2]);
    root.style.setProperty('--theme-text', selectedTheme.colors[3]);
    root.style.setProperty('--theme-document-bg', selectedTheme.colors[4]);
  }, [theme]);

  // This effect applies the selected font as a CSS variable to the root element.
  useEffect(() => {
    document.documentElement.style.setProperty('--font-document', font);
  }, [font]);

  // If no API key is set, show the key entry screen
  if (!apiKey) {
    return <ApiKeyScreen />;
  }

  return (
    <div className="App">
      {showWelcomeScreen && <WelcomeScreen />}
      <LiveAPIProvider apiKey={apiKey}>
        <AppContent />
      </LiveAPIProvider>
    </div>
  );
}

export default App;
