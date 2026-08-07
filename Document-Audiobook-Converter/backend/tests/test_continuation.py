#!/usr/bin/env python3
"""Check how a recycled session is told what it is carrying on from.

No API key or server needed - this only exercises the config the server builds.

    python tests/test_continuation.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from main_server_files.api_configuration.gemini_config import (  # noqa: E402
    create_gemini_config,
    DEFAULT_NARRATION_INSTRUCTION,
    CONTINUATION_MAX_CHARS,
)

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}{' -> ' + detail if detail else ''}")


def instruction_of(config):
    return config["system_instruction"]["parts"][0]["text"]


PREVIOUS = "The lighthouse blinked twice across the bay tonight."

print("\n== without a hint, nothing changes ==")
plain = instruction_of(create_gemini_config())
check("a session with no hint gets the narration default", plain == DEFAULT_NARRATION_INSTRUCTION)
check("an empty hint is ignored",
      instruction_of(create_gemini_config(continuation_hint="")) == DEFAULT_NARRATION_INSTRUCTION)
check("whitespace is not a hint",
      instruction_of(create_gemini_config(continuation_hint="   \n ")) == DEFAULT_NARRATION_INSTRUCTION)

print("\n== with a hint ==")
carried = instruction_of(create_gemini_config(continuation_hint=PREVIOUS))
check("the narration default is still underneath it", carried.startswith(DEFAULT_NARRATION_INSTRUCTION),
      carried[:60])
check("the previous passage is quoted", PREVIOUS in carried)
check("it is told not to read it aloud", "do not read it aloud" in carried.lower())
check("it is told to match the delivery",
      "voice" in carried.lower() and "pace" in carried.lower())

print("\n== a reader's own instructions are style-only ==")
own = "Read in a slow, low voice."
mixed = instruction_of(create_gemini_config(instructions=own, continuation_hint=PREVIOUS))
check("the mandatory narration policy stays first",
      mixed.startswith(DEFAULT_NARRATION_INSTRUCTION), mixed[:50])
check("the reader's delivery style is kept", own in mixed)
check("style is explicitly unable to override verbatim narration",
      "cannot override the verbatim-narration policy" in mixed)
check("the hint is still appended", PREVIOUS in mixed)

print("\n== a long previous passage is trimmed ==")
long_previous = "word " * 400
trimmed = instruction_of(create_gemini_config(continuation_hint=long_previous))
quoted = trimmed[trimmed.index('read:\n"') + 7:]
quoted = quoted[:quoted.index('"')]
check(f"quoted passage capped at {CONTINUATION_MAX_CHARS} chars",
      len(quoted) <= CONTINUATION_MAX_CHARS, f"{len(quoted)} chars")
check("line breaks in the passage are flattened",
      "\n" not in quoted)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
