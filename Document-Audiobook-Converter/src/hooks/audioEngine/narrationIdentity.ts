import type { GeminiApiConfig } from '../../types/gemini';

/** Fields that change the voice or content of generated narration. */
export const getNarrationIdentity = (config: GeminiApiConfig | null): string | null => (
    config
        ? JSON.stringify([
            config.model,
            config.allowModelOverride,
            config.voice,
            config.instructions,
        ])
        : null
);
