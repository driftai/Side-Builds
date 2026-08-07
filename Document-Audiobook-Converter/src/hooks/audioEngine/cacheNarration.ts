import type { GeminiApiConfig, NarrationResult } from '../../types/gemini';
import {
    adoptLegacyClip,
    audioBufferToPcm16,
    getClip,
    isSavingEnabled,
    makeClipKey,
    makeLegacyClipKey,
    noteActivity,
    putClip,
    updateClipPosition,
} from '../../utils/audioCache';
import { narratableText } from '../../utils/textProcessing';
import type { GenerateAudioForSentence } from './types';

interface NarrationCacheRequest {
    index: number;
    text: string;
    signal?: AbortSignal;
    onChunk?: (pcm: ArrayBuffer) => void;
    geminiConfig: GeminiApiConfig | null;
    documentId: string | null;
    documentName: string;
    getAudioContext: () => AudioContext;
    generateAudioForSentence: GenerateAudioForSentence;
    logAudio: (action: string, details: string) => void;
}

export const requestNarrationAudio = async ({
    index,
    text,
    signal,
    onChunk,
    geminiConfig,
    documentId,
    documentName,
    getAudioContext,
    generateAudioForSentence,
    logAudio,
}: NarrationCacheRequest): Promise<AudioBuffer> => {
    const context = getAudioContext();
    const voice = geminiConfig?.voice ?? '';
    const model = geminiConfig?.model ?? '';
    const saving = isSavingEnabled();
    let key: string | null = null;

    if (documentId && saving) {
        try {
            key = await makeClipKey({ documentId, text, voice, model });
            let hit = await getClip(key, context);
            if (!hit) {
                const legacyKey = await makeLegacyClipKey({ documentId, index, voice, model });
                const legacy = await getClip(legacyKey, context);
                if (legacy && legacy.meta.text === text && await adoptLegacyClip(legacyKey, key)) {
                    logAudio('Adopted', `Sentence ${index} from the previous cache layout`);
                    hit = legacy;
                }
            }
            if (hit) {
                logAudio('Cache hit', `Sentence ${index} (${hit.meta.durationSec.toFixed(1)}s, no API call)`);
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
        result = await generateAudioForSentence(narratableText(text), signal, onChunk, index);
    } catch (error) {
        noteActivity(index, text, 'idle');
        throw error;
    }

    if (key && documentId && saving) {
        const pcm = audioBufferToPcm16(result.buffer);
        void putClip({
            key,
            documentId,
            documentName,
            index,
            text,
            spokenText: result.spokenText,
            voice,
            model,
            bytes: pcm.byteLength,
            durationSec: result.buffer.duration,
            sampleRate: result.buffer.sampleRate,
        }, pcm).then(() => noteActivity(index, text, 'saved'));
    } else {
        noteActivity(index, text, 'idle');
    }
    return result.buffer;
};
