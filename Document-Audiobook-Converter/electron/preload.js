const { contextBridge, ipcRenderer } = require('electron');

let messagePort = null;

// Listen for MessageChannel port from main process
ipcRenderer.on('init-port', (event) => {
    messagePort = event.ports[0];
    messagePort.start();
    console.log('MessageChannel port received in preload');
});

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
    // Send audio state updates to Electron controls
    updateAudioState: (state) => ipcRenderer.send('update-audio-state', state),

    // Listen for audio control commands from Electron controls
    onAudioCommand: (callback) => ipcRenderer.on('execute-audio-command', callback),

    // Toggle floating controls
    toggleControls: () => ipcRenderer.send('toggle-controls'),

    // Close controls window
    closeControls: () => ipcRenderer.send('close-controls'),

    // Press a transport control. The main process forwards this to its own
    // window and to any browser tab connected over the socket, so the controls
    // drive whichever copy of the reader is actually playing.
    audioControl: (command) => ipcRenderer.send('audio-control', command),

    // Send command via MessageChannel (for controls window)
    sendCommand: (command) => {
        if (messagePort) {
            messagePort.postMessage({ command });
        } else {
            console.warn('MessageChannel port not available');
        }
    },

    // Check if MessageChannel is available
    hasMessagePort: () => messagePort !== null,

    // Remove all listeners when component unmounts
    removeAllListeners: () => ipcRenderer.removeAllListeners(),

    // Listen for IPC messages from main process
    onIpcMessage: (channel, callback) => ipcRenderer.on(channel, callback),

    // Remove IPC message listeners
    removeIpcListeners: (channel) => ipcRenderer.removeAllListeners(channel),

    // Send renderer logs to main process
    log: (level, message, ...args) => ipcRenderer.send('log', { level, message, args }),
});
