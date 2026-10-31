# What you can do inside each app, and how

Pick the most exact path the editor accepts. Files and scripting are exact and reversible; MCP servers are convenient but
uneven; computer use reaches everything but is slow and needs checking after every batch. Ask the editor once which paths
they accept and write it into the editor skill.

| App | Read their work | Put your work in | Scripting | MCP servers (community) | Computer use for |
|---|---|---|---|---|---|
| **Premiere Pro** | `.prproj` (gzip XML) → `timeline.py read`, `measure.py`, `premiere_graphics.py` — works while Premiere is open, on the last save | FCP7 XML import → new sequence (`timeline.py write`, starters) | ExtendScript/UXP only from inside a panel — no command line | several (UXP or CEP panel + local bridge) | placing .mogrt templates, adjustment layers, typing template text |
| **After Effects** | the open project through `ae_run.py` (comps, layers, effects, fonts, keyframes); `.aep` is binary — read it live | ExtendScript via `ae_run.py`: build comps, layers, keyframes, expressions; import footage/SVG | yes, from the command line into the running app | several (panel + bridge) | rarely needed |
| **DaVinci Resolve** | export FCP7 XML / FCPXML → `timeline.py`; Studio: `resolve_bridge.py export` | FCP7 XML import (use FCP7, not FCPXML, for Resolve) | Python API — **Studio only** (external scripting = Local) | several (need Studio) | free version: import/export dialogs |
| **Final Cut Pro** (macOS) | export FCPXML / `.fcpxmld` → `timeline.py` | FCPXML import (`--fcpxml`) — open the first import together and check | minimal (AppleScript) | few | titles/Motion templates |
| **CapCut** | `draft_content.json` in the drafts folder — if it parses; newer/encrypted drafts don't | write the draft JSON with the app closed, after a backup | none official | a few, edit the draft file | everything when the draft is encrypted |
| **Other** (Audition, Photoshop, Illustrator, Blender, Canva, image/video AI tools) | exported files | files they import (images, audio, scripts, prompt files) | Adobe apps: ExtendScript; Blender: Python | check what exists | the rest |

Details and tested procedures: `apps/premiere.md`, `apps/after-effects.md`, `apps/resolve.md`, `apps/fcp.md`,
`apps/capcut.md`.

## Rules for any path
- **Test small first, on a copy.** One clip, one comp, one title; read it back; then the batch.
- **Read back after every change** (rule 9): saved project → `timeline.py read`; motion → render frames with
  `frames.py` or `comp.saveFrameToPng`; never trust your own write or a screenshot alone.
- **Your work goes next to theirs**, never over it: new sequence, new comp folder, new track, a clear prefix.
- **MCP servers are third-party code.** Before suggesting one: check the repository (maintained? license? what it
  really supports for this app version?), tell the editor what it installs (a panel inside the app + a local server),
  and install only after a yes. If a file or scripting path does the job, prefer it — nothing to install.
- **Computer use** (Claude desktop app → computer use on, access granted to the app): batch a few actions, screenshot,
  verify from the saved project. Anti-cheat software can block synthetic input. Never click links in the editor's
  apps; never type passwords.
- **What no path reaches** — say so, and offer what you can prepare outside the app (a plan with timecodes, assets
  named in timeline order, a script or checklist the editor runs).
