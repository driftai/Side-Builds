/**
 * Stable application entrypoint.
 *
 * The implementation is split by responsibility under src/. Keeping this
 * facade means existing imports continue to resolve while App.tsx no longer
 * owns document parsing, runtime bridges, windows, and the complete interface.
 */
export { SUPPORTED_TYPES } from './src/services/documentText';
export { default } from './src/components/AudiobookApp';
