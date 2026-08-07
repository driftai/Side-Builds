import type React from 'react';
import { useState, useRef, useCallback, useEffect } from 'react';
import { GeminiApiConfig } from '../components/GeminiConfig';
import {
    makeClipKey, makeLegacyClipKey, adoptLegacyClip, updateClipPosition,
    getClip, putClip, audioBufferToPcm16, noteActivity, isSavingEnabled, isStreamingEnabled,
    subscribe,
} from '../utils/audioCache';
import { remapIndex } from '../utils/documentDiff';
import { narratableText, isNarratable } from '../utils/textProcessing';
import { PcmStreamPlayer } from '../utils/streamingPlayer';
import type { NarrationResult } from './useGemini';

/** Sample rate of the PCM the Live API returns. */
const PCM_SAMPLE_RATE = 24000;

/**
 * Audio fragments for one passage as they arrive, so playback can begin before
 * generation finishes. Only kept while the streaming bypass is enabled.
 */
interface StreamRecord {
    chunks: ArrayBuffer[];
    done: boolean;
    listeners: Set<(pcm: ArrayBuffer | null) => void>;
}

/**
 * A passage that is generated or generating. The text it was made from is kept
 * alongside it so a document edit can tell which queued passages are still
 * valid and which have to be thrown away - see applySentenceUpdate.
 */
interface PrefetchEntry {
    promise: Promise<AudioBuffer>;
    controller: AbortController;
    text: string;
    /** Set once the passage is fully generated and ready to play as one buffer. */
    settled?: boolean;
    /**
     * Let this generation finish even when playback has moved past it.
     *
     * Set for a passage played as it generated: the listener has heard it, so
     * cancelling the last of it only means it never gets stored.
     */
    keepToCompletion?: boolean;
    /**
     * Fragments for this particular generation, when the bypass is on.
     *
     * Held on the entry rather than in a map keyed by position. Keying by
     * position aliased: jumping back re-queued the same index, and when the
     * abandoned generation's abort landed it removed the *new* entry's
     * fragments, leaving playback waiting on a stream that would never fill.
     */
    stream?: StreamRecord;
}

export enum AppState {
    IDLE,
    PROCESSING,
    READY,
    PLAYING,
    PAUSED,
    ERROR,
}

interface AudioState {
    appState: AppState;
    setAppState: (state: AppState) => void;
    currentSentenceIndex: number;
    setCurrentSentenceIndex: React.Dispatch<React.SetStateAction<number>>;
    sentencesRef: React.MutableRefObject<string[]>;
    handlePlay: () => void;
    handlePause: () => void;
    handleStop: () => void;
    handleSkipForward: () => void;
    handleSkipBackward: () => void;
    error: string | null;
    setError: (error: string | null) => void;
    smoothPlayback: boolean;
    setSmoothPlayback: (smooth: boolean) => void;
    voiceMode: 'browser' | 'gemini';
    setVoiceMode: React.Dispatch<React.SetStateAction<'browser' | 'gemini'>>;
    selectedVoiceURI: string | null;
    setSelectedVoiceURI: (uri: string | null) => void;
    selectedGeminiVoice: string;
    setSelectedGeminiVoice: (voice: string) => void;
    voices: SpeechSynthesisVoice[];
    /**
     * Character offset within the current sentence that is being spoken, or
     * null when nothing is. Browser speech reports real word boundaries;
     * Gemini audio has no per-word timing, so its position is estimated.
     */
    spokenCharIndex: number | null;
    /** Swap in an edited document without disturbing playback. */
    applySentenceUpdate: (next: string[], oldToNew: (number | null)[]) => void;
}

