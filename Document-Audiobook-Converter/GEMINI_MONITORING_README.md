# Gemini API Activity Monitoring System

This document describes the real-time monitoring system for the Gemini Audiobook Converter that shows API activities just like the main Gemini Local Workshop server.

## Overview

The monitoring system provides comprehensive visibility into:

- **Real-time API Calls**: Track every request to Gemini API
- **Connection Status**: Monitor connection health and duration
- **Model Activities**: See which models are being used and when
- **Voice Processing**: Track voice configuration and processing
- **Performance Metrics**: Response times, success rates, error tracking
- **Configuration Changes**: Log all setting modifications

## Components

### 1. Python Monitor (`gemini_monitor.py`)
- **Real-time Console Display**: Shows live API activities with emojis and timestamps
- **HTTP Server**: Receives logs from the React app (port 8081)
- **Periodic Reports**: Comprehensive status updates every 30 seconds
- **Performance Tracking**: Response times, success rates, error analysis

### 2. JavaScript Logger (`src/services/geminiLogger.js`)
- **Browser Integration**: Logs activities from the React application
- **HTTP Communication**: Sends logs to the Python monitor
- **Automatic Reconnection**: Handles monitor availability gracefully
- **Rich Logging**: Multiple log types with detailed context

### 3. Enhanced Batch File (`start_audiobook_converter_enhanced.bat`)
- **Dual Launch**: Starts both the development server and monitor
- **Status Display**: Shows monitoring capabilities and server URLs
- **Process Management**: Handles background processes properly

## Features

### Real-time Console Output

The monitor displays activities with clear visual indicators:

```
🔄 [14:23:15] Starting Connection Test: Testing gemini-2.0-flash-exp with API key
🤖 [14:23:15] gemini-2.0-flash-exp: Connection test initiated
✅ [14:23:16] SUCCESS: Connection Test (1.25s)
🎤 [14:23:20] Voice natural: Configuration updated
⚙️ [14:23:25] Config changed: Configuration from unsaved to saved to localStorage
```

### Periodic Status Reports

Every 30 seconds, the monitor displays a comprehensive report:

```
============================================================
🎵 GEMINI AUDIOBOOK CONVERTER - API STATUS REPORT
============================================================
⏱️  Runtime: 5.2m
📊 API Calls: 15 total
   ✅ Successful: 14
   ❌ Failed: 1
   📈 Success Rate: 93.3%
🔗 Active Connections: 1
🔄 Current Activity: Idle

📋 Recent API Calls:
   ✅ Connection Test: API is responding correctly (1.25s)
   ✅ Configuration Save: Settings saved successfully (0.05s)
============================================================
```

### Log Types Tracked

#### API Calls
- **Connection Tests**: Verify API connectivity and response times
- **Model Interactions**: Track which models are being used
- **Error Handling**: Log failures with detailed error messages
- **Test Audio Generation**: Live API simulation with performance metrics

#### Configuration Changes
- **API Key Updates**: Track key configuration changes
- **Model Selection**: Log model switches
- **Voice Settings**: Monitor voice configuration changes
- **Save/Load Operations**: Track configuration persistence

#### Voice Processing
- **Voice Selection**: Log which voices are chosen
- **Language Settings**: Track language configuration
- **Processing Activities**: Monitor voice synthesis activities

#### Connection Events
- **Client Initialization**: Track API client setup
- **Connection Status**: Monitor connection health
- **Error Recovery**: Log reconnection attempts

## Usage

### Starting the Enhanced System

1. **Use the Enhanced Batch File**:
   ```cmd
   start_audiobook_converter_enhanced.bat
   ```

2. **Manual Start** (Alternative):
   ```cmd
   # Terminal 1 - Start the monitor
   python gemini_monitor.py

   # Terminal 2 - Start the React app
   npm run dev
   ```

### What You'll See

#### Console Output Examples

**Successful Connection Test:**
```
🔄 [14:23:15] Starting Connection Test: Testing gemini-2.0-flash-exp
🤖 [14:23:15] gemini-2.0-flash-exp: Connection test initiated
✅ [14:23:16] SUCCESS: Connection Test (1.25s)
   Response time: 1.25s
```

**Configuration Changes:**
```
⚙️ [14:23:20] Config changed: Configuration
   From: gemini-1.5-flash
   To: gemini-2.0-flash-exp
🎤 [14:23:20] Voice natural: Configuration updated
```

