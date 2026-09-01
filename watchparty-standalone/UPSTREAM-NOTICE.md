# Upstream Notice

This WatchParty base retains the room, synchronization, LAN, and remote-tunnel structure of the supplied WatchParty project.

YouTube playback in this base is intentionally limited to the official YouTube IFrame Player API flow used by the supplied UnlawfulIllustriousWebsphere YouTube player: parse a YouTube URL/video ID, create the YouTube player, and synchronize the player through WatchParty room state.

The previous WatchParty direct-media/yt-dlp/googlevideo fallback has been removed from this base. No external quality resolver or native video fallback is included.
