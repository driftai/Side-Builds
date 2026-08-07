import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = (path: string): string => readFileSync(
    new URL(`../${path}`, import.meta.url),
    'utf8',
);

describe('Electron detached-controls contract', () => {
    it('carries stop from the control window through the generic command bridge', () => {
        const controls = source('electron/controls.html');
        const preload = source('electron/preload.js');
        const main = source('electron/main.cjs');

        expect(controls).toContain('id="stop-btn"');
        expect(controls).toContain("send('stop')");
        expect(preload).toContain("ipcRenderer.send('audio-control', command)");
        expect(main).toContain("ipcMain.on('audio-control'");
        expect(main).toContain("broadcastToExtensions({ action: 'audio-control', command })");
    });

    it('pushes retained state as soon as a new controls window is ready', () => {
        const main = source('electron/main.cjs');
        const ready = main.indexOf("controlsWindow.once('ready-to-show'");
        const publish = main.indexOf(
            "controlsWindow.webContents.send('audio-state-update', audioState)",
            ready,
        );

        expect(ready).toBeGreaterThanOrEqual(0);
        expect(publish).toBeGreaterThan(ready);
    });
});
