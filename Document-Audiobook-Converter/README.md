# Document Audiobook Converter

Document Audiobook Converter turns PDF, DOCX, and TXT files into spoken audio.
It can use the browser's built-in speech engine without a backend, or Gemini
Live for streamed natural-voice narration with look-ahead generation and a
persistent local audio cache.

## Features

- PDF, DOCX, and plain-text extraction in the browser
- Coordinate-aware PDF reading order for multi-column textbook pages
- Conservative textbook cleanup for wrapped words, spaced headings, URLs, and service metadata
- Browser speech synthesis for a zero-configuration reading mode
- Gemini Live narration through the Python WebSocket backend
- Non-replaceable verbatim narration policy with optional delivery-style presets
- Two-lane priority generation and look-ahead buffering
- Optional playback while Gemini is still generating a passage
- IndexedDB narration cache with retention controls and transcript comparison
- Live document refresh when the File System Access API is available
- Safe stop, jump, pause, and document-edit handling during asynchronous audio
- Document Picture-in-Picture controls in supported browsers
- Always-on-top playback controls through the Electron companion
- Browser-extension/Electron bridge on local port 3001

## Requirements

- Node.js 22.13 or newer (required by the locked PDF.js dependency)
- Python 3.10 or newer
- A Gemini API key for Gemini narration

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
Browser speech mode does not require a key or the Python backend.

## Quick start

From this directory:

```bash
npm install
python -m pip install -r backend/requirements.txt
```

Copy the environment template and add your key:

```powershell
Copy-Item .env.example .env.local
```

On macOS or Linux, use `cp .env.example .env.local` instead.

Start the backend in one terminal:

```bash
python backend/main.py
```

Start the web app in another:

```bash
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`, upload a document, and
press play. Select **Gemini Live API** under Voice Engine to use streamed Gemini
narration.

### Local services

| Service | Default address |
|---|---|
| React/Vite app | `http://localhost:5173` |
| Gemini WebSocket backend | `ws://127.0.0.1:9083` (loopback by default) |
| Backend status endpoint | `http://localhost:9084/status` |
| Electron control bridge | `ws://localhost:3001` |

## API-key resolution

The backend uses the first valid key it finds:

1. A key supplied by the app's Gemini settings panel and persisted in that
   browser profile's `localStorage`
2. `GEMINI_API_KEY` or `GOOGLE_API_KEY` in the process environment
3. `GEMINI_API_KEY` in the project-root `.env.local`

`.env.local`, other environment files, runtime chat history, Python bytecode,
dependencies, and build output are ignored by Git. Never commit a real key. If
a key reaches Git history, rotate it rather than merely deleting the current
file.

## Running modes

### Browser speech

Run only `npm run dev`, leave Voice Engine set to **Browser**, choose an
available voice, and play. The app does not send this text to Gemini or the
Python backend. Whether a `speechSynthesis` voice is implemented locally or by
a platform-provided remote service depends on the browser and operating system.

### Gemini Live narration

Run both the Python backend and the Vite app. The frontend queues upcoming
passages by document position; two independent Gemini lanes generate work in
parallel while maintaining strict turn ordering within each WebSocket session.
Sessions are periodically recycled to prevent long audio histories from
degrading narration quality.

Gemini's explicit turn-complete event is authoritative. A single 20-second
audio-idle watchdog recovers abandoned turns; the browser allows 60 seconds for
that watchdog plus optional fallback transcription, while the outer backend
supervisor waits 75 seconds. A failed client turn retires its untagged socket so
late output cannot be mistaken for the next passage. Byte-size shortcuts are
not used to end short or long clips.

Generated audio can be saved in IndexedDB. The Saved Audio panel controls the
storage ceiling, age limit, live-only regeneration, streaming playback, and
per-document or per-clip deletion.

The mandatory read-verbatim policy always remains active. The delivery-style
field can adjust pacing, tone, accent, and pronunciation without replacing that
policy. Built-in presets include **Strict Textbook** and **Natural Southern**.
Style and policy versions are part of each cache key, so changing delivery does
not replay audio generated under an older configuration.

### Electron companion controls

For development, start the Vite app and Electron together:

```bash
npm run electron-dev
```

The companion keeps an always-on-top transport window available even when the
reader itself is running in a regular browser tab. `Ctrl+Shift+B` toggles the
controls. Browser tabs discover the companion on local port 3001.

For a packaged build:

```bash
npm run build-electron
```

In browsers supporting Document Picture-in-Picture, detached controls use a PiP
window when Electron is unavailable. Other browsers fall back to an in-page
floating panel.

## Development checks

