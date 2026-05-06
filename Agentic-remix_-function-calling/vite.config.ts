import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { exec } from 'child_process';

/**
 * Vite plugin: Bridges the web UI to Windows display hardware.
 * - /api/brightness (GET/POST) — screen brightness via WMI
 * - /api/color-temperature (POST) — color warmth via gamma ramp
 */
function displayControlPlugin() {
  return {
    name: 'display-control-plugin',
    configureServer(server: any) {
      // --- BRIGHTNESS ---
      server.middlewares.use('/api/brightness', (req: any, res: any, next: any) => {
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

        if (req.method === 'OPTIONS') {
          res.statusCode = 204;
          return res.end();
        }

        if (req.method === 'POST') {
          let body = '';
          req.on('data', (chunk: string) => { body += chunk; });
          req.on('end', () => {
            try {
              const { brightness } = JSON.parse(body);
              const level = Math.max(0, Math.min(100, Math.round(brightness)));

              const psCommand = `powershell -NoProfile -Command "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, ${level})"`;

              exec(psCommand, (error, stdout, stderr) => {
                res.setHeader('Content-Type', 'application/json');
                if (error) {
                  console.error('[Brightness] Error:', stderr || error.message);
                  res.statusCode = 500;
                  res.end(JSON.stringify({ ok: false, error: stderr || error.message }));
                } else {
                  console.log(`[Brightness] Set to ${level}%`);
                  res.end(JSON.stringify({ ok: true, brightness: level }));
                }
              });
            } catch (e: any) {
              res.statusCode = 400;
              res.end(JSON.stringify({ ok: false, error: 'Invalid JSON body' }));
            }
          });
          return;
        }

        if (req.method === 'GET') {
          const psRead = `powershell -NoProfile -Command "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"`;
          exec(psRead, (error, stdout, stderr) => {
            res.setHeader('Content-Type', 'application/json');
            if (error) {
              res.statusCode = 500;
              res.end(JSON.stringify({ ok: false, error: stderr || error.message }));
            } else {
              const current = parseInt(stdout.trim(), 10);
              res.end(JSON.stringify({ ok: true, brightness: isNaN(current) ? -1 : current }));
            }
          });
          return;
        }

        next();
      });

      // --- COLOR TEMPERATURE (Windows Night Light via nightlight-cli) ---
      server.middlewares.use('/api/color-temperature', (req: any, res: any, next: any) => {
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

        if (req.method === 'OPTIONS') {
          res.statusCode = 204;
          return res.end();
        }

        if (req.method === 'POST') {
          let body = '';
          req.on('data', (chunk: string) => { body += chunk; });
          req.on('end', () => {
            try {
              const { temperature } = JSON.parse(body);
              const valid = ['warm', 'cool', 'daylight', 'reset'];
              if (!valid.includes(temperature)) {
                res.statusCode = 400;
                res.end(JSON.stringify({ ok: false, error: `Invalid. Use: ${valid.join(', ')}` }));
                return;
              }

              const nlBin = path.resolve(__dirname, 'node_modules/.bin/nightlight');

              // Map temperature → Night Light commands
              // Night Light only shifts warm (reduces blue). "cool" and "daylight" = off.
              const commands: string[] = [];
              if (temperature === 'warm') {
                commands.push(`"${nlBin}" on`, `"${nlBin}" strength 60`);
              } else {
                // daylight, cool, reset → turn Night Light off
                commands.push(`"${nlBin}" off`);
              }

              // Run commands sequentially
              const runNext = (i: number) => {
                if (i >= commands.length) {
                  res.setHeader('Content-Type', 'application/json');
                  console.log(`[ColorTemp] Set to ${temperature}`);
                  res.end(JSON.stringify({ ok: true, temperature }));
                  return;
                }
                exec(commands[i], (error, stdout, stderr) => {
                  if (error) {
                    console.error('[ColorTemp] Error:', stderr || error.message);
                    res.setHeader('Content-Type', 'application/json');
                    res.statusCode = 500;
                    res.end(JSON.stringify({ ok: false, error: stderr || error.message }));
                    return;
                  }
                  runNext(i + 1);
                });
              };
              runNext(0);
            } catch (e: any) {
              res.statusCode = 400;
              res.end(JSON.stringify({ ok: false, error: 'Invalid JSON body' }));
            }
          });
          return;
        }

        next();
      });
    }
  };
}

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      server: {
        port: 3000,
        host: '0.0.0.0',
      },
      plugins: [react(), tailwindcss(), displayControlPlugin()],
      define: {
        'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
        'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, './src'),
        }
      }
    };
});
