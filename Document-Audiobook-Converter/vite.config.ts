import path from 'path';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      define: {
        'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
        'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
      },
      // PostCSS is auto-discovered from postcss.config.js. This used to point
      // explicitly at postcss.config.cjs, a second, duplicate config - so the
      // Tailwind v4 codemod migrated postcss.config.js while the build kept
      // reading the stale v3 .cjs. The duplicate is gone; there is one config.
      server: {
        watch: {
          // The Python backend lives inside this directory and rewrites
          // chat_history.json on every turn. Vite was watching it and issuing a
          // full page reload each time, which tore down playback mid-sentence
          // during normal use. None of these files are part of the frontend
          // bundle, so nothing here should ever trigger HMR.
          ignored: ['**/backend/**', '**/dist/**', '**/__pycache__/**'],
        },
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      }
    };
});
