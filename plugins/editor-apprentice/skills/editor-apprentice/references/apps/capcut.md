# CapCut (and other apps without a public API)

CapCut has no official scripting. Its desktop projects are folders with a `draft_content.json` (plus meta files) in
the drafts folder (find it in CapCut's settings; it differs per OS and version).
- **Check first** whether the draft is readable: try to parse `draft_content.json`. Newer versions and drafts from the
  template library may be encrypted — then file editing is impossible and only computer use or exported media remain.
- **Readable drafts**: you can read tracks, segments, timings, texts, effects and measure them like any timeline. To
  write: close CapCut on that draft, back up the whole draft folder, change the JSON, reopen and check in the app. The
  format changes between versions — test one small change before a batch, and say so to the editor.
- Community MCP servers and libraries that edit drafts exist; check that they support the editor's CapCut version.
- Exports (`.mp4`, `.srt`) can always be measured with `measure_video.py` and `transcribe.py`.

## Any other app
Same order as `capabilities.md`: what files can it import and export? Does it have scripting (Adobe apps: ExtendScript;
Blender: Python)? Is there a maintained MCP server? Otherwise computer use. Prove the path with one small test, and write
what you learned into the editor skill so it isn't learned twice.
