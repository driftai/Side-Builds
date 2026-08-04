import React from 'react';
import { AppState } from '../hooks/useAudioEngine';

// Icons
const PlayIcon: React.FC<{ className?: string }> = ({ className }) => (<svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path fillRule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.647c1.295.742 1.295 2.545 0 3.286L7.279 20.99c-1.25.717-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" /></svg>);
const PauseIcon: React.FC<{ className?: string }> = ({ className }) => (<svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path fillRule="evenodd" d="M6.75 5.25a.75.75 0 01.75.75v12a.75.75 0 01-1.5 0V6a.75.75 0 01.75-.75zm9 0a.75.75 0 01.75.75v12a.75.75 0 01-1.5 0V6a.75.75 0 01.75-.75z" clipRule="evenodd" /></svg>);
const StopIcon: React.FC<{ className?: string }> = ({ className }) => (<svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path fillRule="evenodd" d="M4.5 7.5a3 3 0 013-3h9a3 3 0 013 3v9a3 3 0 01-3 3h-9a3 3 0 01-3-3v-9z" clipRule="evenodd" /></svg>);
const SkipBackwardIcon: React.FC<{ className?: string }> = ({ className }) => (<svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M5.75 5.5a.75.75 0 00-.75.75v11.5a.75.75 0 001.5 0V6.25a.75.75 0 00-.75-.75zM17.15 5.72a.75.75 0 00-1.05.07L9.4 11.54a.75.75 0 000 .82l6.7 5.75a.75.75 0 10.98-1.14L11.1 12l6.05-5.14a.75.75 0 00.07-1.05z" /></svg>);
const SkipForwardIcon: React.FC<{ className?: string }> = ({ className }) => (<svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M18.25 5.5a.75.75 0 01.75.75v11.5a.75.75 0 01-1.5 0V6.25a.75.75 0 01.75-.75zM6.85 5.72a.75.75 0 011.05.07l6.7 5.75a.75.75 0 010 .82l-6.7 5.75a.75.75 0 01-.98-1.14L12.9 12 6.85 6.86a.75.75 0 01-.07-1.05z" /></svg>);

interface PlayerControlsProps {
    appState: AppState;
    currentSentenceIndex: number;
    totalSentences: number;
    onPlay: () => void;
    onPause: () => void;
    onStop: () => void;
    onSkipForward: () => void;
    onSkipBackward: () => void;
}

const PlayerControls: React.FC<PlayerControlsProps> = ({
    appState,
    currentSentenceIndex,
    totalSentences,
    onPlay,
    onPause,
    onStop,
    onSkipForward,
    onSkipBackward
}) => {
    return (
        <div className="flex items-center justify-center space-x-2 sm:space-x-3">
            <button
                onClick={onSkipBackward}
                className="p-2 sm:p-2.5 rounded-full bg-gray-600 text-white shadow-lg hover:bg-gray-500 focus:outline-hidden focus:ring-2 focus:ring-gray-400/75 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Previous Sentence"
                disabled={(appState !== AppState.PLAYING && appState !== AppState.PAUSED) || currentSentenceIndex <= 0}
            >
                <SkipBackwardIcon className="h-4 w-4 sm:h-5 sm:w-5" />
            </button>
            <button
                onClick={appState === AppState.PLAYING ? onPause : onPlay}
                className="p-2.5 sm:p-3 rounded-full animated-play-button text-white shadow-lg hover:shadow-xl focus:outline-hidden focus:ring-2 focus:ring-gray-400/75 transition-all duration-200 transform hover:scale-105 disabled:opacity-50 disabled:transform-none"
                aria-label={appState === AppState.PLAYING ? 'Pause' : 'Play'}
                disabled={totalSentences === 0}
            >
                {appState === AppState.PLAYING ? <PauseIcon className="h-6 w-6 sm:h-7 sm:w-7" /> : <PlayIcon className="h-6 w-6 sm:h-7 sm:w-7" />}
            </button>
            <button
                onClick={onSkipForward}
                className="p-2 sm:p-2.5 rounded-full bg-gray-600 text-white shadow-lg hover:bg-gray-500 focus:outline-hidden focus:ring-2 focus:ring-gray-400/75 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Next Sentence"
                disabled={(appState !== AppState.PLAYING && appState !== AppState.PAUSED) || currentSentenceIndex >= totalSentences - 1}
            >
                <SkipForwardIcon className="h-4 w-4 sm:h-5 sm:w-5" />
            </button>
            <button
                onClick={onStop}
                className="p-2 sm:p-2.5 rounded-full bg-gray-600 text-white shadow-lg hover:bg-gray-500 focus:outline-hidden focus:ring-2 focus:ring-gray-400/75 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Stop"
                disabled={appState !== AppState.PLAYING && appState !== AppState.PAUSED}
            >
                <StopIcon className="h-4 w-4 sm:h-5 sm:w-5" />
            </button>
        </div>
    );
};

export default PlayerControls;
