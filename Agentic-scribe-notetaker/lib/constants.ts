/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/
/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * Default Live API model to use
 */
export const DEFAULT_LIVE_API_MODEL = 'gemini-3.1-flash-live-preview';
export const DEFAULT_IMAGE_MODEL = 'gemini-3.1-flash-image-preview';

export const LIVE_MODEL_PRESETS = [
  { label: '3.1 Flash Live (Preview)', id: DEFAULT_LIVE_API_MODEL },
  { label: '2.5 Flash Native Audio - 12-2025', id: 'gemini-2.5-flash-native-audio-preview-12-2025' },
] as const;

const LEGACY_LIVE_MODEL_ALIASES: Record<string, string> = {
  'gemini-2.5-flash-live-preview': 'gemini-2.5-flash-native-audio-preview-12-2025',
  'gemini-live-2.5-flash-preview': 'gemini-2.5-flash-native-audio-preview-12-2025',
  'gemini-2.5-flash-native-audio-preview-09-2025': 'gemini-2.5-flash-native-audio-preview-12-2025',
};

export const normalizeLiveApiModel = (model: string | null | undefined): string => {
  const trimmed = model?.trim();
  if (!trimmed) return DEFAULT_LIVE_API_MODEL;
  return LEGACY_LIVE_MODEL_ALIASES[trimmed.toLowerCase()] ?? trimmed;
};

export const FONT_OPTIONS = [
  'Arial',
  'Verdana',
  'Georgia',
  'Times New Roman',
  'Courier New',
  'Roboto',
  'Open Sans',
  'Lato',
  'Montserrat',
  'Playfair Display',
  'Merriweather',
  'Inter',
  'Space Mono',
];

export const IMAGE_MODEL_OPTIONS = [
  DEFAULT_IMAGE_MODEL,
  'gemini-2.5-flash-image',
  'gemini-3-pro-image-preview',
  'imagen-4.0-generate-001',
];

export const IMAGE_GENERATION_FALLBACK_MODELS = [
  DEFAULT_IMAGE_MODEL,
  'gemini-2.5-flash-image',
  'imagen-4.0-generate-001',
  'imagen-3.0-generate-002',
];

const LEGACY_IMAGE_MODEL_ALIASES: Record<string, string> = {
  'gemini-2.0-flash': DEFAULT_IMAGE_MODEL,
  'gemini-1.5-flash': DEFAULT_IMAGE_MODEL,
  'gemini-1.5-pro': DEFAULT_IMAGE_MODEL,
  'gemini-2.5-flash': 'gemini-2.5-flash-image',
  'gemini-2.0-flash-exp': DEFAULT_IMAGE_MODEL,
  'gemini-2.0-flash-preview-image-generation': DEFAULT_IMAGE_MODEL,
  'imagen-3': 'imagen-4.0-generate-001',
};

export const normalizeImageModel = (model: string | null | undefined): string => {
  const trimmed = model?.trim();
  if (!trimmed) return DEFAULT_IMAGE_MODEL;
  return LEGACY_IMAGE_MODEL_ALIASES[trimmed.toLowerCase()] ?? trimmed;
};

export const PLACEHOLDER_DOC = 'As you talk, your scribe will write your document here...';
