# Final Cut Pro (macOS)

Status: the FCPXML writer follows the FCPXML 1.9 structure and imports correctly into Resolve, but has **not been
checked inside Final Cut Pro yet**. Tell the editor on the first import, check it together, and record the result in
the editor skill (and in `skill-feedback.md` if it fails).

## Getting your timelines in
- `--fcpxml` (starters) or `timeline.py write <timeline.json> out.fcpxml`.
- `File › Import › XML…` → a new event + project. V1 (+ linked audio) is the primary storyline; other tracks become
  connected clips on lanes (V2 → lane 1, A2 → lane −1…). Zoom keyframes are `adjust-transform` scale/position.
- Titles/Motion templates are not created from XML — place them in the UI (markers mark each one).

## Reading a finished FCP edit
`File › Export XML…` → `.fcpxml` or `.fcpxmld` (both read by `timeline.py`). Compound and multicam clips read as their
container only.

## Computer use
Grant access to "Final Cut Pro". Ctrl+P = move playhead by timecode (type, Enter); Cmd+I import media.
