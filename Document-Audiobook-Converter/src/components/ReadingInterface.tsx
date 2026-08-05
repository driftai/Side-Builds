import React from 'react';
import { AppState } from '../hooks/useAudioEngine';

interface ReadingInterfaceProps {
    sentences: string[];
    currentSentenceIndex: number;
    appState: AppState;
    onSentenceClick: (index: number) => void;
    sessionStartTime: number | null;
    /** Character offset being spoken in the current sentence, if known. */
    spokenCharIndex?: number | null;
}

/**
 * Split a sentence around the word covering `charIndex`, so it can be marked
 * while the rest of the sentence stays intact. Returns null when the offset
 * falls outside the sentence, in which case the sentence renders plainly.
 */
const splitAroundWord = (sentence: string, charIndex: number | null | undefined) => {
    if (charIndex === null || charIndex === undefined) return null;
    if (charIndex < 0 || charIndex >= sentence.length) return null;

    // Walk out to the whitespace on either side of the offset.
    let start = charIndex;
    while (start > 0 && !/\s/.test(sentence[start - 1])) start--;
    let end = charIndex;
    while (end < sentence.length && !/\s/.test(sentence[end])) end++;
    if (end <= start) return null;

    return {
        before: sentence.slice(0, start),
        word: sentence.slice(start, end),
        after: sentence.slice(end),
    };
};

const ReadingInterface: React.FC<ReadingInterfaceProps> = ({
    sentences,
    currentSentenceIndex,
    appState,
    onSentenceClick,
    sessionStartTime,
    spokenCharIndex
}) => {
    // The reading area takes whatever room is left rather than a fixed slice of
    // the viewport, so it gives way when the controls or the audio manager open
    // and takes the space back when they close. Fixed heights here and on the
    // controls could add up to more than the screen.
    return (
        <div className="grow min-h-[7rem] flex flex-col bg-linear-to-b from-gray-900/30 to-gray-800/20 rounded-lg border border-gray-700/30 overflow-hidden relative transition-all duration-300 ease-in-out">
            {/* Progress & Stats Header */}
            <div className="bg-gray-800/40 px-6 py-3 border-b border-gray-700/20">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="text-sm text-gray-400 font-serif">
                            Reading Session
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span>⏱️</span>
                            <span>Focus Time: {sessionStartTime ? Math.floor((Date.now() - sessionStartTime) / 1000 / 60) : 0}min</span>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <div className="text-xs text-gray-500">
                            Est. {Math.round(sentences.length / 2)}min read
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-20 h-1 bg-gray-700/50 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-linear-to-r from-blue-500/60 to-indigo-500/60 rounded-full transition-all duration-500 ease-out"
                                    style={{ width: `${((currentSentenceIndex + 1) / Math.max(sentences.length, 1)) * 100}%` }}
                                ></div>
                            </div>
                            <span className="text-xs text-gray-400 font-medium w-8 text-right">
                                {Math.round(((currentSentenceIndex + 1) / Math.max(sentences.length, 1)) * 100)}%
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Clean Reading Area */}
            <div className="p-8 overflow-y-auto grow min-h-0 transition-all duration-300 ease-in-out">
                {/* Minimalist Text Content */}
                <div className="max-w-4xl mx-auto font-serif text-lg text-gray-300 leading-relaxed text-justify px-6">
                    {sentences.map((sentence, index) => {
                        const isCurrent = index === currentSentenceIndex;
                        const isCompleted = index < currentSentenceIndex;
                        const isUpcoming = index > currentSentenceIndex && index <= currentSentenceIndex + 1;

                        return (
                            <span
                                key={index}
                                id={`sentence-${index}`}
                                onClick={() => onSentenceClick(index)}
                                className={`transition-all duration-300 cursor-pointer relative inline px-1 py-0.5 mx-0.5 rounded-xs ${isCurrent
                                        ? 'bg-blue-600/20 text-white shadow-xs border border-blue-500/30'
                                        : isCompleted
                                            ? 'text-gray-500/80'
                                            : isUpcoming
                                                ? 'text-gray-200/90 hover:text-white hover:bg-gray-700/20'
                                                : 'text-gray-400/70 hover:text-gray-300 hover:bg-gray-700/10'
                                    }`}
                                title={`${isCurrent
                                    ? '🎯 Currently reading'
                                    : isCompleted
                                        ? '✅ Completed'
                                        : 'Click to jump here'
                                    } - Clip #${index}`}
                            >
                                {(() => {
                                    // Mark the word being spoken, inside the sentence
                                    // already highlighted as current.
                                    const parts = isCurrent ? splitAroundWord(sentence, spokenCharIndex) : null;
                                    if (!parts) return sentence;
                                    return (
                                        <>
                                            {parts.before}
                                            <span className="bg-blue-400/30 text-white rounded-xs px-0.5 -mx-0.5 transition-colors duration-100">
                                                {parts.word}
                                            </span>
                                            {parts.after}
                                        </>
                                    );
                                })()}
                                {' '}
                            </span>
                        );
                    })}
                </div>

                {/* Minimalist Reading Stats */}
                {sentences.length > 0 && (
                    <div className="mt-8 p-4 bg-gray-800/20 rounded-lg border border-gray-700/20 max-w-4xl mx-auto">
                        <div className="grid grid-cols-3 gap-4 text-center">
                            <div>
                                <div className="text-lg font-serif text-gray-300 font-medium">
                                    {sentences.filter(s => s.length > 80).length}
                                </div>
                                <div className="text-xs text-gray-500">key passages</div>
                            </div>
                            <div>
                                <div className="text-lg font-serif text-gray-300 font-medium">
                                    {Math.round(sentences.length / 3)}
                                </div>
                                <div className="text-xs text-gray-500">avg per min</div>
                            </div>
                            <div>
                                <div className="text-lg font-serif text-gray-300 font-medium">
                                    {Math.round(sentences.length / 20)}
                                </div>
                                <div className="text-xs text-gray-500">natural breaks</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ReadingInterface;
