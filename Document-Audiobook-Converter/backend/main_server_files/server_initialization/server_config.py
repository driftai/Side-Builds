"""
Server configuration settings and constants.
"""

# Global cleanup interval for session cleanup task (seconds)
CLEANUP_INTERVAL_SEC = 60

# Default WebSocket server port
DEFAULT_PORT = 9083

# Default status server port (WebSocket port + 1)
STATUS_PORT = DEFAULT_PORT + 1

# Chat history file path
CHAT_HISTORY_FILE = "chat_history.json"

# Transcribe generated audio back into text with a second API call.
#
# The audiobook frontend only uses the resulting `is_transcription` message as
# an "audio finished" sentinel (see useGemini.ts) and discards the text, so
# leaving this on roughly doubles API calls per sentence and was exhausting the
# quota. The sentinel is still sent when this is off. Set True to restore
# transcription for clients that actually consume the text.
TRANSCRIBE_GENERATED_AUDIO = False 