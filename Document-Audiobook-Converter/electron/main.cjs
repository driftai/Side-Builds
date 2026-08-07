const { app, BrowserWindow, ipcMain, globalShortcut, MessageChannelMain } = require('electron');
const path = require('path');
const { createExtensionRelay } = require('./extension-relay.cjs');
const isDev = process.env.NODE_ENV === 'development';

// Fix SSL certificate errors (common in development environments)
app.commandLine.appendSwitch('ignore-certificate-errors');
app.commandLine.appendSwitch('ignore-ssl-errors');
app.commandLine.appendSwitch('disable-web-security');
app.commandLine.appendSwitch('allow-running-insecure-content');
app.commandLine.appendSwitch('disable-features', 'Autofill');

// Handle certificate errors
app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
  // Allow connections despite certificate errors (development only)
  event.preventDefault();
  callback(true);
});
let mainWindow;
let controlsWindow;
let isCreatingControls = false; // Prevent multiple simultaneous window creation attempts
let messageChannel; // MessageChannel for direct window communication
let audioState = {
  isPlaying: false,
  currentIndex: -1,
  totalSentences: 0,
  currentSentence: ''
};

let extensionRelay;

// Create main application window (optional, for development)
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // Load the React app
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
    // In production, also set up MessageChannel when the window is ready
    mainWindow.once('ready-to-show', () => {
      console.log('Main window ready, setting up MessageChannel...');
      setupMessageChannel();
    });
  }

  mainWindow.on('closed', () => {
    console.log('Main window closed - keeping WebSocket server alive');
    mainWindow = null;
    messageChannel = null; // Clean up message channel
    // Don't quit the app - WebSocket server should keep running
  });

  // Ensure main window stays hidden and doesn't interfere
  mainWindow.on('show', () => {
    mainWindow.hide();
  });

  mainWindow.on('restore', () => {
    mainWindow.hide();
  });
}

// Set up MessageChannel for controls window communication
function setupMessageChannel() {
  if (messageChannel) {
    console.log('MessageChannel already exists');
    return;
  }

  console.log('Creating MessageChannel for controls window communication...');
  messageChannel = new MessageChannelMain();

  // port1 stays in main process to receive messages from controls window
  messageChannel.port1.on('message', (event) => {
    const { command } = event.data;
    console.log('Received command from controls window:', command);

    // Forward command to main window (React app)
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('execute-audio-command', command);
    }
  });

  messageChannel.port1.start();
}

// Create always-on-top audio controls window
function createControlsWindow() {
  // Prevent multiple simultaneous window creation attempts
  if (isCreatingControls) {
    console.log('Controls window creation already in progress, skipping...');
    return;
  }

  isCreatingControls = true;
  console.log('Creating floating controls window...');

  // If controls window already exists, just show it
  if (controlsWindow && !controlsWindow.isDestroyed()) {
    console.log('Showing existing controls window');
    controlsWindow.show();
    controlsWindow.focus();
    isCreatingControls = false;
    return;
  }

  console.log('Creating new BrowserWindow for controls');
  try {
    controlsWindow = new BrowserWindow({
      width: 320,
      height: 180,
      alwaysOnTop: true,
      frame: false,
      transparent: false,
      resizable: false,
      skipTaskbar: true,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js')
      },
      show: false, // Don't show until ready
      icon: path.join(__dirname, '../src/assets/icon.png') // Add icon if available
    });

    console.log('Loading controls.html...');
    // Load the controls UI
    controlsWindow.loadFile(path.join(__dirname, 'controls.html'));
    console.log('Controls window file loaded');
  } catch (error) {
    console.error('Error creating controls window:', error);
    isCreatingControls = false; // Reset flag on error
    return;
  }

  // Show window when ready
  controlsWindow.once('ready-to-show', () => {
    console.log('Controls window ready, showing...');
    controlsWindow.show();

    // Send MessageChannel port to controls window
    if (messageChannel) {
      controlsWindow.webContents.postMessage('init-port', null, [messageChannel.port2]);
      console.log('MessageChannel port sent to controls window');
    }
  });

  // Handle window closed
  controlsWindow.on('closed', () => {
    console.log('Controls window closed');
    controlsWindow = null;
    isCreatingControls = false; // Reset flag when window is closed
  });

  // Prevent the window from being hidden behind other windows
  controlsWindow.on('blur', () => {
    // Keep the window on top even when it loses focus
    setTimeout(() => {
      if (controlsWindow && !controlsWindow.isDestroyed()) {
        controlsWindow.setAlwaysOnTop(true);
      }
    }, 100);
  });

  // Make window draggable
  controlsWindow.webContents.on('did-finish-load', () => {
    // Inject CSS for draggable behavior
    controlsWindow.webContents.insertCSS(`
      .controls-header {
        -webkit-app-region: drag;
      }
      .controls-header button {
        -webkit-app-region: no-drag;
      }
    `);
  });
}

