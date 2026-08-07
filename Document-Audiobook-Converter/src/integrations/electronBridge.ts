export type AudioControlCommand =
    | 'play'
    | 'pause'
    | 'stop'
    | 'skipForward'
    | 'skipBackward';

export interface AudioStateSnapshot {
    isPlaying: boolean;
    currentIndex: number;
    totalSentences: number;
    currentSentence: string;
}

interface ElectronApi {
    updateAudioState: (state: any) => void;
    onAudioCommand: (
        callback: (event: any, command: string) => void,
    ) => void;
    toggleControls: () => void;
    sendCommand?: (command: string) => void;
    hasMessagePort?: () => boolean;
    closeControls?: () => void;
    removeAllListeners: () => void;
    onIpcMessage?: (
        channel: string,
        callback: (event: any, ...args: any[]) => void,
    ) => void;
    removeIpcListeners?: (channel: string) => void;
}

declare global {
    interface Window {
        electronAPI?: ElectronApi;
        electron?: {
            ipcRenderer: {
                on: (
                    channel: string,
                    callback: (event: any, ...args: any[]) => void,
                ) => void;
                removeAllListeners: (channel: string) => void;
            };
        };
        messagePort?: MessagePort;
    }
}

const getElectronAPI = (): ElectronApi | null => {
    if (typeof window !== 'undefined' && window.electronAPI) {
        return window.electronAPI;
    }
    return null;
};

const electronAPI = getElectronAPI();

/**
 * Kept as a module-level snapshot to match the preload contract: the API exists
 * before React is loaded and does not appear midway through a reader session.
 */
export const isElectronRuntime = electronAPI !== null;

let electronWebSocket: WebSocket | null = null;
let messageChannelPort: MessagePort | null = null;
let remoteCommandHandler: ((command: AudioControlCommand | string) => void) | null = null;
let latestAudioState: AudioStateSnapshot | null = null;

const sendAudioStateToSocket = (
    socket: WebSocket,
    state: AudioStateSnapshot,
): void => {
    if (socket.readyState !== WebSocket.OPEN) return;
    try {
        socket.send(JSON.stringify({
            action: 'updateAudioState',
            args: state,
        }));
    } catch {
        // Electron closed between the ready-state check and the send.
    }
};

const publishLatestAudioState = (socket: WebSocket): void => {
    if (latestAudioState) sendAudioStateToSocket(socket, latestAudioState);
};

const deliverSocketCommand = (event: MessageEvent) => {
    try {
        const data = JSON.parse(event.data);
        if (data?.action === 'audio-control' && data.command) {
            remoteCommandHandler?.(data.command);
        }
    } catch {
        // Not JSON, or not an audio-control message.
    }
};

/**
 * Is the Electron app running, and can this page reach it?
 *
 * Probed only when detach is requested so normal browser use does not open a
 * collection of doomed sockets on page load.
 */
export const reachElectron = (timeoutMs = 700): Promise<WebSocket | null> => {
    if (electronWebSocket?.readyState === WebSocket.OPEN) {
        return Promise.resolve(electronWebSocket);
    }

    return new Promise(resolve => {
        let socket: WebSocket;
        try {
            socket = new WebSocket('ws://localhost:3001');
        } catch {
            resolve(null);
            return;
        }

        const settle = (result: WebSocket | null) => {
            clearTimeout(timer);
            resolve(result);
        };
        const timer = window.setTimeout(() => {
            try { socket.close(); } catch { /* never opened */ }
            settle(null);
        }, timeoutMs);

        socket.onopen = () => {
            electronWebSocket = socket;
            socket.onmessage = deliverSocketCommand;
            socket.onclose = () => {
                if (electronWebSocket === socket) electronWebSocket = null;
            };
            publishLatestAudioState(socket);
            settle(socket);
        };
        socket.onerror = () => settle(null);
    });
};

/**
 * Open the renderer's legacy floating-controls socket.
 *
 * The first returned socket may still be connecting; callers retain the
 * existing keyboard/extension fallbacks for that first interaction.
 */