```bash
npm run check:size       # enforce the 450-line authored-source ceiling
npm test                 # Vitest unit and facade tests
npx tsc --noEmit         # TypeScript contracts
npm run build            # production Vite build
python -m compileall -q backend
```

The live Gemini smoke test requires a running backend and a valid key:

```bash
python backend/tests/smoke_turns.py
```

Configuration and continuation behavior can be checked without a live API:

```bash
python backend/tests/test_backend_modularization.py
python backend/tests/test_websocket_modularization.py
python backend/tests/test_completion_policy.py
python backend/tests/test_narration_policy.py
python backend/tests/test_continuation.py
```

Document fixtures can be regenerated with:

```bash
python -m pip install python-docx PyMuPDF
python backend/tests/make_fixtures.py
```

The source-size check scans authored `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`,
`.cjs`, `.py`, `.html`, and `.css` files while excluding dependencies, build
artifacts, virtual environments, coverage, and Python bytecode.

## Architecture

The public entry points remain small facades; stateful runtimes and pure helpers
live behind them.

```text
App.tsx
└─ src/components/AudiobookApp.tsx
   ├─ document session and live-file lifecycle
   ├─ src/hooks/useAudioEngine.ts
   │  └─ src/hooks/audioEngine/
   │     ├─ Gemini playback and prefetch ownership
   │     ├─ cache-backed narration requests
   │     └─ browser speech helpers
   ├─ src/hooks/useGemini.ts
   │  ├─ src/hooks/gemini/              lane scheduler and lane runtime
   │  └─ src/services/gemini/           Live protocol and PCM helpers
   ├─ src/components/audioCache/        cache controller and focused views
   ├─ src/utils/audioCache.ts           compatibility facade
   │  └─ src/utils/audioCache/          IndexedDB, identity, PCM, policy
   └─ src/integrations/electronBridge.ts

backend/main.py
└─ backend/main_server_files/
   ├─ websocket_server/                 handshake, dispatch, session runtime
   ├─ response_processing/              frame policy and response audio
   ├─ audio_processing/                 transport, buffering, transcription
   ├─ session_management/               slots, continuity, keep-alive
   ├─ api_configuration/                keys, models, Gemini configuration
   └─ status_monitoring/                 health and circuit-breaker status

electron/main.cjs
└─ electron/extension-relay.cjs         browser/extension WebSocket transport
```

The document pipeline keeps positional reading order in
`src/services/pdfTextLayout.ts` and deterministic cleanup in
`src/utils/textbookNormalization.ts`. The backend's mandatory narration rules
and delivery-style composition live in
`backend/main_server_files/api_configuration/narration_policy.py`.

Important compatibility facades include `App.tsx`, `useAudioEngine.ts`,
`useGemini.ts`, `audioCache.ts`, `response_stream_handler.py`,
`response_handler.py`, `audio_processor.py`, `gemini_session_handler.py`, and
`message_processor.py`. Existing callers can keep importing those paths.

## Document processing

Document extraction is browser-side:

- PDF: `pdfjs-dist`
- DOCX: `mammoth`
- TXT: the browser `File` API

PDF text items are grouped by their public coordinates and font metrics. The
reader detects likely gutters, reads each column top-to-bottom, keeps full-width
headings in sequence, removes repeated outer-margin headers and page numbers,
and falls back to PDF.js end-of-line order when coordinates are incomplete.

Extracted text is conservatively normalized before it is divided into passages:
soft and line-wrapped hyphenation is repaired, known letter-spaced headings are
reconstructed, and common library-service/URL boilerplate is omitted. Isolated
letters, numbers, equations, list markers, and ordinary compounds are retained.
When a watched source file changes, sentence alignment remaps the current
position and retained audio instead of restarting the document from the
beginning.

## Troubleshooting

- Check `http://localhost:9084/status` if Gemini configuration cannot connect.
- Confirm the app's WebSocket URL is `ws://localhost:9083` unless you changed the backend port.
- If Gemini is deliberately disconnected in the UI, use Reconnect before playing again.
- If detached Electron controls are unavailable, confirm the companion is running and local port 3001 is not blocked.
- Cache contents belong to the browser profile. Clearing site data also clears saved narration.

## Security and local data

- API keys must stay in environment variables, `.env.local`, or the browser-persisted settings panel. The panel stores its configuration, including the key, in that browser profile's `localStorage`.
- Cached narration is stored locally in IndexedDB.
- Runtime chat history is ignored by Git because it may contain document text.
- The narration WebSocket binds `127.0.0.1:9083` by default. Deliberate LAN access can be enabled with `python backend/main.py --host 0.0.0.0`; that mode has no built-in authentication or TLS, so use it only on a trusted network behind an appropriate firewall. Put authentication and transport security in front of it before any wider exposure.
