# Electron Always-On-Top Audio Controls

This Electron application provides true always-on-top floating audio controls that stay visible above all other windows and applications.

## Features

- **Always-on-top behavior**: Uses Electron's `alwaysOnTop: true` for true system-level floating controls
- **Cross-application visibility**: Stays visible even when switching between different applications
- **Draggable interface**: Click and drag the header to reposition anywhere on screen
- **Real-time sync**: Automatically syncs with the main audiobook application
- **Minimalist design**: Compact controls that don't interfere with your workflow
- **Global shortcuts**: Press `Ctrl+Shift+B` to quickly toggle controls

## Files

- `main.js` - Electron main process (creates windows and handles IPC)
- `preload.js` - Security layer between main and renderer processes
- `controls.html` - The floating controls UI
- `README.md` - This documentation

## Installation & Setup

### Prerequisites

- Node.js (v14 or higher)
- npm or yarn

### Installation

1. **Install dependencies** (already done):
   ```bash
   npm install
   ```

2. **Development mode** (runs both React dev server and Electron):
   ```bash
   npm run electron-dev
   ```

3. **Production build**:
   ```bash
   npm run build-electron
   ```

## Usage

### Launching Controls

1. **Automatic**: The app automatically shows the main window in development
2. **Manual toggle**: Click the blue monitor icon (🖥️) in the collapsed voice controls
3. **Keyboard shortcut**: Press `Ctrl+Shift+B` anywhere to toggle controls

### Control Features

- **Drag to move**: Click and drag the header to reposition the window
- **Always on top**: Window stays visible above all other applications
- **Real-time sync**: Progress bar and status update automatically
- **Full controls**: Play/pause, skip forward/backward, close button

### WebSocket Communication

The Electron app runs a WebSocket server on port 3001 to communicate with the browser extension. This allows the web app (running in a regular browser) to control the Electron floating controls.

**Communication Flow:**
- **Web App** → **Browser Extension** → **WebSocket** → **Electron App**
- The extension acts as a bridge between the browser and the desktop app

### Window Behavior

- **No frame**: Clean, borderless window design
- **Transparent background**: Modern glassmorphism effect
- **Skip taskbar**: Doesn't clutter your taskbar
- **Always focused**: Automatically maintains focus when needed

## Technical Details

### Architecture

```
Main Process (main.js)
├── Creates BrowserWindow with alwaysOnTop: true
├── Handles IPC communication
├── Manages window lifecycle
└── Registers global shortcuts

Renderer Process (controls.html)
├── Displays audio controls UI
├── Receives state updates via IPC
├── Sends control commands via IPC
└── Handles user interactions
```

### IPC Communication

- **State sync**: Main app → Electron controls (audio state updates)
- **Control commands**: Electron controls → Main app (play/pause/skip)
- **Window management**: Toggle controls, close windows

### Security

- **Context isolation**: Enabled for security
- **Preload script**: Safe API exposure between processes
- **No node integration**: Prevents direct Node.js access from renderer

## Troubleshooting

### Controls not appearing?

- Ensure you're running `npm run electron-dev`
- Check that the React dev server is running on port 5173
- Look for errors in the Electron console

### Window not staying on top?

- Some applications may temporarily override always-on-top
- The window automatically re-asserts itself when it loses focus
- Try closing and reopening the controls

### Sync not working?

- Check that both the main app and Electron controls are running
- Verify IPC communication in dev tools
- Ensure the audio state is updating properly

## Development

### Adding New Features

1. **Main process**: Modify `main.js` for window management or IPC
2. **Renderer process**: Edit `controls.html` for UI changes
3. **Preload script**: Update `preload.js` for new API exposure

### Debugging

- **Main process**: Use `console.log()` in `main.js`
- **Renderer process**: Open dev tools with `Ctrl+Shift+I` in controls window
- **IPC debugging**: Check Electron dev tools for IPC messages

## Distribution

For production builds:

```bash
npm run build-electron
```

This creates distributable packages in the `dist/` folder for Windows, macOS, and Linux.

## Related Files

- `../App.tsx` - Main React application with Electron integration
- `../package.json` - Updated with Electron scripts and dependencies
- `../extension/` - Alternative browser extension approach
