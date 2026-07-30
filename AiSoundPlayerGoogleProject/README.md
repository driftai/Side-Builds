# AI Sound Player - Real-time Music Generation App

This is a real-time AI music generation application built with Google's Lyria-realtime-exp model, featuring MIDI control, dynamic prompt management, and live audio visualization.

## Run Locally

**Prerequisites:**  Node.js

1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

## Architecture Overview

The application uses a modular component architecture built with LitElement, where each component is self-contained in its own folder within `AudioGenerator-tsx-Components/`.

## Component Structure

### AudioGenerator-tsx-Components/

The main component library organized into specialized functional modules:

#### 🎛️ **UI Components**
- **`CircularButton-Component/`** - Base class for circular styled buttons with shadow effects and hover animations
- **`PlayPauseButton-Component/`** - Main play/pause control button with loading states (stopped, playing, loading, paused)
- **`VolumeButton-Component/`** - Master volume control with drag/wheel interaction and visual feedback
- **`WeightKnob-Component/`** - Individual prompt weight controls with color-coded visual feedback
- **`ControlButtonsPanel-Component/`** - Top panel containing MIDI toggle, settings, and volume controls
- **`PromptGrid-Component/`** - 4x4 grid layout for prompt controllers
- **`PromptController-Component/`** - Individual prompt input with MIDI CC mapping, weight knob, and text editing
- **`SettingsPanel-Component/`** - Settings interface for playback duration, fade controls, presets, and audio configuration
- **`ToastMessage-Component/`** - Notification system for user feedback messages
- **`StatusMessage-Component/`** - Status display for connection states and system messages
- **`MainContainer-Component/`** - Root container with full viewport coverage and dynamic background rendering

#### 🎵 **Audio & Visualization**
- **`AudioAnalyser-Component/`** - Web Audio API analyzer for frequency data extraction and audio level monitoring
- **`AudioLevelMonitor-Component/`** - Real-time audio level monitoring and waveform visualization coordination using requestAnimationFrame
- **`WaveformVisualizer-Component/`** - Multi-mode audio visualization (frequency bars, waveform, circle, spectrogram, peaks, audio track)
- **`FrequencyHistoryManager-Component/`** - Manages frequency data storage and history for spectrogram and visualization features with automatic trimming and event dispatching
- **`AudioContextManager-Component/`** - Manages AudioContext lifecycle, suspension/resume, and browser interaction requirements
- **`AudioBufferHandler-Component/`** - Handles real-time audio buffer processing, underrun detection, and audio source scheduling for streaming music with optimized buffer management
- **`RecordingController-Component/`** - Audio recording functionality with stream capture and download capabilities
- **`PeakHandler-Component/`** - Handles peak click event processing and prompt weight updates for interactive frequency visualization
- **`PeakInteractionController-Component/`** - Handles interactive peak clicks in waveform visualization, updating prompt weights based on frequency peaks.

#### 🎛️ **MIDI & Control**
- **`MidiDispatcher-Component/`** - MIDI device access, input selection, and CC message routing
- **`MidiUIController-Component/`** - MIDI UI state management, device toggling, input selection handling, and MIDI device state synchronization

#### 🔧 **Audio Processing Controllers**
- **`FadeController-Component/`** - Audio fade-in/fade-out effects with configurable duration
- **`FadeSettingsHandler-Component/`** - 🆕 Manages fade-in and fade-out duration settings and coordinates updates with FadeController for centralized fade timing control
- **`PlaybackController-Component/`** - Centralized playback control logic for play, pause, stop, and play/pause toggle operations with session management
- **`PlayPauseHandler-Component/`** - Handles play/pause button interactions, state synchronization, and delegation to PlaybackController
- **`PlaybackDurationController-Component/`** - Manages timed vs indefinite playback sessions with automatic stopping
- **`SessionController-Component/`** - 🆕 Central session lifecycle management including LiveMusicSession connection, disconnection recovery, timeout handling, and automatic reconnection logic with integration to other controllers
- **`ConnectionController-Component/`** - Handles WebSocket connection management, reconnection logic, and error recovery
- **`MusicConfigController-Component/`** - Real-time music generation parameters (BPM, density, brightness, guidance, temperature, bass/drums muting, musical scale)

