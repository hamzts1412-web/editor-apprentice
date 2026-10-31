# Premiere Pro

## Getting your timelines in (preferred: XML, no UI automation)
- `File › Import` the `.xml` → a new sequence + its media in the open project. Or `File › Open Project` on the `.xml` →
  Premiere converts it into a new project.
- Tested on Premiere 2026: linked V1/A1 clips with in points, Scale + Position keyframes landing on the exact frames,
  static scale, a still on V2, an SFX on A3 at −20 dB, sequence markers.
- XML cannot carry .mogrt templates or adjustment layers — those are placed in the UI (below).
- **Where it saves**: a project opened from an XML is saved into Premiere's *last-used folder*, which may be another
  project's folder. Prefer `File › Import` into a project already saved where it belongs, or `Save As` with the full
  path; check the window title.
- Mixed frame rates are fine (e.g. 29.97 camera + 30 fps screen + separate mic in a 30 fps sequence): in points exact to
  < ½ frame, no drift. Sources larger than the sequence are written with a fit-to-frame Scale.

## Reading the project back (always, after UI work)
`python <scripts>/timeline.py read "<file.prproj>" --seq "<sequence>" -o _auto/now.timeline.json` (reads the last save;
works while Premiere is open). `timeline.py seqs` lists sequences. Template texts/sizes/images: `premiere_graphics.py`.
Adjustment layers read as kind `adjustment`, Essential Graphics as `graphic`, caption tracks as `C1…`.
Known gaps of the readers: clip **speed** changes and **Motion** (position/scale) keyframes are not reported yet, and
newer Essential Graphics text may not be readable — check those in the UI or extend the reader (`build-a-tool.md`).
A **hole** in the editor's timeline is usually a slot for media still to come (results, b-roll): match it to the
media folders before calling it a gap.

## MCP servers
Community servers exist (a UXP or CEP panel inside Premiere + a local server). Check the repository against the
editor's Premiere version and what it claims to support; some text properties are not reachable through UXP.

## UI automation (computer use) — what works and what bites
- Request access to "Adobe Premiere Pro <year>". Anti-cheat software can block synthetic input.
- **Jump to a timecode**: click the sequence timecode field (top-left of the timeline), type the digits without
  separators and without a leading zero (`22616` = 0:02:26:16), Enter.
- **Paste lands at the playhead.** Clips copied from another sequence keep their source tracks; plain clips follow track
  targeting — target a free track first so V1 is never overwritten. Overwrite-paste trims whatever is under it.
- Keep only the track you work on targeted; `D` selects the clip at the playhead on targeted tracks. Re-target V1 + A1
  at the end.
- Effect Controls › Graphic Parameters: a text parameter's twirl state is stored per clip; collapsed = typing goes
  nowhere. Expand it on one clip and copy *that* clip as the paste source.
- The clipboard can silently empty → paste does nothing; re-copy.
- Ctrl+K may do nothing; trim by dragging the edge onto the playhead with the timeline zoomed in.
- Project panel: a single click on a name starts rename (Escape); open a sequence with right-click › Open in Timeline.
- Templates/adjustment layers from an earlier project: `Ctrl+I` the old `.prproj` › Import Selected Sequences.
- File dialogs: clear with Ctrl+A, Delete; non-Latin paths type reliably via the clipboard.
- Batch about 5 actions per item, ~20 items per batch, screenshot at the end of each batch, verify from the saved project.

## Dynamic Link with After Effects
Comps placed in Premiere through Dynamic Link stay live: when you change a comp in AE, the Premiere sequence updates.
Never rename or delete a comp the editor already placed; build new versions next to it.
