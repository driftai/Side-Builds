# AI Audiobook Floating Controls Extension

This browser extension provides always-on-top floating audio controls for the AI Audiobook Converter that work across all browser tabs.

## Features

- **Always-on-top floating window**: The audio controls stay visible above all other windows and tabs
- **Cross-tab functionality**: Controls work regardless of which tab you're currently viewing
- **Draggable interface**: Move the floating window anywhere on your screen
- **Real-time sync**: Automatically syncs with the main audiobook application
- **Compact design**: Minimalist controls that don't interfere with your work

## Installation

### For Development (Local Testing)

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" in the top right
3. Click "Load unpacked" and select the `extension` folder
4. The extension should now appear in your extensions list

### For Production

1. Package the extension (create a .zip file with all extension files)
2. Submit to Chrome Web Store or distribute manually
3. Users install like any other Chrome extension

## Usage

1. **Launch the extension**: Click the extension icon in your browser toolbar
2. **Floating controls appear**: A small window with audio controls will open
3. **Drag to position**: Click and drag the header to move the window anywhere
4. **Control playback**: Use the play/pause and skip buttons to control audio
5. **Close when done**: Click the X button to close the floating controls

## How it Works

The extension consists of several components:

- **manifest.json**: Defines extension permissions and structure
- **background.js**: Manages the always-on-top window creation and messaging
- **content.js**: Runs in web pages to extract audio state and send commands
- **popup.html/popup.js**: The floating controls interface

The extension communicates with your React audiobook app through:
1. Content scripts that read DOM state
2. Chrome messaging API for cross-context communication
3. Simulated clicks to trigger audio controls in the main app

## Permissions Required

- `activeTab`: Access current tab for audio control
- `tabs`: Monitor tab changes and maintain reference to audiobook app
- `storage`: Save extension settings
- `windows`: Create and manage the floating popup window

## Development Notes

- The extension automatically detects when you're on an audiobook app page
- State sync happens every 500ms for responsive controls
- The floating window uses `alwaysOnTop: true` for persistent visibility
- Window positioning respects screen boundaries

## Troubleshooting

**Controls not responding?**
- Make sure you're on the audiobook app page
- Check that the extension has the necessary permissions
- Try refreshing the page

**Window not staying on top?**
- Some applications may override the always-on-top behavior
- Try closing and reopening the floating controls

**Extension not loading?**
- Ensure all files are in the correct locations
- Check the browser console for error messages
- Verify manifest.json syntax
