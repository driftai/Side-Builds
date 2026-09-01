# YouTube integration base — 1.0.0

This build starts from the supplied WatchParty-Standalone Point base and replaces its accumulated direct-media playback path with the YouTube-player approach from the supplied UnlawfulIllustriousWebsphere project.

## Included

- YouTube URL / video-ID parsing for watch, youtu.be, Shorts, live, embed, and /v/ URLs.
- Official YouTube IFrame Player API loading.
- YouTube player creation and video switching.
- WatchParty synchronized play, pause, seek, and playback-rate state.
- Existing WatchParty rooms, chat, host handoff, LAN mode, and Cloudflare remote launcher.

## Deliberately excluded

- yt-dlp
- direct `googlevideo.com` playback
- native `<video>` playback fallback
- custom HLS / M3U8 pipeline
- external quality dropdown / quality ladder UI
- external YouTube format extraction / resolver endpoints

Quality and playback controls belong to the embedded YouTube player in this base.
