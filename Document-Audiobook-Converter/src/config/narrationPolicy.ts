/** Must match the backend's mandatory narration-policy version. */
export const NARRATION_POLICY_VERSION = 'strict-verbatim-v2';
export const STYLE_INSTRUCTION_MAX_CHARS = 8000;

/** Mirrors the backend normalization used for effective delivery guidance. */
export const normalizeNarrationStyle = (instructions = ''): string =>
    instructions.replace(/\s+/g, ' ').trim().slice(0, STYLE_INSTRUCTION_MAX_CHARS);

export interface NarrationStylePreset {
    label: string;
    instructions: string;
}

export const NARRATION_STYLE_PRESETS: readonly NarrationStylePreset[] = [
    {
        label: 'Strict Textbook',
        instructions: 'Use precise textbook diction, steady pacing, neutral emphasis, and clear pronunciation for headings, lists, symbols, and technical terms.',
    },
    {
        label: 'Natural Southern',
        instructions: 'Use a warm, natural Southern U.S. cadence with subtle regional color. Avoid caricature and do not add clichés, greetings, or honorifics.',
    },
];
