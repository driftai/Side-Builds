import path from 'path';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      define: {
        'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
        'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
          '@audio-viz': path.resolve(__dirname, './AudioGenerator-tsx-Components/Audio-&-Visualization'),
          '@midi-control': path.resolve(__dirname, './AudioGenerator-tsx-Components/MIDI-&-Control'),
          '@utilities': path.resolve(__dirname, './AudioGenerator-tsx-Components/Audio-Processing-Controllers/Utilities-&-Initialization'),
        }
      },
      server: {
        port: 5173,
        strictPort: true, // This ensures it fails if port 5173 is unavailable instead of trying another port
        host: '0.0.0.0',
        fs: {
          // Allow serving files from one level up to the project root
          allow: ['..']
        }
      }
    };
});
