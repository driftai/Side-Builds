# Gemini API Integration for PDF Audiobook Converter

This document describes the integration of Google's Gemini API with the PDF to Audiobook Converter application.

## Overview

The application now includes a comprehensive Gemini API configuration system that allows users to:

- Configure API keys and model settings
- Test API connectivity
- Save/load configurations
- Access various Gemini models for future AI-powered features
- Manage voice and audio settings

## Architecture

### Components

1. **GeminiAudiobookApiConfig.tsx** - Main configuration component
2. **geminiApiService.ts** - Service layer for API interactions
3. **App.tsx** - Main application with integrated configuration

### File Structure

```
Original-Base-Of-pdf-to-audiobook-converter-natural-tts/
├── GeminiAudiobookApiConfig.tsx          # Main config component
├── App.tsx                               # Main app with integration
├── src/
│   ├── services/
│   │   └── geminiApiService.ts          # API service layer
│   └── types/
│       └── google-generative-ai.d.ts    # Type definitions
├── package.json                         # Dependencies
└── GEMINI_INTEGRATION_README.md         # This documentation
```

## Features

### Configuration Management

- **API Key Management**: Secure storage and validation
- **Model Selection**: Support for multiple Gemini models
- **Voice Settings**: Language, voice type, speed, and pitch control
- **Audio Settings**: Format, sample rate, and channel configuration
- **Timeout & Retry**: Configurable connection settings

### Test Audio Generation

- **Live API Simulation**: Test text-to-speech generation in browser
- **Real-time Feedback**: See generation progress and results
- **Voice Configuration**: Test different voices and settings
- **Performance Monitoring**: Track response times and success rates
- **Preset Examples**: Quick test with sample text and pangrams
- **Automatic Speech Synthesis**: Generated text is automatically spoken aloud
- **Speech Controls**: Play, pause, stop, and adjust speech settings
- **Voice Selection**: Choose from available browser speech voices
- **Speech Parameters**: Adjust rate, pitch, and volume in real-time

### Live API Test Generation

The test generation feature simulates how the Gemini Live API works for text-to-speech:

#### Browser Simulation
- Uses Gemini text generation API as proxy
- Simulates the audio generation process
- Provides timing and performance metrics
- Shows how voice configurations affect output

#### Full Live API Implementation
For actual audio generation (as used in the audiobook converter):
- Connects to Gemini Live API via WebSocket
- Sends text and receives audio chunks in real-time
- Uses voice configurations from the API settings
- Supports streaming audio playback
- Requires server-side implementation

#### Integration Points
- **Configuration**: Same settings used for both test and production
- **Monitoring**: Both generate logs to the monitoring system
- **Voice Settings**: Applied consistently across implementations
- **Error Handling**: Same error reporting and recovery patterns

### Available Models

- `gemini-2.0-flash-exp` - Gemini 2.0 Flash (Experimental)
- `gemini-1.5-flash` - Gemini 1.5 Flash
- `gemini-1.5-pro` - Gemini 1.5 Pro
- `gemini-2.5-flash-preview-native-audio-dialog` - Gemini 2.5 Flash (Audio Dialog)

### Voice Options

- **Languages**: English (US/UK), Spanish, French, German, Italian, Japanese, Korean, Chinese
- **Voice Types**: Natural, Male, Female, Neutral, Aoede, Charon, Fenrir, Kore

### API Connection Testing

- Real-time connection validation
- Detailed error reporting
- Status indicators
- Automatic retry logic

## Usage

### Basic Setup

