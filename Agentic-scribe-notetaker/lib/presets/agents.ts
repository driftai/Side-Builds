/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/

/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export const INTERLOCUTOR_VOICES = [
  'Aoede',
  'Charon',
  'Fenrir',
  'Kore',
  'Leda',
  'Orus',
  'Puck',
  'Zephyr',
] as const;

export type INTERLOCUTOR_VOICE = (typeof INTERLOCUTOR_VOICES)[number];

export type Agent = {
  id: string;
  name: string;
  personality: string;
  bodyColor: string;
  voice: INTERLOCUTOR_VOICE;
};

import {
  AMELIE_PERSONALITY,
  ARI_PERSONALITY,
  HANS_PERSONALITY,
  HIRO_PERSONALITY,
  JIWON_PERSONALITY,
  MEI_PERSONALITY,
  RAMON_PERSONALITY,
  SCRIBE_PERSONALITY,
} from './personalities/language-core';
import {
  DEFNE_PERSONALITY,
  GAUSS_PERSONALITY,
  INES_PERSONALITY,
  KARIM_PERSONALITY,
  LUCA_PERSONALITY,
  NEWTON_PERSONALITY,
  OLGA_PERSONALITY,
  RAHUL_PERSONALITY,
  REZA_PERSONALITY,
} from './personalities/language-extended';

/**
 * Alice (English)
 * The default English-speaking scribe.
 */
export const Alice: Agent = {
  id: 'alice',
  name: 'Alice (English)',
  personality: SCRIBE_PERSONALITY,
  bodyColor: '#25C1E0', // cyan
  voice: 'Leda',
};

/**
 * Sam (English)
 * A yellow-themed English scribe.
 */
export const Sam: Agent = {
  id: 'sam',
  name: 'Sam (English)',
  personality: SCRIBE_PERSONALITY,
  bodyColor: '#fbbc04', // yellow
  voice: 'Fenrir',
};

/**
 * Irene (English)
 * A pink-themed English scribe.
 */
export const Irene: Agent = {
  id: 'irene',
  name: 'Irene (English)',
  personality: SCRIBE_PERSONALITY,
  bodyColor: '#f538a0', // pink
  voice: 'Zephyr',
};

/**
 * Tom (English)
 * An orange-themed English scribe.
 */
export const Tom: Agent = {
  id: 'tom',
  name: 'Tom (English)',
  personality: SCRIBE_PERSONALITY,
  bodyColor: '#fa7b17', // orange
  voice: 'Charon',
};

/**
 * Rahul (Hindi)
 * A scribe that speaks Hinglish and writes in Hindi.
 */
export const Rahul: Agent = {
  id: 'rahul',
  name: 'Rahul (Hindi)',
  personality: RAHUL_PERSONALITY,
  bodyColor: '#34a853', // green
  voice: 'Fenrir',
};

/**
 * Ramon (Spanish)
 * A creative scribe that speaks and writes in Spanish.
 */
export const Ramon: Agent = {
  id: 'ramon',
  name: 'Ramon (Spanish)',
  personality: RAMON_PERSONALITY,
  bodyColor: '#4285F4', // blue (same as Newton)
  voice: 'Fenrir',
};

/**
 * Amelie (French)
 * A scribe that speaks and writes in French.
 */
export const Amelie: Agent = {
  id: 'amelie',
  name: 'Amelie (French)',
  personality: AMELIE_PERSONALITY,
  bodyColor: '#9C27B0', // purple
  voice: 'Zephyr',
};

/**
 * Ari (Hebrew)
 * A scribe that speaks and writes in Hebrew.
 */
export const Ari: Agent = {
  id: 'ari',
  name: 'Ari (Hebrew)',
  personality: ARI_PERSONALITY,
  bodyColor: '#FFF9C4', // pale yellow
  voice: 'Charon',
};

/**
 * Mei (Chinese)
 * A scribe that speaks and writes in Mandarin Chinese.
 */
export const Mei: Agent = {
  id: 'mei',
  name: 'Mei (Chinese)',
  personality: MEI_PERSONALITY,
  bodyColor: '#FFCDD2', // pale red/pink
  voice: 'Kore',
};

/**
 * Hiro (Japanese)
 * A scribe that speaks and writes in Japanese.
 */
export const Hiro: Agent = {
  id: 'hiro',
  name: 'Hiro (Japanese)',
  personality: HIRO_PERSONALITY,
  bodyColor: '#fbbc04', // yellow
  voice: 'Fenrir',
};

/**
 * Ji-won (Korean)
 * A scribe that speaks and writes in Korean.
 */
export const Jiwon: Agent = {
  id: 'jiwon',
  name: 'Ji-won (Korean)',
  personality: JIWON_PERSONALITY,
  bodyColor: '#F3E5F5', // pale purple
  voice: 'Aoede',
};

/**
 * Hans (German)
 * A scribe that speaks and writes in German.
 */
export const Hans: Agent = {
  id: 'hans',
  name: 'Hans (German)',
  personality: HANS_PERSONALITY,
  bodyColor: '#FFEB3B', // yellow
  voice: 'Orus',
};

/**
 * Newton (Math)
 * A specialized scribe for mathematical documents using LaTeX.
 */
export const Newton: Agent = {
  id: 'newton',
  name: 'Newton (Math)',
  personality: NEWTON_PERSONALITY,
  bodyColor: '#4285F4', // blue
  voice: 'Orus',
};

/**
 * Defne (Turkish)
 * A scribe that speaks and writes in Turkish.
 */
export const Defne: Agent = {
  id: 'defne',
  name: 'Defne (Turkish)',
  personality: DEFNE_PERSONALITY,
  bodyColor: '#009688', // Teal
  voice: 'Zephyr',
};

/**
 * Karim (Arabic)
 * A scribe that speaks and writes in Arabic.
 */
export const Karim: Agent = {
  id: 'karim',
  name: 'Karim (Arabic)',
  personality: KARIM_PERSONALITY,
  bodyColor: '#FFF9C4', // pale yellow (same as Ari)
  voice: 'Fenrir',
};

/**
 * Reza (Farsi)
 * A scribe that speaks and writes in Farsi.
 */
export const Reza: Agent = {
  id: 'reza',
  name: 'Reza (Farsi)',
  personality: REZA_PERSONALITY,
  bodyColor: '#fbbc04', // yellow
  voice: 'Fenrir',
};

/**
 * InÃªs (Portuguese)
 * A scribe that speaks and writes in Portuguese.
 */
export const Ines: Agent = {
  id: 'ines',
  name: 'InÃªs (Portuguese)',
  personality: INES_PERSONALITY,
  bodyColor: '#9C27B0', // purple (same as Amelie)
  voice: 'Zephyr',
};

/**
 * Olga (Russian)
 * A scribe that speaks and writes in Russian.
 */
export const Olga: Agent = {
  id: 'olga',
  name: 'Olga (Russian)',
  personality: OLGA_PERSONALITY,
  bodyColor: '#9C27B0', // purple (same as Amelie)
  voice: 'Zephyr',
};

/**
 * Luca (Italian)
 * A scribe that speaks and writes in Italian.
 */
export const Luca: Agent = {
  id: 'luca',
  name: 'Luca (Italian)',
  personality: LUCA_PERSONALITY,
  bodyColor: '#4285F4', // blue (same as Ramon)
  voice: 'Fenrir',
};
