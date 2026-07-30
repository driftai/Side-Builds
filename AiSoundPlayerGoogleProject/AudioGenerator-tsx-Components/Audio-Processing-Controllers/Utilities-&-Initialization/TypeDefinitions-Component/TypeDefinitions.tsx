/**
 * @fileoverview Shared type definitions for the AI Sound Player application
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export interface Prompt {
  readonly promptId: string;
  text: string;
  weight: number;
  cc: number;
  color: string;
}

export interface ControlChange {
  channel: number;
  cc: number;
  value: number;
}


export interface MusicConfigPreset {
  bpm: number;
  useDefaultBpm: boolean;
  density: number;
  useDefaultDensity: boolean;
  brightness: number;
  useDefaultBrightness: boolean;
  guidance: number;
  useDefaultGuidance: boolean;
  temperature: number;
  useDefaultTemperature: boolean;
  muteBass: boolean;
  muteDrums: boolean;
  onlyBassAndDrums: boolean;
  currentScale: string;
}

export type PlaybackState = 'stopped' | 'playing' | 'loading' | 'paused';
export type VisualizationMode = 'frequency' | 'waveform' | 'circle' | 'spectrogram' | 'frequency-peaks' | 'audio-track'; 