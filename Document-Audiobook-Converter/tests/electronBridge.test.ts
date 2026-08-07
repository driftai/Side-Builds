import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
});

describe('Electron playback bridge', () => {
    it('publishes state and owns one command subscription in Electron', async () => {
        const updateAudioState = vi.fn();
        const onAudioCommand = vi.fn();
        const onIpcMessage = vi.fn();
        const removeAllListeners = vi.fn();
        const removeIpcListeners = vi.fn();
        const addEventListener = vi.fn();

        vi.stubGlobal('window', {
            electronAPI: {
                updateAudioState,
                onAudioCommand,
                toggleControls: vi.fn(),
                removeAllListeners,
                onIpcMessage,
                removeIpcListeners,
            },
            addEventListener,
        });

        const bridge = await import('../src/integrations/electronBridge');
        expect(bridge.isElectronRuntime).toBe(true);
        expect(addEventListener).toHaveBeenCalledTimes(1);
        expect(addEventListener).toHaveBeenCalledWith(
            'message',
            expect.any(Function),
        );

        const snapshot = {
            isPlaying: true,
            currentIndex: 2,
            totalSentences: 8,
            currentSentence: 'A short preview',
        };
        bridge.publishAudioState(snapshot);
        expect(updateAudioState).toHaveBeenCalledWith(snapshot);

        const handler = vi.fn();
        const dispose = bridge.subscribeToAudioCommands(handler);
        expect(onAudioCommand).toHaveBeenCalledTimes(1);
        expect(onIpcMessage).not.toHaveBeenCalled();

        const direct = onAudioCommand.mock.calls[0][0];
        direct({}, 'skipForward');
        expect(handler).toHaveBeenCalledExactlyOnceWith('skipForward');

        dispose();
        expect(removeAllListeners).not.toHaveBeenCalled();
        expect(removeIpcListeners).toHaveBeenCalledWith(
            'execute-audio-command',
        );
    });

    it('publishes an already-playing snapshot on connect, then accepts pause', async () => {
        class FakeWebSocket {
            static readonly CONNECTING = 0;
            static readonly OPEN = 1;
            static readonly CLOSED = 3;
            static readonly instances: FakeWebSocket[] = [];

            readyState = FakeWebSocket.CONNECTING;
            sent: string[] = [];
            onopen: (() => void) | null = null;
            onmessage: ((event: { data: string }) => void) | null = null;
            onclose: (() => void) | null = null;
            onerror: (() => void) | null = null;

            constructor(readonly url: string) {
                FakeWebSocket.instances.push(this);
            }

            open(): void {
                this.readyState = FakeWebSocket.OPEN;
                this.onopen?.();
            }

            send(message: string): void {
                this.sent.push(message);
            }

            receive(message: object): void {
                this.onmessage?.({ data: JSON.stringify(message) });
            }

            close(): void {
                this.readyState = FakeWebSocket.CLOSED;
                this.onclose?.();
            }
        }

        vi.stubGlobal('window', {
            addEventListener: vi.fn(),
            setTimeout,
        });
        vi.stubGlobal('WebSocket', FakeWebSocket);

        const bridge = await import('../src/integrations/electronBridge');
        const playing = {
            isPlaying: true,
            currentIndex: 5,
            totalSentences: 12,
            currentSentence: 'Playback was already underway.',
        };
        bridge.publishAudioState(playing);

        const connection = bridge.reachElectron();
        const socket = FakeWebSocket.instances[0];
        expect(socket.url).toBe('ws://localhost:3001');
        socket.open();
        await expect(connection).resolves.toBe(socket);

        expect(socket.sent.map(message => JSON.parse(message))).toEqual([{
            action: 'updateAudioState',
            args: playing,
        }]);

        const { dispatchAudioControlCommand } = await import('../src/hooks/useElectronAudioBridge');
        const handlers = {
            onPlay: vi.fn(),
            onPause: vi.fn(),
            onStop: vi.fn(),
            onSkipForward: vi.fn(),
            onSkipBackward: vi.fn(),
        };
        const dispose = bridge.subscribeToAudioCommands(command => {
            dispatchAudioControlCommand(command, handlers);
        });
        socket.receive({ action: 'audio-control', command: 'pause' });
        expect(handlers.onPause).toHaveBeenCalledTimes(1);
        dispose();
    });

    it('routes the stop command to the mounted playback owner', async () => {
        vi.stubGlobal('window', { addEventListener: vi.fn() });
        const { dispatchAudioControlCommand } = await import('../src/hooks/useElectronAudioBridge');
        const handlers = {
            onPlay: vi.fn(),
            onPause: vi.fn(),
            onStop: vi.fn(),
            onSkipForward: vi.fn(),
            onSkipBackward: vi.fn(),
        };

        expect(dispatchAudioControlCommand('stop', handlers)).toBe(true);
        expect(handlers.onStop).toHaveBeenCalledTimes(1);
        expect(handlers.onPlay).not.toHaveBeenCalled();
    });
});