function toggleControlsWindow() {
  if (controlsWindow && !controlsWindow.isDestroyed()) {
    controlsWindow.close();
  } else {
    createControlsWindow();
  }
}

function updateAudioState(state) {
  audioState = { ...audioState, ...state };
  if (controlsWindow && !controlsWindow.isDestroyed()) {
    controlsWindow.webContents.send('audio-state-update', audioState);
  }
}

// IPC handlers for communication between windows
ipcMain.on('toggle-controls', () => {
  toggleControlsWindow();
});

ipcMain.on('update-audio-state', (event, state) => {
  updateAudioState(state);
});

ipcMain.on('audio-control', (event, command) => {
  // Forward command to main window
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('execute-audio-command', command);
  }

  // And to anything connected over the socket. Without this the controls could
  // only ever drive Electron's own window, so opening them from a browser tab
  // gave you buttons that did nothing to what you were actually listening to.
  broadcastToExtensions({ action: 'audio-control', command });
});

/** Send a message to every socket client - typically a browser tab running the reader. */
function broadcastToExtensions(payload) {
  extensionRelay?.broadcast(payload);
}

ipcMain.on('close-controls', () => {
  console.log('Main process: Received close-controls command');
  if (controlsWindow && !controlsWindow.isDestroyed()) {
    console.log('Main process: Closing controls window');
    controlsWindow.close();
  } else {
    console.log('Main process: Controls window not found or already destroyed');
  }
});

ipcMain.on('log', (event, { level, message, args }) => {
  const logMessage = `[Renderer - ${event.sender.id}] ${message}`;
  switch (level) {
    case 'info':
      console.log(logMessage, ...args);
      break;
    case 'warn':
      console.warn(logMessage, ...args);
      break;
    case 'error':
      console.error(logMessage, ...args);
      break;
    default:
      console.log(logMessage, ...args);
  }
});

// Global shortcuts are now registered in the main app.whenReady() callback below

app.on('window-all-closed', () => {
  // Keep app running for WebSocket server - NEVER quit automatically
  console.log('All windows closed, but keeping Electron app running for WebSocket server');
  console.log('WebSocket server status: running on port 3001');

  // Explicitly DO NOT quit - the app should only quit via WebSocket 'quit' command
  // This ensures the WebSocket server stays available for the browser extension
});

app.on('activate', () => {
  // On macOS, re-create window when dock icon is clicked
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
  }
});

// Clean up shortcuts and WebSocket server when app quits
app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  extensionRelay?.close();
});

// Handle process termination signals
process.on('SIGINT', () => {
  console.log('Received SIGINT, shutting down gracefully...');
  app.quit();
});

process.on('SIGTERM', () => {
  console.log('Received SIGTERM, shutting down gracefully...');
  app.quit();
});

// Handle app ready
app.whenReady().then(() => {
  // Start WebSocket server for extension communication FIRST
  extensionRelay = createExtensionRelay({
    onToggleControls: toggleControlsWindow,
    onUpdateAudioState: updateAudioState,
    onQuit: () => app.quit(),
  });
  extensionRelay.start();

  // Set up MessageChannel in the main process
  setupMessageChannel();

  console.log('ðŸŽµ Electron audiobook controls app started successfully!');
  console.log('ðŸ’¡ WebSocket server running on port 3001');
  console.log('ðŸ”§ Global shortcut: Ctrl+Shift+B to toggle controls');

  // Register global shortcut (Ctrl+Shift+B) to toggle controls
  globalShortcut.register('CommandOrControl+Shift+B', () => {
    toggleControlsWindow();
  });
});
