/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/

/**
 * Defines the structure for a theme object.
 * The `colors` array corresponds to CSS variables:
 * [bg, surface, accent, text, document-bg]
 */
export type Theme = {
  name: string;
  colors: [string, string, string, string, string];
};

/**
 * An array of available themes for the application.
 */
export const themes: Theme[] = [
  {
    name: 'Light Theme',
    colors: ['#d9d9df', '#e9e9ef', '#4285F4', '#202124', '#FFFFFF'],
  },
  {
    name: 'Dark Theme',
    colors: ['#202326', '#36393b', '#8AB4F8', '#E8EAED', '#000000'],
  },
  {
    name: 'Mint Chocolate',
    colors: ['#3d5a55', '#4f756f', '#a3d9d2', '#ffffff', '#4f756f'],
  },
  {
    name: 'Sunset',
    colors: ['#4c3a69', '#6e5d8d', '#f7b267', '#ffffff', '#6e5d8d'],
  },
  {
    name: 'Rose Gold',
    colors: ['#fdf0f0', '#ffffff', '#e6a1a1', '#5c3a3a', '#ffffff'],
  },
];
