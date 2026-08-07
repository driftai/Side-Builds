import { describe, it, expect } from 'vitest';
import { compareNarration } from '../src/utils/audioCache';

/**
 * The markers exist so a passage can be judged at a glance and acted on. They
 * are only worth having if they are honest: a green that hides drift is useless,
 * and a red on narration that was fine sends you regenerating audio that was
 * never wrong.
 */
describe('compareNarration', () => {
    it('calls a faithful reading green', () => {
        const line = 'The road was wet from the night rain';
        const r = compareNarration(line, line);
        expect(r.level).toBe('match');
        expect(r.label).toBe('read word for word');
    });

    it('calls an edited source against older audio orange', () => {
        // The source now says one thing and the stored narration says another:
        // drift, not divergence.
        expect(compareNarration('Hello To One', 'Hello To All').level).toBe('drift');
    });

    it('tolerates one word in thirteen', () => {
        const source = 'The fishermen gathered their nets and spoke in low voices about the weather';
        expect(compareNarration(source, source.replace('weather', 'harbour')).level).toBe('match');
    });

    it('calls unrelated narration red', () => {
        expect(compareNarration(
            'The fishermen gathered their nets and spoke in low voices about the weather',
            'A completely different line about something else entirely happening far away',
        ).level).toBe('diverged');
    });

    it('calls a passage the model carried on past red, not mild drift', () => {
        // Every source word is present and in order, so overlap alone scores this
        // around two thirds. Length is what gives it away.
        const source = 'She closed the door behind her and walked into the rain.';
        const spoken = `${source} The street was empty and the lamps had not yet come on that evening.`;
        const r = compareNarration(source, spoken);
        expect(r.level).toBe('diverged');
        expect(r.label).toMatch(/x the source/);
    });

    it('does not flag a couple of extra words on a very short line', () => {
        expect(compareNarration('Hello To All', 'Hello To All Everyone').level).not.toBe('diverged');
    });

    it('reports a missing transcript as unknown rather than a false red', () => {
        const r = compareNarration('Some source text here that is long enough', '');
        expect(r.level).toBe('unknown');
        expect(r.label).toBe('no transcript stored');
    });

    it('refuses to judge a transcript too short for the audio it came with', () => {
        // The session sometimes reports only the opening of a long passage while
        // the audio is complete and correct.
        const source = 'Name: Leon kirumi. Race: Human. Class: Hero, Grand Magician, Tamer. '
            + 'Level one. Health six hundred. Class skills: Holy Sword Summon.';
        const r = compareNarration(source, 'Name: Leon', 57);
        expect(r.level).toBe('unknown');
        expect(r.label).toMatch(/transcript incomplete/);
    });

    it('still judges a stub transcript when the audio is short too', () => {
        // Here the narration really did stop early, which is worth flagging.
        const source = 'Name: Leon kirumi. Race: Human. Class: Hero, Grand Magician, Tamer.';
        expect(compareNarration(source, 'Name: Leon', 1.5).level).not.toBe('unknown');
    });

    it('is unaffected when no duration is known', () => {
        const line = 'The lighthouse blinked twice across the bay.';
        expect(compareNarration(line, line).level).toBe('match');
    });
});