const connectToElectronWebSocket = (): WebSocket | null => {
    if (electronWebSocket?.readyState === WebSocket.OPEN) {
        return electronWebSocket;
    }

    const ports = [3001, 3002, 3003, 3004, 3005, 3006];
    for (const port of ports) {
        try {
            const socket = new WebSocket(`ws://localhost:${port}`);
            socket.onopen = () => {
                console.log(`✅ Electron app connected on port ${port}`);
                electronWebSocket = socket;
                publishLatestAudioState(socket);
            };
            socket.onmessage = deliverSocketCommand;
            socket.onclose = () => {
                console.log('❌ Electron app disconnected');
                if (electronWebSocket === socket) electronWebSocket = null;
            };
            socket.onerror = () => {
                // Connection failed; the next deliberate action may retry.
            };
            return socket;
        } catch {
            continue;
        }
    }

    console.log('❌ Could not connect to Electron app on any port');
    return null;
};

const simulateKeyPress = (
    key: string,
    ctrlKey = false,
    shiftKey = false,
) => {
    const createEvent = (type: 'keydown' | 'keyup') => {
        const event = new KeyboardEvent(type, {
            key,
            code: `Key${key.toUpperCase()}`,
            ctrlKey,
            shiftKey,
            bubbles: true,
            cancelable: true,
            composed: true,
            altKey: false,
            metaKey: false,
            repeat: false,
        });
        Object.defineProperty(event, 'which', { value: key.charCodeAt(0) });
        Object.defineProperty(event, 'keyCode', { value: key.charCodeAt(0) });
        return event;
    };

    const targets = [document, window, document.body, document.activeElement];
    for (const target of targets) {
        try {
            target?.dispatchEvent(createEvent('keydown'));
            target?.dispatchEvent(createEvent('keyup'));
        } catch {
            // A fallback target being unavailable is harmless.
        }
    }

    try {
        const edgeEvent = new CustomEvent('keydown', {
            detail: { key: 'A', ctrlKey: true, shiftKey: true },
        });
        document.body.dispatchEvent(edgeEvent);
    } catch {
        // Edge-specific fallback unavailable.
    }
};

/**
 * Ask Electron to toggle its always-on-top controls, retaining the extension
 * and global-shortcut fallbacks used by browser tabs.
 */
export const toggleElectronControls = () => {
    const socket = connectToElectronWebSocket();
    if (socket?.readyState === WebSocket.OPEN) {
        console.log('🎵 Toggling floating controls');
        socket.send(JSON.stringify({ action: 'toggleControls' }));
        return;
    }

    if (electronAPI) {
        try {
            console.log('🎵 Toggling floating controls (extension)');
            electronAPI.toggleControls();
            return;
        } catch {
            // Continue to browser-extension messaging.
        }
    }

    if (typeof chrome !== 'undefined' && chrome.runtime?.sendMessage) {
        try {
            console.log('🎵 Toggling floating controls (messaging)');
            chrome.runtime.sendMessage({
                action: 'electronCommand',
                method: 'toggleControls',
            });
            return;
        } catch {
            // Continue to the shortcut fallback.
        }
    }

    console.log('🎵 Using global shortcut fallback');
    simulateKeyPress('B', true, true);
};

/** Publish the reader's current transport state over the active bridge. */
export const publishAudioState = (state: AudioStateSnapshot) => {
    latestAudioState = state;
    if (isElectronRuntime && electronAPI) {
        electronAPI.updateAudioState(state);
        return;
    }

    const socket = electronWebSocket;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;

    sendAudioStateToSocket(socket, state);
};

/**
 * Register the mounted reader as the single owner of remote transport commands.
 */
export const subscribeToAudioCommands = (
    handler: (command: AudioControlCommand | string) => void,
): (() => void) => {
    if (!isElectronRuntime) {
        remoteCommandHandler = handler;
        return () => {
            if (remoteCommandHandler === handler) remoteCommandHandler = null;
        };
    }

    if (!electronAPI) return () => {};

    const handleAudioCommand = (
        _event: any,
        command: string,
    ) => handler(command);

    electronAPI.onAudioCommand(handleAudioCommand);

    return () => {
        if (electronAPI.removeIpcListeners) {
            electronAPI.removeIpcListeners('execute-audio-command');
        } else {
            electronAPI.removeAllListeners();
        }
    };
};

const receiveMessagePort = (event: MessageEvent) => {
    if (event.data !== 'init-port' || !event.ports?.[0]) return;
    messageChannelPort = event.ports[0];
    messageChannelPort.start();
    console.log('React App: MessageChannel port received and started');
};

if (typeof window !== 'undefined') {
    window.addEventListener('message', receiveMessagePort);
}
