/**
 * Keep a loaded document in step with the file on disk.
 *
 * A file chosen through a normal `<input type=file>` is a frozen snapshot: the
 * browser hands over the bytes and never looks at the path again, so editing the
 * document afterwards changes nothing until it is uploaded a second time.
 *
 * The File System Access API gives a durable handle instead, which can be
 * re-read on demand. Polling its `lastModified` lets edits appear in the reader
 * without re-picking the file. Where the API is missing (Firefox, Safari, and
 * any non-secure context) the app falls back to the ordinary picker and simply
 * does not watch.
 */

export const supportsLiveFiles = (): boolean =>
    typeof window !== 'undefined' && typeof (window as any).showOpenFilePicker === 'function';

export interface PickedFile {
    file: File;
    /** Present only when the pick went through the File System Access API. */
    handle: FileSystemFileHandle | null;
}

const ACCEPT = {
    'application/pdf': ['.pdf'],
    'text/plain': ['.txt'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
} as Record<string, string[]>;

/**
 * Open a document, preferring a watchable handle.
 * Returns null if the user dismissed the picker.
 */
export const pickDocument = async (): Promise<PickedFile | null> => {
    if (!supportsLiveFiles()) return null;
    try {
        const [handle] = await (window as any).showOpenFilePicker({
            multiple: false,
            types: [{ description: 'Documents', accept: ACCEPT }],
        });
        if (!handle) return null;
        return { file: await handle.getFile(), handle };
    } catch (error: any) {
        // Dismissing the dialog is not an error worth surfacing.
        if (error?.name === 'AbortError') return null;
        console.warn('File picker failed, falling back to upload:', error);
        return null;
    }
};

/** Can we still read this handle without prompting again? */
const stillPermitted = async (handle: FileSystemFileHandle): Promise<boolean> => {
    const query = (handle as any).queryPermission;
    if (typeof query !== 'function') return true;
    const state = await query.call(handle, { mode: 'read' });
    return state === 'granted';
};

/**
 * Watch a handle and report the file whenever it changes on disk.
 *
 * Polls rather than subscribes: the platform offers no change event for a file
 * handle. `lastModified` is compared instead of re-reading the contents, so an
 * untouched file costs almost nothing to check.
 *
 * Returns a function that stops the watch.
 */
export const watchFile = (
    handle: FileSystemFileHandle,
    initialLastModified: number,
    onChange: (file: File) => void,
    intervalMs = 2000,
): (() => void) => {
    let lastSeen = initialLastModified;
    let stopped = false;
    let inFlight = false;

    const tick = async () => {
        if (stopped || inFlight) return;
        inFlight = true;
        try {
            if (!(await stillPermitted(handle))) {
                // Permission lapsed; stop quietly rather than prompting on a timer.
                stop();
                return;
            }
            const file = await handle.getFile();
            if (file.lastModified !== lastSeen) {
                lastSeen = file.lastModified;
                onChange(file);
            }
        } catch (error) {
            // The file may be mid-save, renamed or removed. Keep watching; a
            // transient failure should not end the session.
        } finally {
            inFlight = false;
        }
    };

    const timer = window.setInterval(tick, intervalMs);
    const stop = () => {
        if (stopped) return;
        stopped = true;
        window.clearInterval(timer);
    };
    return stop;
};
