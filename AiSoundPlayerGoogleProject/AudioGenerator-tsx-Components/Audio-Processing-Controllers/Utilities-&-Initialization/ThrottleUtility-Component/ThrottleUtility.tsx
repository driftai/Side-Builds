/**
 * @fileoverview Enhanced throttle utility function for rate limiting function calls with high-resolution timing
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Enhanced throttle that uses high-resolution timing for better audio processing
 * Also returns the result of the last "fresh" call with improved timing accuracy
 */
export function throttle<T extends (...args: Parameters<T>) => ReturnType<T>>(
  func: T,
  delay: number,
): (...args: Parameters<T>) => ReturnType<T> {
  let lastCall = -Infinity;
  let lastResult: ReturnType<T>;
  let isScheduled = false;
  
  return (...args: Parameters<T>) => {
    const now = performance.now(); // Use high-resolution timing
    const timeSinceLastCall = now - lastCall;
    
    if (timeSinceLastCall >= delay) {
      lastResult = func(...args);
      lastCall = now;
      isScheduled = false;
    } else if (!isScheduled) {
      // Schedule the next call for more responsive behavior
      isScheduled = true;
      const remainingTime = delay - timeSinceLastCall;
      setTimeout(() => {
        lastResult = func(...args);
        lastCall = performance.now();
        isScheduled = false;
      }, remainingTime);
    }
    
    return lastResult;
  };
} 