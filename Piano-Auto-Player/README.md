# Piano Auto Player v0.6.21

> **Universal Sheet Finder, MIDI Player, and AI-Powered Polyphonic Piano Transcriber.**  
> Automatically find piano sheets across 13 sheet providers, import MIDI, or convert live YouTube/Spotify/public audio directly into timed piano performances with high-resolution timed playback.

---

## Key Features

* **Multi-Host Sheet Search:** Query 13 sheet repositories simultaneously (Virtual Piano, PlayPianoSheets, RobloxPianoSheet, VirtualPianoSheet, Game Piano Sheets, Piano Letter Notes, Online Sequencer, Music Box Maniacs, Toon Keys, Dyn Shii, etc.).
* **AI Audio-to-Piano Conversion (Auto Hi-Fi):** Dual-engine AI transcription fusing **Transkun V2** (specialized polyphonic piano neural network) with **Spotify Basic Pitch** fallback and adaptive consensus filtering.
* **Intelligent Musical Cleaning:** Automatic sustain continuity repair, fast-note onset anchoring (55 ms floor), ghost note reduction, and adaptive voice stability guards.
* **Layout Support:** Full support for standard **61-key (C2–C7)** and **88-key (A0–C8)** piano keyboard layouts with black-key Shift lead and mixed-chord spread timing.
* **Zero-Setup Internal Piano:** High-fidelity sampled Acoustic Grand Piano preview running directly in the browser via Web Audio API.
* **Robotic Playback Engine:** Precise Windows keyboard automation with Foreground and Virtual Target window routing, auto-focus countdown, and emergency killswitch (F7).
* **Persistent YouTube Session Bridge:** Local, opt-in cookie session bridge to unlock bot-challenged and account-gated YouTube media streams with locally retained authentication state.
* **Song Library Transfer:** Export and import complete song library packages (.piano-song.json or ZIP archives) to backup or sync between machines.

---

## Architecture & Isolation

Piano Auto Player uses a **modular, dependency-isolated design**:
1. **Core Web & Server (Zero Dependencies):** Standard Python library only (http.server, threading, json, ctypes). No third-party packages required to search sheets, load MIDI, or play piano.
2. **AI Transcription Engine (.youtube-piano-venv):** Isolated Python 3.10 environment containing Basic Pitch, yt-dlp nightly, and WPC token helper.
3. **Hi-Fi Neural Engine (.piano-hifi-venv):** Isolated Python environment running PyTorch with automatic NVIDIA CUDA 12.8 GPU acceleration (or CPU fallback) and Transkun V2 inference.

The local application server binds only to 127.0.0.1 (localhost). Outbound network requests occur only for features that access external sheet/media providers, model/setup dependencies, and sampled assets.

---

## Installation & Setup

### Prerequisites
* Windows 10 or 11 (64-bit).
* [Python 3.10+](https://www.python.org/downloads/) installed and added to PATH.

---

### Quick Start (Core Player)

1. Clone or download this repository:
   `cmd
   git clone https://github.com/driftai/Side-Builds.git
   cd Side-Builds/Piano-Auto-Player
   `

2. Launch the local player:
   `cmd
   start.bat
   `
   *The web interface will open at http://127.0.0.1:8765.*

---

### Enabling AI Audio Conversion (Optional)

To enable converting YouTube, Spotify metadata, or audio files into timed piano:

1. Run the YouTube/Basic Pitch setup script:
   `cmd
   setup-youtube-piano.bat
   `
   *(This automatically installs Deno, FFmpeg, and the isolated .youtube-piano-venv)*.

2. **(Optional) Enable Auto Hi-Fi Engine (Transkun V2):**
   `cmd
   setup-hifi-piano.bat
   `
   *(Automatically detects NVIDIA GPUs, configures PyTorch CUDA 12.8, and sets up Transkun in .piano-hifi-venv)*.

3. Restart start.bat. In the web UI under **Media / Spotify -> Piano**, select **Auto Hi-Fi** or **Rhythm clean**.

---

## YouTube Session Bridge & Privacy

When YouTube requests bot verification (Sign in to confirm you\'re not a bot), Piano Auto Player provides a **Local Live Session Bridge**:

1. Open DevTools (F12) on YouTube while signed in -> **Application** -> **Storage** -> **Cookies** -> https://www.youtube.com.
2. Select all (Ctrl + A) -> Copy (Ctrl + C).
3. In Piano Auto Player, click **YouTube diagnostics & session bridge** -> **Import YouTube session** -> Paste -> **OK**.

### Security & Privacy Design
* **Local State Isolation:** On Windows, retained YouTube sessions live outside the project tree under the user\'s Local AppData PianoAutoPlayer state directory (%LOCALAPPDATA%\PianoAutoPlayer\youtube_session.txt, or $XDG_STATE_HOME/PianoAutoPlayer/youtube_session.txt on Linux). The legacy data/youtube_session.txt location is migrated and removed.
* **Credentials Stay Local:** Stored cookies are strictly persistent local credentials, are excluded from Git/source/library exports, and are supplied to yt-dlp only when authenticated YouTube requests require them.
* **1-Click Deletion:** You can clear stored credentials anytime via the **Clear saved session** button in the diagnostics panel.

---

## Keyboard Controls & Safety

* **F7**: Global Emergency Stop (immediately halts all automated keystroke playback).
* **Space**: Pause / Resume playback in web player.
* **Ctrl + S**: Save current sheet/performance to local library.

---

## License & Attribution

* Piano Auto Player source code is licensed under the [MIT License](../../LICENSE).
* See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for open-source licenses of optional inference engines (Basic Pitch, Transkun, yt-dlp, FFmpeg, Deno).
