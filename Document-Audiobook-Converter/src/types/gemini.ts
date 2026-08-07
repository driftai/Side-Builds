export interface GeminiApiConfig {
    apiKey: string;
    model: string;
    allowModelOverride: boolean;
    temperature: number;
    maxTokens: number;
    timeout: number;
    websocketUrl: string;
    voice: string;
    instructions: string;
}

export type GeminiConnectionState =
    | 'disconnected'
    | 'connecting'
    | 'connected'
    | 'error';

/**
 * One narrated passage, including the model's own transcript for drift checks.
 */
export interface NarrationResult {
    buffer: AudioBuffer;
    spokenText: string;
}
