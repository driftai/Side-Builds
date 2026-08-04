"""
API key management functionality.
This module handles the API key storage and retrieval.

Resolution order (first usable key wins):
  1. Key supplied by the client in its init message (per-session override)
  2. GEMINI_API_KEY / GOOGLE_API_KEY environment variable
  3. GEMINI_API_KEY in the project's .env.local

There is deliberately no key in this file. Get one from
https://aistudio.google.com/apikey and set it via the environment or .env.local
(which .gitignore already excludes). A key committed to source is public the
moment the repository is - and stays public in the history even if removed
later - so this module fails loudly instead of shipping a default.
"""

import os

# No in-source fallback. Kept as an empty constant because other modules import
# these names; get_api_key() returns "" when nothing is configured, and
# validate_api_key() then rejects it with a clear message.
FALLBACK_API_KEY = ""

# Backwards compatibility for anything still importing the old name.
DEFAULT_API_KEY = FALLBACK_API_KEY

# Values that show up as stand-ins in configs/test clients and must never be
# treated as a real key.
_PLACEHOLDERS = {
    "placeholder_api_key",
    "your_api_key_here",
    "test_key",
    "none",
    "null",
    "",
}

# Project root — backend/main_server_files/api_configuration -> up three levels.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)


def _read_env_local():
    """Read GEMINI_API_KEY out of the project's .env.local, if present."""
    path = os.path.join(_PROJECT_ROOT, ".env.local")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                    return value.strip().strip("'\"")
    except OSError:
        pass
    return None


def validate_api_key(api_key):
    """
    Validate the format of the API key.
    Returns True if the key appears usable, False otherwise.

    Google AI Studio keys start with "AIza" and are 39 characters long.
    Anything shorter, or a known placeholder, is rejected so that we fall
    through to the next source instead of failing a live session with a
    confusing generic "API error".
    """
    if not api_key or not isinstance(api_key, str):
        return False
    if api_key.strip().lower() in _PLACEHOLDERS:
        return False
    if len(api_key) < 30:
        return False
    return api_key.startswith("AIza")


def get_api_key(client_key=None):
    """
    Get the API key for Gemini services.

    Args:
        client_key: Key supplied by the connecting client, if any. Takes
            priority so the in-app Gemini settings panel actually works.
    """
    if validate_api_key(client_key):
        return client_key

    for candidate in (
        os.environ.get("GEMINI_API_KEY"),
        os.environ.get("GOOGLE_API_KEY"),
        _read_env_local(),
    ):
        if validate_api_key(candidate):
            return candidate

    return FALLBACK_API_KEY


def describe_key_source(client_key=None):
    """Human-readable note about where the active key came from (never the key)."""
    if validate_api_key(client_key):
        return "client-supplied (app settings panel)"
    if validate_api_key(os.environ.get("GEMINI_API_KEY")):
        return "GEMINI_API_KEY environment variable"
    if validate_api_key(os.environ.get("GOOGLE_API_KEY")):
        return "GOOGLE_API_KEY environment variable"
    if validate_api_key(_read_env_local()):
        return ".env.local"
    return ("no key configured - set GEMINI_API_KEY, or add it to .env.local, "
            "or paste one into the app's Gemini settings panel")
