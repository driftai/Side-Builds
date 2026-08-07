import { describe, expect, it } from 'vitest';
import {
    NARRATION_POLICY_VERSION,
    NARRATION_STYLE_PRESETS,
    normalizeNarrationStyle,
    STYLE_INSTRUCTION_MAX_CHARS,
} from '../src/config/narrationPolicy';

describe('narration policy', () => {
    it('provides the two supported delivery presets', () => {
        expect(NARRATION_STYLE_PRESETS.map(preset => preset.label)).toEqual([
            'Strict Textbook',
            'Natural Southern',
        ]);
        expect(NARRATION_STYLE_PRESETS.every(preset => preset.instructions.length < 180)).toBe(true);
    });

    it('keeps the Southern preset subtle and prohibits added social flourishes', () => {
        const southern = NARRATION_STYLE_PRESETS.find(
            preset => preset.label === 'Natural Southern',
        )?.instructions ?? '';
        expect(southern).toContain('subtle');
        expect(southern).toContain('do not add');
        expect(southern).toContain('greetings');
        expect(southern).toContain('honorifics');
    });

    it('normalizes style exactly as the backend does and enforces the UI cap', () => {
        expect(normalizeNarrationStyle('  slow\n\n and   steady  ')).toBe('slow and steady');
        expect(normalizeNarrationStyle('x'.repeat(9000))).toHaveLength(
            STYLE_INSTRUCTION_MAX_CHARS,
        );
        expect(NARRATION_POLICY_VERSION).toBe('strict-verbatim-v2');
    });
});
