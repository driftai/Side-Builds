/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { evaluateMathExpression } from '../../../../lib/safe-math';

/**
 * Parses a string representation of an array (e.g., "['sin(x)', 'cos(x)']").
 */
export const parseArrayString = (str: string): string[] => {
  if (!str) return [];
  try {
    const trimmed = str.trim();
    if (!trimmed.startsWith('[') || !trimmed.endsWith(']')) return [];

    const inner = trimmed.substring(1, trimmed.length - 1);
    if (!inner.trim()) return [];

    return inner.split(/,(?=\s*')/).map(p => {
      const item = p.trim();
      return item.replace(/^'|'$/g, '');
    });
  } catch (e) {
    console.error('Error parsing array string:', str, e);
    return [];
  }
};

export const splitTopLevelComma = (str: string): string[] => {
  const parts: string[] = [];
  let depth = 0;
  let start = 0;

  for (let i = 0; i < str.length; i++) {
    const char = str[i];

    if (char === '(' || char === '[') {
      depth += 1;
    } else if (char === ')' || char === ']') {
      depth = Math.max(0, depth - 1);
    } else if (char === ',' && depth === 0) {
      parts.push(str.slice(start, i).trim());
      start = i + 1;
    }
  }

  parts.push(str.slice(start).trim());
  return parts;
};

/**
 * Evaluates a domain string (e.g., "[-2*pi, 2*pi]") into a numeric array.
 */
export const evaluateDomain = (str: string): [number, number] => {
  if (!str) return [-10, 10];
  try {
    const trimmed = str.trim();
    if (!trimmed.startsWith('[') || !trimmed.endsWith(']')) return [-10, 10];

    const inner = trimmed.substring(1, trimmed.length - 1);
    const parts = splitTopLevelComma(inner);
    if (parts.length !== 2) return [-10, 10];

    const evaluated = parts.map(p => {
      return evaluateMathExpression(p) ?? parseFloat(p);
    });

    if (!evaluated.every(Number.isFinite)) return [-10, 10];

    return [evaluated[0], evaluated[1]] as [number, number];
  } catch (e) {
    console.error('Error evaluating domain:', str, e);
    return [-10, 10];
  }
};