#### 📊 **Data Management**
- **`PromptManager-Component/`** - Central prompt state management, filtering, and session synchronization
- **`PresetController-Component/`** - Centralizes preset logic, handling the saving, loading, and deleting of prompt configurations by coordinating between the UI (`SettingsPanel`) and storage (`SettingsPersistence`).
- **`PresetManager-Component/`** - Save/load/delete functionality for prompt configurations
- **`PromptDefaults-Component/`** - Default prompt configurations and localStorage persistence
- **`SessionTimer-Component/`** - Session duration tracking and display formatting
- **`SettingsPersistence-Component/`** - localStorage management for master volume and preset data with validation and error handling
- **`MasterVolumeController-Component/`** - Master volume control coordination between audio nodes, fade controller, and settings persistence

#### 🎨 **Visual Effects**
- **`BackgroundGenerator-Component/`** - Dynamic radial gradient background based on active prompt weights and colors
- **`ColorBlender-Component/`** - Weighted color blending utility for visual feedback based on active prompts

#### ⚙️ **Utilities & Initialization**
- **`AppInitializer-Component/`** - Application bootstrap and dependency injection
- **`AppViewportManager-Component/`** - 🆕 Handles viewport initialization, layout setup, and app-level display configuration by coordinating with ViewportController for full-screen application display
- **`DependencyInitializer-Component/`** - Component dependency setup and cross-component communication initialization for lifecycle management
- **`SettingsCoordinator-Component/`** - 🆕 Coordinates settings application between toast messages, playback duration controller, and UI state management for centralized settings handling
- **`ThrottleUtility-Component/`** - Performance optimization utility for frequent function calls
- **`TypeDefinitions-Component/`** - Shared TypeScript interfaces and type definitions
- **`GoogleAIConfig-Component/`** - Google AI client configuration and live music session management
- **`ViewportController-Component/`** - Document-level viewport styling and layout management for full-screen application display
- **`UIStateController-Component/`** - Manages the state of the user interface components
- **`EventHandlerController-Component/`** - Centralizes simple event delegation handlers that connect UI interactions to component logic without containing business logic themselves
- **`FilteredPromptsController-Component/`** - Manages filtered prompts state and handles prompts that are rejected by the AI system with toast notifications and event dispatching
- **`OutputNodeController-Component/`** - Coordinates updates to all dependent audio components when the main audio output node is recreated, ensuring proper audio routing and volume application

#### 📁 **Main Export**
- **`AudioGenerator-tsx-Components.tsx`** - Central export file that aggregates all components for easy importing
- **`MainComponent-Component/`** - The core PromptDjMidi component that orchestrates the application, managing state and rendering child components.

## Key Features

### 🎼 **Real-time Music Generation**
- Powered by Google's Lyria-realtime-exp model
- WebSocket-based streaming audio with buffer management
- Dynamic prompt weighting and real-time parameter control

### 🎹 **MIDI Integration**
- Live MIDI device detection and selection
- CC (Control Change) mapping for prompt weights
- MIDI learn mode for easy controller setup

### 🎨 **Interactive Visualization**
- Multiple visualization modes (frequency, waveform, spectrogram, etc.)
- Interactive frequency peak clicking
- Dynamic background effects responding to audio

### ⚙️ **Advanced Audio Controls**
- Configurable fade-in/fade-out effects
- Timed session management
- Audio recording and download
- Master volume control

### 💾 **Preset Management**
- Save and load prompt configurations
- Session persistence with localStorage
- Preset deletion and organization

## Technical Notes

Based on the search results on the lyria-realtime-exp google audio model, particularly the "Music generation | Gemini API | Google AI for Developers" page 1, the model itself doesn't have a fixed duration limit like 10 minutes for a single output. Instead, it operates on a persistent, bidirectional, low-latency streaming connection using WebSockets. You control the start, pause, and stop of the music generation programmatically.

Api key has already been set in a hidden file thats called .env.local