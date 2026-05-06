/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { evaluateMathExpression } from '../../../../lib/safe-math';

// Define a default color palette for the plots if not provided.
export const DEFAULT_PLOT_COLORS = [
  '#FF0000',
  '#0000FF',
  '#00AA00',
  '#FF8C00',
  '#990099',
  '#00AAAA',
  '#FF00FF',
  '#8B4513',
];

export const evaluateFunction = (fnStr: string, x: number): number | null => {
  return evaluateMathExpression(fnStr, { x, t: x });
};

export const getNiceTicks = (min: number, max: number, count = 5) => {
  if (!isFinite(min) || !isFinite(max)) return [];
  if (min === max) return [min];
  if (min > max) [min, max] = [max, min];

  const step = (max - min) / count;
  if (step <= 0) return [min];

  const power = Math.floor(Math.log10(step));
  const magnitude = Math.pow(10, power);
  const normalizedStep = step / magnitude;

  let niceStep;
  if (normalizedStep < 1.5) niceStep = 1;
  else if (normalizedStep < 3) niceStep = 2;
  else if (normalizedStep < 7) niceStep = 5;
  else niceStep = 10;

  niceStep *= magnitude;

  let start = Math.ceil(min / niceStep) * niceStep;
  if (Math.abs(start) < 1e-10) start = 0;

  const ticks = [];
  let safety = 0;
  for (let t = start; t <= max + 1e-10; t += niceStep) {
    if (safety++ > 1000) break;
    const val = parseFloat(t.toPrecision(10));
    if (val >= min && val <= max) {
      ticks.push(val);
    }
  }

  if (min <= 0 && max >= 0 && !ticks.some(t => Math.abs(t) < 1e-10)) {
    ticks.push(0);
    ticks.sort((a, b) => a - b);
  }

  return ticks;
};