1. **Get API Key**: Visit [Google AI Studio](https://makersuite.google.com/app/apikey) to obtain your API key

2. **Configure Settings**:
   - Click "Show Gemini API Configuration" in the app header
   - Enter your API key
   - Select your preferred model
   - Adjust generation settings (temperature, max tokens)
   - Configure voice and audio settings

3. **Test Connection**: Click "Test Connection" to verify your setup

4. **Test Audio Generation**: Use the "Test Audio Generation" section to:
   - Enter text in the textarea
   - Click "Generate Test Audio" to test the API
   - Try preset examples for quick testing
   - Monitor performance and status messages
   - Listen to generated text spoken automatically
   - Adjust speech settings (voice, rate, pitch, volume)
   - Use speech controls (speak, pause, stop)

5. **Save Configuration**: Use "Save Config" to persist your settings

### Advanced Configuration

#### Generation Settings
- **Temperature**: Controls creativity (0.0 = conservative, 2.0 = creative)
- **Max Tokens**: Limits response length (1024-8192)
- **Timeout**: Connection timeout in milliseconds
- **Retry Attempts**: Number of retry attempts for failed requests

#### Voice Configuration
- **Language**: Target language for speech synthesis
- **Voice Type**: Voice characteristics (natural, male, female, etc.)
- **Speed**: Speech rate (0.5x to 2.0x)
- **Pitch**: Voice pitch adjustment (-1.0 to +1.0)

#### Audio Settings
- **Format**: Output audio format (WAV, MP3, OGG)
- **Sample Rate**: Audio quality (22kHz, 44kHz, 48kHz)
- **Channels**: Mono or stereo output

## Integration Points

### App.tsx Integration

The main App.tsx file includes:

```typescript
// Gemini API state management
const [geminiClient, setGeminiClient] = useState<GoogleGenerativeAI | null>(null);
const [geminiConfig, setGeminiConfig] = useState<GeminiApiConfig | null>(null);

// Configuration handlers
const handleGeminiConfigChange = useCallback((config: GeminiApiConfig) => {
  setGeminiConfig(config);
  geminiApiService.initializeClient(config);
  // Additional setup logic
}, []);

const handleGeminiClientReady = useCallback((client: GoogleGenerativeAI | null) => {
  setGeminiClient(client);
}, []);
```

### Service Layer

The `geminiApiService.ts` provides:

- Client initialization and management
- Connection testing functionality
- Configuration persistence
- Error handling and retry logic

## Gemini Live API Integration

### Overview

The latest version includes full integration with Gemini Live API for real-time text-to-speech streaming. This provides a more sophisticated and responsive experience compared to the standard TTS API.

### Features

#### Real-Time Streaming
- **Sentence-by-Sentence Processing**: Each sentence is processed individually for better control
- **Live Audio Streaming**: Audio is generated and played in real-time
- **WebSocket Communication**: Uses WebSocket for efficient bidirectional communication
- **Automatic Fallback**: Falls back to browser TTS if Live API fails

#### Visual Indicators
- **Connection Status**: Real-time WebSocket connection status (🟢 Connected, 🟡 Connecting, 🔴 Error, ⚪ Disconnected)
- **Voice Engine Toggle**: Visual toggle between Browser TTS and Gemini Live API
- **Live Playback Indicator**: Shows when Gemini is actively speaking
- **Error Display**: User-friendly error messages with automatic clearing

#### Audio Playback
- **Smooth Transitions**: Seamless playback between sentences
- **High-Quality Audio**: Uses Gemini's advanced voice synthesis
- **Multiple Voices**: Support for Aoede, Charon, Fenrir, Kore, and Puck
- **Real-Time Processing**: No waiting for full audio generation

### Setup Instructions

#### 1. Prerequisites
- **GeminiEngine Server**: Must be installed at `backend`
- **Python 3.8+**: Required for the GeminiEngine server
- **Node.js v18+**: Required for the React app

#### 2. Start the Complete System
Use the provided startup script:
```bash
start_with_gemini_live.bat
```

This will start:
- **GeminiEngine Server**: `ws://localhost:9083` (centralized WebSocket server)
- **Status Server**: `http://localhost:9084/status` (for monitoring)
- **React App**: `http://localhost:5173` (main application)

**Note**: The audiobook app now uses the centralized GeminiEngine server instead of running its own WebSocket server. This provides:
- Better session management
- Unified connection handling
- Reduced code duplication
- Centralized monitoring and logging

Alternatively, you can start the servers individually:

**Option 1: Start GeminiEngine server only**
```bash
cd backend
python main.py
```

**Option 2: Start React app only**
```bash
npm run dev
```

#### 3. Configure Gemini API
1. Open the app and click "Show Gemini API Configuration"
2. Enter your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
3. Configure your preferred model and voice settings
4. The WebSocket will auto-connect when you switch to Gemini mode

#### 4. Upload and Play
1. Upload a PDF document
2. Toggle to "Gemini Live API" mode
3. Select your preferred voice (Aoede, Charon, etc.)
4. Click play to start real-time audiobook playback

### Technical Architecture

#### GeminiEngine Server (Centralized)
Located at `backend`, the server provides:
- **Session Management**: Handles concurrent session limits and cleanup
- **WebSocket Handling**: Manages multiple client connections
- **Audio Processing**: Converts and streams audio data
- **Status Monitoring**: Real-time server status and metrics
- **Error Recovery**: Automatic reconnection and retry logic

#### Client Integration (`App.tsx`)
- WebSocket connection management (single shared connection)
- Real-time audio playback
- Error handling and automatic retry
- Visual status indicators
- Automatic test connection cleanup

#### Audio Processing
- Base64 audio decoding
- Web Audio API integration
- Smooth sentence transitions
- Playback queue management
- Automatic reconnection on failures

### Troubleshooting

#### WebSocket Connection Issues
- Ensure the GeminiEngine server is running: `cd backend && python main.py`
- Check that your firewall allows WebSocket connections on port 9083
- Verify the Gemini API key is configured correctly
- **Fixed**: Session limit issues resolved with centralized server
- **Fixed**: Race conditions between test and audiobook connections eliminated
- **Fixed**: Automatic retry logic with proper delays
- Check server logs at `backend` for detailed error messages

#### Audio Playback Issues
- Check browser audio permissions
- Ensure Web Audio API is supported
- Try refreshing the page if audio doesn't play

#### API Errors
- Verify your Gemini API key is valid
- Check your API quota and usage limits
- Ensure you have the correct permissions for Live API

### Monitoring

#### Server Status
Check the status endpoint: `http://localhost:9084/status`

#### Client Logs
Monitor the browser console for detailed logging of:
- WebSocket connection events
- Audio processing status
- Error messages and recovery actions

## Future Enhancements

### Planned Features

1. **AI-Powered Text Enhancement**
   - Use Gemini to improve text readability
   - Generate summaries and key points
   - Enhance pronunciation guides

2. **Smart Voice Selection**
   - Automatic voice selection based on content
   - Emotion-aware voice modulation
   - Multi-language content detection

3. **Audio Quality Optimization**
   - AI-driven audio enhancement
   - Background noise reduction
   - Voice clarity improvement

4. **Content Analysis**
   - Extract key information from PDFs
   - Generate chapter summaries
   - Create content metadata

5. **Advanced Playback Features**
   - Pause/Resume support for Live API
   - Audio buffering for smoother playback
   - Speed control and voice modulation
   - Bookmark and resume functionality

### API Usage Monitoring

- Track API usage and costs
- Monitor response times
- Rate limiting and quota management
- Usage analytics and reporting

## Dependencies

```json
{
  "@google/generative-ai": "^0.21.0",
  "@types/google.generative-ai": "^0.21.0"
}
```

## Error Handling

The integration includes comprehensive error handling for:

- Invalid API keys
- Network connectivity issues
- Rate limiting and quotas
- Model availability
- Configuration validation

## Security Considerations

- API keys are stored in localStorage (consider secure storage for production)
- No sensitive data is transmitted except API keys
- All communication uses HTTPS
- Input validation and sanitization

## Troubleshooting

### Common Issues

1. **"Cannot find module '@google/generative-ai'"**
   - Run `npm install` to install dependencies
   - Check package.json for correct version

2. **"Invalid API key"**
   - Verify your API key from Google AI Studio
   - Ensure the key has necessary permissions
   - Check for expired or revoked keys

3. **Connection timeout**
   - Increase timeout settings in configuration
   - Check internet connectivity
   - Verify API service status

4. **Model not found**
   - Ensure you're using a supported model
   - Check model availability in your region
   - Update to latest model versions

### Debug Mode

Enable debug logging by setting:

```javascript
localStorage.setItem('geminiDebug', 'true');
```

This will provide detailed console logging for troubleshooting.

## Contributing

When extending the Gemini integration:

1. Follow the existing service pattern in `geminiApiService.ts`
2. Add proper TypeScript types for new features
3. Include comprehensive error handling
4. Update this documentation
5. Test with various API keys and configurations

## Related Files

- `server/interactions/main_server_files/api_configuration/` - Server-side Gemini integration
- `server/interactions/main_server_files/websocket_server/gemini_session_handler.py` - WebSocket API handling
- `config/requirements.txt` - Python dependencies for server-side integration
