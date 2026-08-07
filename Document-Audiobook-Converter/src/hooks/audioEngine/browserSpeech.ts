interface BrowserSpeechOptions {
    text: string;
    voiceURI: string | null;
    voices: SpeechSynthesisVoice[];
    onEnd?: () => void;
    onBoundary: (charIndex: number) => void;
}

export const speakWithPersistentVoice = ({
    text,
    voiceURI,
    voices,
    onEnd,
    onBoundary,
}: BrowserSpeechOptions): void => {
    const utterance = new SpeechSynthesisUtterance(text);
    const selectedVoice = voices.find(voice => voice.voiceURI === voiceURI);

    if (selectedVoice) {
        utterance.voice = selectedVoice;
        const currentVoices = window.speechSynthesis.getVoices();
        const voiceIndex = currentVoices.findIndex(voice => voice.voiceURI === selectedVoice.voiceURI);
        if (voiceIndex >= 0) utterance.voice = currentVoices[voiceIndex];
        utterance.lang = selectedVoice.lang;
        utterance.rate = 1;
        utterance.pitch = 1;
        utterance.volume = 1;
    }

    utterance.onend = onEnd ?? null;
    utterance.onboundary = event => {
        if (event.name === 'word' || event.name === undefined) onBoundary(event.charIndex);
    };
    utterance.onerror = event => {
        console.warn('TTS utterance error:', event.error);
        if (event.error === 'language-unavailable' || event.error === 'synthesis-unavailable') {
            const fallback = new SpeechSynthesisUtterance(text);
            fallback.onend = onEnd ?? null;
            window.speechSynthesis.speak(fallback);
        } else {
            onEnd?.();
        }
    };

    window.speechSynthesis.speak(utterance);
};