export const useAudioEngine = (
    geminiConfig: GeminiApiConfig | null,
    generateAudioForSentence: (
        text: string, signal?: AbortSignal, onChunk?: (pcm: ArrayBuffer) => void, priority?: number,
    ) => Promise<NarrationResult>,
    /** Identity of the loaded document; null disables caching (nothing to key on). */
    documentId: string | null = null,
    documentName: string = '',
): AudioState => {
    const [appState, setAppState] = useState<AppState>(AppState.IDLE);
    const [currentSentenceIndex, setCurrentSentenceIndex] = useState<number>(-1);
    const [error, setError] = useState<string | null>(null);
    const [smoothPlayback, setSmoothPlayback] = useState<boolean>(true);
    const [voiceMode, setVoiceMode] = useState<'browser' | 'gemini'>('browser');
    // Restore the last voice on load. App.tsx has always written this on change,
    // but nothing ever read it back, so every reload dropped you onto the system
    // default and the choice had to be made again.
    const [selectedVoiceURI, setSelectedVoiceURI] = useState<string | null>(() => {
        try { return localStorage.getItem('selectedVoiceURI'); } catch { return null; }
    });
    const [selectedGeminiVoice, setSelectedGeminiVoice] = useState<string>(() => {
        try {
            const saved = localStorage.getItem('geminiAudiobookConfig');
            const voice = saved ? JSON.parse(saved).voice : null;
            return typeof voice === 'string' && voice ? voice : 'Aoede';
        } catch { return 'Aoede'; }
    });
    const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
    const [spokenCharIndex, setSpokenCharIndex] = useState<number | null>(null);
    const wordTimerRef = useRef<number | null>(null);
    // Bumped to make the playback effect re-run when the sentence to play has
    // not changed number - resuming on a passage that was edited underneath us.
    const [playNonce, setPlayNonce] = useState(0);

    const audioContextRef = useRef<AudioContext | null>(null);
    const currentAudioSourceRef = useRef<AudioBufferSourceNode | null>(null);
    const sentencesRef = useRef<string[]>([]);
    const appStateRef = useRef<AppState>(appState);
    /** "<mode>:<index>" of the sentence already started, so it is not restarted. */
    const startedTokenRef = useRef<string | null>(null);
    /** Latest playing index, readable from callbacks without re-creating them. */
    const currentIndexRef = useRef<number>(-1);

    // Look-ahead queue of sentences already being generated, keyed by index.
    //
    // This replaces a single prefetch slot that was abandoned and re-created on
    // every advance: only one sentence could ever be in flight, so if a sentence
    // took longer to generate than the previous one took to play, playback sat
    // silent for the difference. Holding several in flight lets generation run
    // ahead of playback and absorb the slow ones.
    //
    // Requests are serialised on the shared socket (see useGemini), so a depth of
    // N queues N turns back-to-back rather than firing them concurrently - the
    // pipeline simply stays fed.
    // How many sentences to keep generated-or-generating ahead of the one
    // playing. The queue tops itself up the moment any prefetch finishes, not
    // only when playback advances, so a run of short sentences lets generation
    // pull further ahead instead of restarting the chain at each boundary.
    const PREFETCH_DEPTH = 4;
    const prefetchQueueRef = useRef<Map<number, PrefetchEntry>>(new Map());
    const activePlayerRef = useRef<PcmStreamPlayer | null>(null);
    /**
     * Where playback should go when the current audio ends, when that is not
     * simply the next passage - set when an edit has left the audio being played
     * detached from the document, so the passage it moved to is not skipped.
     */
    const nextIndexOverrideRef = useRef<number | null>(null);

    const consoleLogger = useRef({
        logAudio: (action: string, details: string) => console.log(`[Audio] ${action}: ${details}`),
    });

    useEffect(() => { appStateRef.current = appState; }, [appState]);
    useEffect(() => { currentIndexRef.current = currentSentenceIndex; }, [currentSentenceIndex]);
    // Read by applySentenceUpdate, which must not be rebuilt when the engine
    // changes or it would churn the file watcher that holds it.
    const voiceModeRef = useRef(voiceMode);
    useEffect(() => { voiceModeRef.current = voiceMode; }, [voiceMode]);

    const getAudioContext = useCallback(() => {
        if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
            audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }
        return audioContextRef.current;
    }, []);

    const resetPlaybackState = useCallback(() => {
        consoleLogger.current.logAudio('Reset', 'Playback state cleared');
        window.speechSynthesis.cancel();
        if (currentAudioSourceRef.current) {
            currentAudioSourceRef.current.onended = null;
            try { currentAudioSourceRef.current.stop(); } catch (e) { }
            currentAudioSourceRef.current = null;
        }
        activePlayerRef.current?.stop();
        activePlayerRef.current = null;
        nextIndexOverrideRef.current = null;
        for (const { promise, controller } of prefetchQueueRef.current.values()) {
            controller.abort();
            promise.catch(() => { });  // queued rejections are expected once aborted
        }
        prefetchQueueRef.current.clear();
        startedTokenRef.current = null;
        if (wordTimerRef.current !== null) {
            cancelAnimationFrame(wordTimerRef.current);
            wordTimerRef.current = null;
        }
        setSpokenCharIndex(null);
    }, []);

    // Voice list population
    useEffect(() => {
        const populateVoiceList = () => {
            const newVoices = window.speechSynthesis.getVoices();
            if (newVoices.length === 0) return;
            setVoices(newVoices);

            // Voices arrive asynchronously and vary by machine, so a restored
            // choice is only honoured once it is confirmed to still exist. If it
            // has gone (different device, uninstalled voice), fall back rather
            // than leaving a selection that cannot speak.
            setSelectedVoiceURI(current => {
                if (current && newVoices.some(v => v.voiceURI === current)) return current;
                const fallback = newVoices.find(v => v.lang.startsWith('en') && v.default) || newVoices[0];
                return fallback.voiceURI;
            });
        };
        populateVoiceList();
        speechSynthesis.onvoiceschanged = populateVoiceList;
        return () => {
            speechSynthesis.onvoiceschanged = null;
            resetPlaybackState();
        };
        // selectedVoiceURI is deliberately not a dependency: the setter above
        // reads the current value functionally, and listing it here tore down
        // and re-subscribed the voiceschanged handler on every voice change.
    }, [resetPlaybackState]);

    // Persist the choice here rather than only in the change handler, so it is
    // remembered however it was set.
    useEffect(() => {
        if (!selectedVoiceURI) return;
        try { localStorage.setItem('selectedVoiceURI', selectedVoiceURI); } catch { /* non-fatal */ }
    }, [selectedVoiceURI]);

    /**
     * Move on once a passage has finished being spoken.
     *
     * Normally that is the next passage. After an edit replaced or removed the
     * one being spoken, the position it moved to has not been read yet, so
     * playback resumes *at* it - stepping over it is what skipped a passage
     * after every source change. The number may be unchanged in that case, so
     * the started-token is cleared and the effect nudged, or nothing would
     * restart.
     */
    const advanceAfterPassage = useCallback(() => {
        const override = nextIndexOverrideRef.current;
        nextIndexOverrideRef.current = null;
        if (override === null) {
            setCurrentSentenceIndex(prev => prev + 1);
            return;
        }
        startedTokenRef.current = null;
        setCurrentSentenceIndex(override);
        setPlayNonce(n => n + 1);
    }, []);

    /** Drop queued sentences we have already moved past, aborting their work. */
    const prunePrefetchQueue = useCallback((beforeIndex: number) => {
        for (const [i, entry] of [...prefetchQueueRef.current.entries()]) {
            if (i < beforeIndex) {
                // A passage played as it generated is nearly finished and worth
                // keeping: aborting it here is what stopped it ever reaching the
                // manager. It was heard, so let it finish and be stored.
                if (!entry.keepToCompletion) {
                    entry.controller.abort();
                    entry.promise.catch(() => { });
                }
                prefetchQueueRef.current.delete(i);
            }
        }
    }, []);

    /**
     * Forget buffers held in memory once the stored copy has gone.
     *
     * Deleting a clip to force a regeneration replayed the deleted audio: the
     * look-ahead was still holding the buffer it had already produced, and never
     * looked at the store again. Anything already generated is dropped so the
     * next play goes back to the cache - which is now empty for that passage, so
     * it regenerates. Work still in flight is left alone.
     */
    useEffect(() => subscribe(event => {
        if (event.type !== 'removed') return;
        for (const [i, entry] of [...prefetchQueueRef.current.entries()]) {
            if (!entry.settled) continue;
            if (i === currentIndexRef.current) continue;   // do not cut off what is playing
            entry.promise.catch(() => { });
            prefetchQueueRef.current.delete(i);
        }
    }), []);

    /**
     * Get audio for one sentence, from the cache when we already have it.
     *
     * Every request for narration funnels through here - the sentence being
     * played and each look-ahead alike - so a clip is stored exactly once and
     * replaying a passage costs nothing. Cache trouble is never fatal: any
     * failure falls through to generating it again.
     */
    const requestAudio = useCallback(async (
        index: number, text: string, signal?: AbortSignal, onChunk?: (pcm: ArrayBuffer) => void,
    ): Promise<AudioBuffer> => {
        const context = getAudioContext();
        const voice = geminiConfig?.voice ?? '';
        const model = geminiConfig?.model ?? '';
        const saving = isSavingEnabled();
        let key: string | null = null;

        // With saving off nothing stored is used either: every passage is
        // generated live. Reading the cache while refusing to write it would
        // still replay old audio for a document being worked on, which is the
        // opposite of what turning saving off is for.
        if (documentId && saving) {
            try {
                // Found by its words, so a passage keeps its audio however far an
                // edit above has moved it.
                key = await makeClipKey({ documentId, text, voice, model });
                let hit = await getClip(key, context);

                if (!hit) {
                    // Clips generated before this keying change are stored under
                    // the old position-based key; take them over rather than
                    // paying to generate them all again.
                    const legacyKey = await makeLegacyClipKey({ documentId, index, voice, model });
                    const legacy = await getClip(legacyKey, context);
                    if (legacy && legacy.meta.text === text && await adoptLegacyClip(legacyKey, key)) {
                        consoleLogger.current.logAudio(
                            'Adopted', `Sentence ${index} from the previous cache layout`);
                        hit = legacy;
                    }
                }

                if (hit) {
                    consoleLogger.current.logAudio(
                        'Cache hit',
                        `Sentence ${index} (${hit.meta.durationSec.toFixed(1)}s, no API call)`,
                    );
                    // The manager lists and jumps by position, so keep it current
                    // when a passage has shifted.
                    if (hit.meta.index !== index) void updateClipPosition(key, index);
                    noteActivity(index, text, 'hit');
                    return hit.buffer;
                }
            } catch (error) {
                console.warn(`Cache lookup failed for sentence ${index}, generating:`, error);
            }
        }

        noteActivity(index, text, 'generating');
        let result: NarrationResult;
        try {
            // Read the passage without its visual rules. The text stored with
            // the clip stays the source text, so markers still compare against
            // what the document actually says.
            // The position doubles as the priority: whichever passage playback
            // will reach first is the one a free lane picks up.
            result = await generateAudioForSentence(narratableText(text), signal, onChunk, index);
        } catch (error) {
            noteActivity(index, text, 'idle');
            throw error;
        }

        // Stored even if the request was abandoned part-way through. The audio is
        // finished and correct for this position; throwing it away because
        // playback moved on is what left gaps in the manager - a passage played
        // but never listed, with the one after it saved in its place. A clip made
        // from text that has since changed is caught on read, not here.
        if (key && documentId && saving) {
            const pcm = audioBufferToPcm16(result.buffer);
            // Not awaited: storing must never delay playback.
            void putClip({
                key, documentId, documentName, index, text,
                spokenText: result.spokenText,
                voice, model,
                bytes: pcm.byteLength,
                durationSec: result.buffer.duration,
                sampleRate: result.buffer.sampleRate,
            }, pcm).then(() => noteActivity(index, text, 'saved'));
        } else {
            noteActivity(index, text, 'idle');
        }
        return result.buffer;
    }, [geminiConfig, documentId, documentName, generateAudioForSentence, getAudioContext]);

    /** Queue one sentence if it isn't queued already. Returns its promise. */
    const enqueuePrefetch = useCallback((index: number): Promise<AudioBuffer> | null => {
        if (index < 0 || index >= sentencesRef.current.length) return null;

        const existing = prefetchQueueRef.current.get(index);
        if (existing) return existing.promise;

        const text = sentencesRef.current[index];
        if (!text) return null;
        // Nothing to say: never spend a call on a passage that is only a rule.
        if (!isNarratable(text)) return null;

        const controller = new AbortController();
        consoleLogger.current.logAudio('Prefetching', `Sentence ${index}`);

        // With the bypass on, keep the fragments as they arrive so this passage
        // can start playing before it has finished generating.
        const record: StreamRecord | null = isStreamingEnabled()
            ? { chunks: [], done: false, listeners: new Set() }
            : null;
        const onChunk = record
            ? (pcm: ArrayBuffer) => {
                record!.chunks.push(pcm);
                for (const listener of record!.listeners) listener(pcm);
            }
            : undefined;

        const promise = requestAudio(index, text, controller.signal, onChunk);

        const closeRecord = () => {
            if (!record || record.done) return;
            record.done = true;
            for (const listener of record.listeners) listener(null);
        };

        // Attach handlers that never reject, so an unclaimed queue entry can't
        // surface as an unhandled rejection while it waits to be played.
        promise.then(
            () => {
                const entry = prefetchQueueRef.current.get(index);
                if (entry?.controller === controller) entry.settled = true;
                closeRecord();
                if (!controller.signal.aborted) {
                    consoleLogger.current.logAudio('Prefetched', `Sentence ${index} ready`);
                    // Extend the chain immediately. Waiting for playback to reach
                    // the next sentence meant the look-ahead could never get
                    // further ahead than it started, so a run of short sentences
                    // kept catching up with generation.
                    fillFromRef.current?.(currentIndexRef.current + 1);
                }
            },
            (error) => {
                if (error?.name !== 'AbortError') {
                    console.warn(`Prefetch of sentence ${index} failed, will retry on demand:`, error?.message ?? error);
                }
                // Release anyone waiting on the stream before dropping it, or a
                // streaming playback would sit waiting for fragments forever.
                closeRecord();
                // Only ever drop our own entry. A jump can have re-queued this
                // position already, and removing the newcomer here is what left
                // playback stranded on a stream that never filled.
                if (prefetchQueueRef.current.get(index)?.controller === controller) {
                    prefetchQueueRef.current.delete(index);
                }
            }
        );

        prefetchQueueRef.current.set(index, {
            promise, controller, text, stream: record ?? undefined,
        });
        return promise;
    }, [requestAudio]);

    /** Keep the next PREFETCH_DEPTH sentences after `fromIndex` in flight. */
    const fillPrefetchQueue = useCallback((fromIndex: number) => {
        if (!smoothPlayback) return;
        for (let i = fromIndex; i < fromIndex + PREFETCH_DEPTH; i++) {
            enqueuePrefetch(i);
        }
    }, [smoothPlayback, enqueuePrefetch]);

    // enqueuePrefetch calls back into fillPrefetchQueue when a prefetch lands,
    // which would be a circular dependency between two useCallbacks. A ref
    // breaks the cycle without either having to be recreated.
    const fillFromRef = useRef<((from: number) => void) | null>(null);
    useEffect(() => { fillFromRef.current = fillPrefetchQueue; }, [fillPrefetchQueue]);

    /**
     * Fold an edited version of the document into the running session.
     *
     * Re-reading the file used to mean processing it from scratch: playback
     * stopped, the queue was discarded and the reading position reset, so
     * saving the file mid-listen cut the audio off. Nothing about an edit
     * requires that. Given an alignment between the old and new sentences, this
     * swaps the text underneath the session and leaves everything else running.
     *
     * Three things have to move together for that to hold:
     *
     * - queued work follows its passage to the new position, so an insertion
     *   near the top does not invalidate every passage below it;
     * - the reading position follows the sentence it was on;
     * - the "already started" token follows the position, because the playback
     *   effect keys on it. Without that the index change alone would restart
     *   the sentence currently being spoken - the very interruption this exists
     *   to prevent.
     *
     * Audio already playing is left alone even if its own text changed. It
     * finishes, and the edit is heard when playback next reaches that passage.
     */
    const applySentenceUpdate = useCallback((
        next: string[],
        oldToNew: (number | null)[],
    ) => {
        sentencesRef.current = next;

        const remapped = new Map<number, PrefetchEntry>();
        for (const [oldIndex, entry] of prefetchQueueRef.current) {
            const newIndex = oldIndex < oldToNew.length ? oldToNew[oldIndex] : null;
            // Keep it only if it survived the edit and still matches the text at
            // its new home; anything else would play stale words.
            if (newIndex === null || next[newIndex] !== entry.text) {
                entry.controller.abort();
                entry.promise.catch(() => { });
                continue;
            }
            remapped.set(newIndex, entry);
        }
        prefetchQueueRef.current = remapped;

        const from = currentIndexRef.current;
        if (from >= 0) {
            const to = remapIndex(from, oldToNew, next.length);
            const survived = from < oldToNew.length && oldToNew[from] !== null;

            currentIndexRef.current = to;
            if (startedTokenRef.current !== null) {
                startedTokenRef.current = `${voiceModeRef.current}:${to}`;
            }
            if (to !== from) setCurrentSentenceIndex(to);

            // If the passage being spoken was itself edited or removed, the audio
            // still playing no longer belongs to any passage in the document. It
            // is left to finish, but the position it moved to has not been read
            // yet - so playback must resume *at* it rather than after it, which
            // is what was skipping a passage on every edit.
            nextIndexOverrideRef.current = survived ? null : to;
        }

        // Top the look-ahead back up: passages dropped above leave gaps.
        //
        // Only when the Live engine is the one speaking. Browser speech needs no
        // look-ahead, and filling it here would send the edited passages to the
        // API for audio that is never played - an edit would quietly cost calls
        // while the browser voice is reading.
        if (voiceModeRef.current === 'gemini') {
            fillFromRef.current?.(currentIndexRef.current + 1);
        }
    }, []);

    /**
     * Start a passage that has not finished generating, playing its fragments
     * as they arrive. Returns true when it has taken playback over.
     *
     * This is the bypass for the case where the look-ahead did not get far
     * enough ahead: rather than sitting in silence until the passage is
     * complete, the audio that exists is played immediately and the rest is
     * scheduled behind it as it streams in.
     */
    const playStreamed = useCallback(async (
        index: number, record: StreamRecord,
    ): Promise<boolean> => {
        const audioContext = getAudioContext();
        if (audioContext.state === 'suspended') {
            try { await audioContext.resume(); } catch { return false; }
        }
        // It finished while we were getting ready - the normal path is better.
        if (record.done) return false;

        // Wait for proof that this passage really is streaming before taking it
        // over.
        //
        // A passage served from the cache arrives whole and emits no fragments
        // at all. Committing to the stream on the strength of an unsettled
        // promise meant those played nothing: the record closed empty, the
        // player finished with no audio, and the book raced to the end in
        // silence. The first fragment is the only reliable signal.
        if (record.chunks.length === 0) {
            const streaming = await new Promise<boolean>((resolve) => {
                const probe = (pcm: ArrayBuffer | null) => {
                    record.listeners.delete(probe);
                    resolve(pcm !== null);   // null means it ended without streaming
                };
                record.listeners.add(probe);
            });
            if (!streaming) return false;
        }
        // The listener may have moved on while we waited - a jump, a stop.
        if (appStateRef.current !== AppState.PLAYING || currentIndexRef.current !== index) {
            return false;
        }

        consoleLogger.current.logAudio('Streaming', `Sentence ${index} while it generates`);

        // Heard, so worth storing: let it run to the end even once playback has
        // moved on, instead of being cancelled by the look-ahead's tidy-up.
        const entry = prefetchQueueRef.current.get(index);
        if (entry) entry.keepToCompletion = true;

        const player = new PcmStreamPlayer({
            context: audioContext,
            sampleRate: PCM_SAMPLE_RATE,
            onStarved: () => consoleLogger.current.logAudio(
                'Stream ran dry', `Sentence ${index} - generation fell behind playback`),
            onFinished: () => {
                record.listeners.delete(listener);
                if (activePlayerRef.current !== player) return;  // superseded
                activePlayerRef.current = null;
                if (appStateRef.current === AppState.PLAYING) advanceAfterPassage();
            },
        });

        const listener = (pcm: ArrayBuffer | null) => {
            if (activePlayerRef.current !== player) return;
            if (pcm === null) player.end(); else player.push(pcm);
        };

        activePlayerRef.current = player;
        record.listeners.add(listener);
        // Everything that arrived before playback reached this passage.
        for (const chunk of record.chunks) player.push(chunk);
        if (record.done) player.end();

        // Follow the audio clock for the word highlight. The passage's full
        // length is not known yet, so progress is measured against what has
        // been scheduled so far - it firms up as more arrives.
        const spokenText = sentencesRef.current[index] ?? '';
        const totalChars = spokenText.length || 1;
        const followStream = () => {
            if (appStateRef.current !== AppState.PLAYING || activePlayerRef.current !== player) {
                wordTimerRef.current = null;
                return;
            }
            const scheduled = player.scheduledSeconds;
            if (scheduled > 0) {
                const progress = Math.min(1, Math.max(0, player.elapsedSeconds / scheduled));
                setSpokenCharIndex(Math.floor(progress * totalChars));
            }
            wordTimerRef.current = requestAnimationFrame(followStream);
        };
        if (wordTimerRef.current !== null) cancelAnimationFrame(wordTimerRef.current);
        wordTimerRef.current = requestAnimationFrame(followStream);

        return true;
    }, [getAudioContext, sentencesRef, advanceAfterPassage]);

    const playSentence = useCallback(async (index: number) => {
        if (currentAudioSourceRef.current) {
            currentAudioSourceRef.current.onended = null;
            try { currentAudioSourceRef.current.stop(); } catch (e) { }
        }

        // Anything before this sentence is history; stop paying for it.
        prunePrefetchQueue(index);

        // A passage that is only a divider - the rule above a stat block, a
        // scene break - has nothing to speak. The model answers those with a
        // turn containing no audio, which surfaced as "No audio data received"
        // and paused the book. Move past it instead, keeping the look-ahead fed.
        if (!isNarratable(sentencesRef.current[index] ?? '')) {
            consoleLogger.current.logAudio('Skipping', `Sentence ${index} has no speakable text`);
            fillPrefetchQueue(index + 1);
            window.setTimeout(() => {
                if (appStateRef.current === AppState.PLAYING
                    && currentIndexRef.current === index) advanceAfterPassage();
            }, 200);
            return;
        }

        // Claim THIS sentence before queueing any look-ahead. Turns are
        // serialised in the order they are requested, so filling the look-ahead
        // first would put the sentence the listener is waiting on at the back of
        // the queue - silence until three other sentences had been generated.
        let audioBuffer: AudioBuffer | null = null;
        const queued = prefetchQueueRef.current.get(index)?.promise ?? enqueuePrefetch(index);

        // Now extend the look-ahead behind it.
        fillPrefetchQueue(index + 1);

        if (!queued) {
            console.error(`No text found for sentence ${index}`);
            setError('Failed to generate audio for the selected sentence.');
            setAppState(AppState.PAUSED);
            return;
        }

        // Still generating? With the bypass on, play what exists rather than
        // waiting for the rest. Only worth it when the passage really is not
        // ready - a finished one plays better as a single buffer.
        const pending = prefetchQueueRef.current.get(index);
        const stream = pending?.stream;
        if (pending && !pending.settled && stream && !stream.done) {
            if (await playStreamed(index, stream)) return;
        }

        try {
            audioBuffer = await queued;
            consoleLogger.current.logAudio('Playing', `Sentence ${index}`);
        } catch (error: any) {
            if (error?.name === 'AbortError') return;  // superseded by a seek or stop

            // One retry on demand. A prefetch can fail for reasons that have
            // nothing to do with this sentence (a dropped socket, a transient
            // 1011 from Google), and pausing the whole book on it - which is
            // what used to happen - is far worse than spending one more call.
            console.warn(`Sentence ${index} failed from queue, regenerating:`, error?.message ?? error);
            prefetchQueueRef.current.delete(index);
            try {
                const text = sentencesRef.current[index];
                if (!text) throw new Error(`No text found for sentence ${index}`);
                audioBuffer = await requestAudio(index, text);
            } catch (retryError: any) {
                if (retryError?.name === 'AbortError') return;
                console.error(`Error generating audio for sentence ${index}:`, retryError);
                // Being disconnected is not a failure to explain away - say so
                // plainly, or the reader looks broken when it is simply stopped.
                const message = typeof retryError?.message === 'string'
                    && retryError.message.includes('disconnected')
                    ? retryError.message
                    : 'Failed to generate audio for the selected sentence.';
                setError(message);
                setAppState(AppState.PAUSED);
                return;
            }
        }

        prefetchQueueRef.current.delete(index);

        if (audioBuffer) {
            const audioContext = getAudioContext();

            // Ensure audio context is running (fixes cutoff at beginning)
            // MUST await this to prevent audio from starting before context is ready
            if (audioContext.state === 'suspended') {
                consoleLogger.current.logAudio('Audio Context', 'Resuming from suspended state...');
                await audioContext.resume();
                consoleLogger.current.logAudio('Audio Context', 'Resumed successfully');
            }

            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);
            currentAudioSourceRef.current = source;
            source.onended = () => {
                if (appStateRef.current === AppState.PLAYING) advanceAfterPassage();
            };

            // Top the queue up again: this sentence's duration is now known, so
            // the look-ahead has exactly that long to get the next ones ready.
            fillPrefetchQueue(index + 1);

            source.start();

            // Follow the audio clock to estimate which word is being spoken.
            //
            // Live audio carries no per-word timing, so position is inferred from
            // elapsed time. Weighting by character count rather than spreading
            // words evenly tracks noticeably better, since longer words take
            // longer to say - but it is still an estimate and will drift a little
            // inside a long passage.
            const spokenText = sentencesRef.current[index] ?? '';
            const startedAt = audioContext.currentTime;
            const totalChars = spokenText.length || 1;
            const followAudio = () => {
                if (appStateRef.current !== AppState.PLAYING
                    || currentAudioSourceRef.current !== source) {
                    wordTimerRef.current = null;
                    return;
                }
                const elapsed = audioContext.currentTime - startedAt;
                const progress = Math.min(1, Math.max(0, elapsed / (audioBuffer!.duration || 1)));
                setSpokenCharIndex(Math.floor(progress * totalChars));
                wordTimerRef.current = requestAnimationFrame(followAudio);
            };
            if (wordTimerRef.current !== null) cancelAnimationFrame(wordTimerRef.current);
            wordTimerRef.current = requestAnimationFrame(followAudio);
        }
    }, [requestAudio, getAudioContext, prunePrefetchQueue, fillPrefetchQueue, enqueuePrefetch, playStreamed]);

    const speakWithPersistentVoice = useCallback((text: string, voiceURI: string | null, onEnd?: () => void) => {
        const utterance = new SpeechSynthesisUtterance(text);
        const selectedVoice = voices.find(v => v.voiceURI === voiceURI);

        if (selectedVoice) {
            utterance.voice = selectedVoice;
            const currentVoices = window.speechSynthesis.getVoices();
            const voiceIndex = currentVoices.findIndex(v => v.voiceURI === selectedVoice.voiceURI);
            if (voiceIndex >= 0) {
                utterance.voice = currentVoices[voiceIndex];
            }
            utterance.lang = selectedVoice.lang;
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;
        }

        if (onEnd) {
            utterance.onend = onEnd;
        }

        // Browser speech reports real word boundaries, so the highlight can be
        // exact here rather than estimated.
        utterance.onboundary = (event) => {
            if (event.name === 'word' || event.name === undefined) {
                setSpokenCharIndex(event.charIndex);
            }
        };

        utterance.onerror = (event) => {
            console.warn('TTS utterance error:', event.error);
            // These were 'voice-unavailable' / 'voice-cancelled', neither of which
            // is a SpeechSynthesisErrorCode - the retry-with-default-voice fallback
            // could never fire. These are the real codes for "this voice won't work".
            if (event.error === 'language-unavailable' || event.error === 'synthesis-unavailable') {
                const fallbackUtterance = new SpeechSynthesisUtterance(text);
                fallbackUtterance.onend = onEnd;
                window.speechSynthesis.speak(fallbackUtterance);
            } else if (onEnd) {
                onEnd();
            }
        };

        window.speechSynthesis.speak(utterance);
    }, [voices]);

    // Hand over cleanly when the engine is switched.
    //
    // Nothing used to stop the outgoing engine: switching mid-sentence left
    // browser speech running while Gemini started its own audio, so both played
    // at once, and the look-ahead queue still held work for the old mode. This
    // stops the old engine and clears its queue; the playback effect below then
    // resumes the same sentence on the new one - from saved audio if there is
    // any, which needs no API call at all.
    //
    // Declared before the playback effect so it runs first in the same commit.
    const previousVoiceModeRef = useRef(voiceMode);
    useEffect(() => {
        if (previousVoiceModeRef.current === voiceMode) return;
        previousVoiceModeRef.current = voiceMode;
        resetPlaybackState();
    }, [voiceMode, resetPlaybackState]);

    // Playback effect
    //
    // Guarded so a sentence is only ever started once. This effect depends on
    // several callbacks whose identity changes for reasons unrelated to
    // playback - speakWithPersistentVoice rebuilds whenever the browser's voice
    // list repopulates, playSentence whenever the Gemini config object is
    // replaced. Each of those re-ran the effect mid-sentence and called
    // playSentence again for the *same* index, which stops the audio currently
    // playing and starts it over: the sentence appeared to cut off part-way and
    // the next one to begin early.
    useEffect(() => {
        const sentences = sentencesRef.current;
        const token = `${voiceMode}:${currentSentenceIndex}`;
        if (appState === AppState.PLAYING && startedTokenRef.current === token) return;
        if (appState !== AppState.PLAYING) startedTokenRef.current = null;

        if (appState === AppState.PLAYING && currentSentenceIndex >= 0 && currentSentenceIndex < sentences.length) {
            startedTokenRef.current = token;
            setSpokenCharIndex(null);
            document.getElementById(`sentence-${currentSentenceIndex}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            if (voiceMode === 'browser') {
                if (!window.speechSynthesis.speaking) {
                    window.speechSynthesis.cancel();
                }

                speakWithPersistentVoice(
                    sentences[currentSentenceIndex],
                    selectedVoiceURI,
                    advanceAfterPassage
                );
            } else {
                playSentence(currentSentenceIndex);
            }
        } else if (appState === AppState.PLAYING && currentSentenceIndex >= sentences.length) {
            handleStop();
        }
    }, [currentSentenceIndex, appState, speakWithPersistentVoice, selectedVoiceURI, playSentence, voiceMode, playNonce, advanceAfterPassage]);

    const handleStop = useCallback(() => {
        resetPlaybackState();
        setAppState(AppState.READY);
        setCurrentSentenceIndex(-1);
    }, [resetPlaybackState]);

    const handlePlay = useCallback(() => {
        if (appState === AppState.READY || appState === AppState.IDLE) {
            setAppState(AppState.PLAYING);
            setCurrentSentenceIndex(0);
        } else if (appState === AppState.PAUSED) {
            setAppState(AppState.PLAYING);
        }
    }, [appState]);

    const handlePause = useCallback(() => {
        if (appState === AppState.PLAYING) {
            resetPlaybackState();
            setAppState(AppState.PAUSED);
        }
    }, [appState, resetPlaybackState]);

    const handleSkipBackward = useCallback(() => {
        if (currentSentenceIndex > 0) {
            setCurrentSentenceIndex(prev => prev - 1);
        }
    }, [currentSentenceIndex]);

    const handleSkipForward = useCallback(() => {
        if (currentSentenceIndex < sentencesRef.current.length - 1) {
            setCurrentSentenceIndex(prev => prev + 1);
        }
    }, [currentSentenceIndex]);

    return {
        appState,
        setAppState,
        currentSentenceIndex,
        setCurrentSentenceIndex,
        sentencesRef,
        handlePlay,
        handlePause,
        handleStop,
        handleSkipForward,
        handleSkipBackward,
        error,
        setError,
        smoothPlayback,
        setSmoothPlayback,
        voiceMode,
        setVoiceMode,
        selectedVoiceURI,
        setSelectedVoiceURI,
        selectedGeminiVoice,
        setSelectedGeminiVoice,
        voices,
        spokenCharIndex,
        applySentenceUpdate
    };
};
