"""
Server configuration settings and constants.
"""

# Global cleanup interval for session cleanup task (seconds)
CLEANUP_INTERVAL_SEC = 60

# Default WebSocket server port
DEFAULT_PORT = 9083

# Safe default for a desktop-local service. LAN access must be requested with
# ``python backend/main.py --host 0.0.0.0``.
DEFAULT_BIND_HOST = "127.0.0.1"

# Default status server port (WebSocket port + 1)
STATUS_PORT = DEFAULT_PORT + 1

# Chat history file path
CHAT_HISTORY_FILE = "chat_history.json"

# Send outbound API traffic over IPv4.
#
# Google API keys restricted by IP almost always list an IPv4 address, but a
# dual-stack machine prefers IPv6, so the request Google actually sees comes
# from an IPv6 address that was never allowlisted. The result is a confusing
# API_KEY_IP_ADDRESS_BLOCKED naming an address you did not add. Set this to
# False if you are on an IPv6-only network.
FORCE_IPV4 = True

# Transcribe generated audio back into text with a second API call.
#
# The audiobook frontend only uses the resulting `is_transcription` message as
# an "audio finished" sentinel (see useGemini.ts) and discards the text, so
# leaving this on roughly doubles API calls per sentence and was exhausting the
# quota. The sentinel is still sent when this is off. Set True to restore
# transcription for clients that actually consume the text.
TRANSCRIBE_GENERATED_AUDIO = False
# Fill in a transcript when the Live session did not report one itself.
#
# The session usually says what it spoke alongside the audio, at no extra cost.
# Roughly one passage in three comes back without it, and that clip's marker then
# cannot judge whether the narration matched the source - which is the whole
# point of storing the transcript. This transcribes only those passages, so the
# cost lands on the gap rather than on everything, unlike TRANSCRIBE_GENERATED_AUDIO
# above which ran on every turn and doubled the calls.
TRANSCRIBE_WHEN_SESSION_SILENT = True
