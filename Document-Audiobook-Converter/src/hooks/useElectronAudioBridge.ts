import { useEffect } from 'react';
import type React from 'react';
import {
    publishAudioState,
    subscribeToAudioCommands,
    type AudioControlCommand,
} from '../integrations/electronBridge';
import { AppState } from '../types/playback';

interface ElectronAudioBridgeOptions {
    appState: AppState;
    currentSentenceIndex: number;
    sentencesRef: React.MutableRefObject<string[]>;
    onPlay: () => void;
    onPause: () => void;
    onSkipForward: () => void;
    onSkipBackward: () => void;
}

const summariseSentence = (sentence: string | undefined): string => {
    if (!sentence) return '';
    return sentence.substring(0, 60) + (sentence.length > 60 ? '...' : '');
};

/**
 * Renderer-side Electron wiring kept separate from the reader controller.
 *
 * The integration module owns its singleton transports; this hook only binds
 * the currently mounted playback callbacks and state snapshot.
 */
export const useElectronAudioBridge = ({
    appState,
    currentSentenceIndex,
    sentencesRef,
    onPlay,
    onPause,
    onSkipForward,
    onSkipBackward,
}: ElectronAudioBridgeOptions): void => {
    useEffect(() => {
        const sentences = sentencesRef.current;
        publishAudioState({
            isPlaying: appState === AppState.PLAYING,
            currentIndex: currentSentenceIndex,
            totalSentences: sentences.length,
            currentSentence: summariseSentence(sentences[currentSentenceIndex]),
        });
    }, [appState, currentSentenceIndex, sentencesRef]);

    useEffect(() => {
        const handleCommand = (command: AudioControlCommand | string) => {
            if (command === 'play') onPlay();
            else if (command === 'pause') onPause();
            else if (command === 'skipForward') onSkipForward();
            else if (command === 'skipBackward') onSkipBackward();
            else console.log('Ignoring unknown control command:', command);
        };

        return subscribeToAudioCommands(handleCommand);
    }, [onPlay, onPause, onSkipForward, onSkipBackward]);
};
