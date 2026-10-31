# Building a tool that doesn't exist yet

The scripts that come with this skill cover what every editor needs. Each editor will also need something nobody wrote:
a reader for a template format, a detector for static screen recordings to speed up, a converter for their caption
style, a scene generator for their motion system. Build it — small, tested, and kept with the editor's skills.

## Before writing
- Is there a tool already? This skill's scripts (`--help`), a maintained library, an MCP server. Reuse beats rewrite.
- Prove the idea by hand on one sample first (one file, one clip, one comp).

## How to write it
- Python 3 (or ExtendScript for Adobe apps), one file, a docstring with the exact usage, plain arguments.
- Reuse `common.py` (profile loading, timecodes, audio energy, text normalisation) and the timeline format of
  `timeline.py` (read → JSON → write), so it works with every other tool.
- Read the editor's files, never modify them: write outputs to `<project>/_auto/` and new versions next to theirs.
- Print a short report in editing terms (counts, times, what to check), not logs.
- Non-Latin paths and text: read and write UTF-8 explicitly.
- Numbers that belong to a client go in their `profile.json`, not in the code.

## Test, then keep
- Run it on the real project; read the result back; compare with what the editor did by hand when possible.
- Store it where it will be found again: a tool for one client → `client-<name>/tools/`; for this editor's work in
  general → `editor-<name>/tools/`. Mention it in the stage file that uses it, with its command.
- If it is useful to every editor (no client or editor specifics in it), suggest sharing it with the skill's
  maintainers (`skill-feedback.md`) — without any client data.

## Known gaps worth building when an editor needs them
- Premiere reader: clip speed changes and Motion keyframes; newer Essential Graphics text.
- A static-screen detector (long stretches of screen recording with no change → speed-up candidates).
- Readers for other template formats (.mogrt contents, Resolve Fusion titles, CapCut text styles).
