import { useCallback, useEffect, useState } from 'react';
import type React from 'react';
import {
    isElectronRuntime,
    reachElectron,
    toggleElectronControls,
} from '../integrations/electronBridge';

interface DetachedControlsState {
    pipWindow: Window | null;
    pipCompact: boolean;
    floatingControls: boolean;
    floatingAt: { x: number; y: number };
    setFloatingAt: React.Dispatch<React.SetStateAction<{ x: number; y: number }>>;
    closeFloatingControls: () => void;
    toggleDetachedControls: () => Promise<void>;
    togglePipCompact: () => void;
}

/**
 * Owns the windows and positioning used to keep the transport within reach.
 *
 * Audio remains in the main page; only controls are portaled into Document
 * Picture-in-Picture, Electron, or the draggable in-page fallback.
 */
export const useDetachedControls = (
    fileName: string,
    currentSentenceIndex: number,
): DetachedControlsState => {
    const [floatingControls, setFloatingControls] = useState(false);
    const [floatingAt, setFloatingAt] = useState({ x: 24, y: 24 });
    const [pipWindow, setPipWindow] = useState<Window | null>(null);
    const [pipCompact, setPipCompact] = useState(false);

    const toggleDetachedControls = useCallback(async () => {
        if (isElectronRuntime) {
            toggleElectronControls();
            return;
        }

        // Prefer Electron when its app is already running. Unlike a browser
        // Picture-in-Picture window, its controls can outlive this tab.
        const electron = await reachElectron();
        if (electron) {
            electron.send(JSON.stringify({ action: 'toggleControls' }));
            return;
        }

        const documentPip = (window as any).documentPictureInPicture;
        if (!documentPip?.requestWindow) {
            setFloatingControls(open => !open);
            return;
        }

        if (pipWindow) {
            pipWindow.close();
            setPipWindow(null);
            return;
        }

        try {
            const win: Window = await documentPip.requestWindow({
                width: 320,
                height: 168,
            });

            for (const sheet of Array.from(document.styleSheets)) {
                try {
                    const css = Array.from(sheet.cssRules)
                        .map(rule => rule.cssText)
                        .join('');
                    const style = win.document.createElement('style');
                    style.textContent = css;
                    win.document.head.appendChild(style);
                } catch {
                    // A cross-origin sheet cannot expose cssRules, but the
                    // detached window can still load its URL directly.
                    if (sheet.href) {
                        const link = win.document.createElement('link');
                        link.rel = 'stylesheet';
                        link.href = sheet.href;
                        win.document.head.appendChild(link);
                    }
                }
            }

            win.document.body.style.margin = '0';
            win.document.body.style.background = '#111827';
            win.document.title = 'Audiobook controls';
            win.addEventListener('pagehide', () => {
                setPipWindow(null);
                setPipCompact(false);
            });
            setPipWindow(win);
        } catch (error) {
            console.warn('Could not open a detached controls window:', error);
            setFloatingControls(open => !open);
        }
    }, [pipWindow]);

    useEffect(
        () => () => {
            try { pipWindow?.close(); } catch { /* already closed */ }
        },
        [pipWindow],
    );

    useEffect(() => {
        if (!pipWindow) return;
        const position = currentSentenceIndex >= 0
            ? ` - Clip #${currentSentenceIndex}`
            : '';
        pipWindow.document.title = `${fileName || 'Audiobook'}${position}`;
    }, [pipWindow, fileName, currentSentenceIndex]);

    const togglePipCompact = useCallback(() => {
        const next = !pipCompact;
        setPipCompact(next);
        try {
            pipWindow?.resizeTo(next ? 232 : 320, next ? 96 : 168);
        } catch {
            // Window sizing is controlled by the browser.
        }
    }, [pipCompact, pipWindow]);

    const closeFloatingControls = useCallback(
        () => setFloatingControls(false),
        [],
    );

    return {
        pipWindow,
        pipCompact,
        floatingControls,
        floatingAt,
        setFloatingAt,
        closeFloatingControls,
        toggleDetachedControls,
        togglePipCompact,
    };
};