**Error Handling:**
```
❌ [14:23:25] Connection Test: API quota exceeded
   Details: QUOTA_EXCEEDED
```

#### Status Reports

The system generates periodic reports showing:

- **Runtime Duration**: How long the system has been running
- **API Statistics**: Total calls, success/failure rates
- **Active Connections**: Current connection count
- **Recent Activities**: Last 5 API calls with durations
- **Performance Metrics**: Response times and trends

### React App Integration

The React application automatically logs activities:

- **API Configuration**: Key setup, model selection, voice settings
- **Connection Tests**: Full test cycle with timing
- **Error Events**: Failed operations with context
- **User Actions**: Configuration saves, loads, resets

## Architecture

### Communication Flow

```
React App (5173) → HTTP POST → Python Monitor (8081)
    ↓                           ↓
Browser Console           Console Display + Reports
```

### Log Message Format

```javascript
{
  "eventType": "api_call_start",
  "data": {
    "callType": "Connection Test",
    "details": "Testing gemini-2.0-flash-exp",
    "timestamp": "14:23:15"
  },
  "source": "audiobook-converter"
}
```

### Data Flow

1. **React App** → **geminiLogger.js** → **HTTP POST** → **Python Monitor**
2. **Monitor** → **Console Display** + **Periodic Reports**
3. **Monitor** → **Status Tracking** + **Performance Metrics**

## Configuration

### Monitor Settings

The monitor runs on these default settings:

- **HTTP Port**: 8081 (for receiving React app logs)
- **Status Interval**: 30 seconds (periodic reports)
- **Reconnection Attempts**: 5 (for HTTP client reconnection)
- **Reconnection Delay**: 2 seconds

### React Logger Settings

- **Monitor Port**: 8081 (matches Python monitor)
- **Max Reconnect Attempts**: 5
- **Reconnect Delay**: 2 seconds
- **Auto-initialization**: On page load

## Troubleshooting

### Common Issues

#### Monitor Not Starting
```
Solution: Ensure Python is installed and in PATH
Command: python --version
```

#### HTTP Connection Failed
```
Error: Monitor not available, logging to console only
Solution: Check if Python monitor is running on port 8081
```

#### React App Not Logging
```
Check: Browser console for connection errors
Verify: Python monitor is receiving HTTP requests
```

#### Port Conflicts
```
Solution: Change ports in configuration
Monitor: Modify run_http_server(port)
Logger: Update monitoringPort in geminiLogger.js
```

### Debug Mode

Enable verbose logging:

```javascript
// In browser console
localStorage.setItem('geminiDebug', 'true');
```

This adds detailed debug information to console logs.

## Integration with Main Server

This monitoring system mirrors the logging approach used in the main Gemini Local Workshop server:

- **Similar Log Format**: Uses same activity tracking patterns
- **Console Display**: Emojis and timestamps match main server style
- **Performance Metrics**: Tracks same KPIs as main server
- **Error Handling**: Consistent error reporting approach

## Future Enhancements

### Planned Features

1. **Log Persistence**: Save logs to files for analysis
2. **Web Dashboard**: HTML interface for viewing logs
3. **Alert System**: Notifications for critical events
4. **Performance Graphs**: Visual charts of API performance
5. **Export Functionality**: Export logs in various formats

### Integration Points

- **Main Server Logs**: Could merge with main Gemini server logs
- **Database Storage**: Store logs in database for historical analysis
- **Remote Monitoring**: Send logs to remote monitoring systems
- **Analytics Integration**: Connect with analytics platforms

## Files Overview

```
📁 Monitoring System Files:
├── gemini_monitor.py              # Python monitoring system
├── src/services/geminiLogger.js   # JavaScript logging client
├── start_audiobook_converter_enhanced.bat  # Enhanced launcher
└── GEMINI_MONITORING_README.md    # This documentation
```

## Quick Start

1. **Run Enhanced Launcher**:
   ```cmd
   start_audiobook_converter_enhanced.bat
   ```

2. **Open Browser**: Navigate to http://localhost:5173

3. **Configure Gemini**: Add your API key and settings

4. **Test Connection**: Click "Test Connection" to see monitoring in action

5. **Watch Console**: See real-time API activities in the monitor window

The system will now show comprehensive Gemini API activities just like the main server!
