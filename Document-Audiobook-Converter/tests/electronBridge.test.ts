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
        expect(onIpcMessage).toHaveBeenCalledTimes(1);

        const direct = onAudioCommand.mock.calls[0][0];
        const ipc = onIpcMessage.mock.calls[0][1];
        direct({}, 'skipForward');
        ipc({}, 'pause');
        expect(handler.mock.calls).toEqual([
            ['skipForward'],
            ['pause'],
        ]);

        dispose();
        expect(removeAllListeners).toHaveBeenCalledTimes(1);
        expect(removeIpcListeners).toHaveBeenCalledWith(
            'execute-audio-command',
        );
    });
});
