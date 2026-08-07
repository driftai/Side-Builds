import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
    extractDocumentText,
    getDocumentType,
    SUPPORTED_TYPES,
} from '../services/documentText';
import { AppState, type SentenceIndexSetter } from '../types/playback';
import { makeDocumentId } from '../utils/audioCache';
import { alignSentences } from '../utils/documentDiff';
import { pickDocument, supportsLiveFiles, watchFile } from '../utils/liveFile';
import { splitIntoSentences } from '../utils/textProcessing';

interface DocumentSessionOptions {
    currentSentenceIndex: number;
    setCurrentSentenceIndex: SentenceIndexSetter;
    sentencesRef: React.MutableRefObject<string[]>;
    setFileName: React.Dispatch<React.SetStateAction<string>>;
    setDocumentId: React.Dispatch<React.SetStateAction<string | null>>;
    setAppState: (state: AppState) => void;
    setError: (error: string | null) => void;
    handleStop: () => void;
    applySentenceUpdate: (next: string[], oldToNew: (number | null)[]) => void;
}

export const useDocumentSession = ({
    currentSentenceIndex,
    setCurrentSentenceIndex,
    sentencesRef,
    setFileName,
    setDocumentId,
    setAppState,
    setError,
    handleStop,
    applySentenceUpdate,
}: DocumentSessionOptions) => {
    const [liveWatching, setLiveWatching] = useState(false);
    const [lastEdit, setLastEdit] = useState<{ at: number; changed: number } | null>(null);
    const [sessionStartTime, setSessionStartTime] = useState<number | null>(null);
    const [, setDocRevision] = useState(0);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const stopWatchRef = useRef<(() => void) | null>(null);

    useEffect(() => () => {
        stopWatchRef.current?.();
        stopWatchRef.current = null;
    }, []);

    const closeDocument = useCallback(() => {
        handleStop();
        setAppState(AppState.IDLE);
        stopWatchRef.current?.();
        stopWatchRef.current = null;
        setLiveWatching(false);
        setFileName('');
        setDocumentId(null);
        setError(null);
        setCurrentSentenceIndex(-1);
        sentencesRef.current = [];
        setSessionStartTime(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
    }, [
        handleStop,
        sentencesRef,
        setAppState,
        setCurrentSentenceIndex,
        setDocumentId,
        setError,
        setFileName,
    ]);

    const processFile = useCallback(async (
        file: File,
        options: { keepPosition?: boolean } = {},
    ) => {
        const fileType = getDocumentType(file.name);
        if (!fileType) {
            setError(`Please select a valid file. Supported formats: ${SUPPORTED_TYPES.join(', ')}`);
            setAppState(AppState.IDLE);
            return;
        }

        const resumeAt = options.keepPosition ? currentSentenceIndex : -1;
        handleStop();
        setFileName(file.name);
        setAppState(AppState.PROCESSING);

        try {
            const fullText = await extractDocumentText(file, fileType);
            sentencesRef.current = splitIntoSentences(fullText);
            setDocumentId(await makeDocumentId(file.name));

            if (!options.keepPosition) setSessionStartTime(Date.now());
            if (resumeAt >= 0) {
                setCurrentSentenceIndex(Math.min(resumeAt, sentencesRef.current.length - 1));
            }
            setAppState(AppState.READY);
        } catch (cause) {
            console.error(`Error processing ${fileType.toUpperCase()} file:`, cause);
            setError(
                `Failed to process the ${fileType.toUpperCase()} file. It might be corrupted or in an unsupported format.`,
            );
            setAppState(AppState.ERROR);
        }
    }, [
        currentSentenceIndex,
        handleStop,
        sentencesRef,
        setAppState,
        setCurrentSentenceIndex,
        setDocumentId,
        setError,
        setFileName,
    ]);

    const applyLiveUpdate = useCallback(async (file: File) => {
        const fileType = getDocumentType(file.name);
        if (!fileType) return;

        try {
            const fullText = await extractDocumentText(file, fileType);
            const next = splitIntoSentences(fullText);
            const alignment = alignSentences(sentencesRef.current, next);
            if (alignment.identical) return;

            applySentenceUpdate(next, alignment.oldToNew);
            setDocRevision(revision => revision + 1);
            setLastEdit({ at: Date.now(), changed: alignment.changedCount });
        } catch (cause) {
            console.warn('Live update skipped, document could not be re-read:', cause);
        }
    }, [applySentenceUpdate, sentencesRef]);

    const uploadDocument = useCallback(async () => {
        if (supportsLiveFiles()) {
            const picked = await pickDocument();
            if (picked) {
                await processFile(picked.file);
                stopWatchRef.current?.();
                if (picked.handle) {
                    stopWatchRef.current = watchFile(
                        picked.handle,
                        picked.file.lastModified,
                        updated => { void applyLiveUpdate(updated); },
                    );
                    setLiveWatching(true);
                }
                return;
            }
        }
        fileInputRef.current?.click();
    }, [applyLiveUpdate, processFile]);

    const handleFileChange = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) await processFile(file);
    }, [processFile]);

    return {
        liveWatching,
        lastEdit,
        sessionStartTime,
        fileInputRef,
        closeDocument,
        uploadDocument,
        handleFileChange,
    };
};
