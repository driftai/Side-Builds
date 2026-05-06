# Project Halcyon — Draft v0.3

## Overview

Halcyon is an experimental note-capture system that converts spoken
conversations into structured documents in real time. This draft
covers the original problem statement; the solution section is still
intentionally rough.

## Problem

Knowledge workers in long-form discussions (interviews, design
reviews, planning sessions) consistently lose 60–80% of usable
detail by the next morning. Existing note tools force a context
switch — you stop participating to type.

## Goals

- Zero-friction capture during the conversation itself
- Structured output you can hand to a reviewer without cleanup
- Round-trip editing: a human can correct the draft and the system
  respects those corrections

## Open Questions

1. How aggressive should the agent be about reorganizing what the
   speaker said vs. transcribing verbatim?
2. Where does the document live when the session ends?
3. What's the right primitive for "go back to an earlier draft"?

## Notes

The rest of this document is unfinished. The next section should
cover the proposed architecture, but the author hasn't written it
yet.
