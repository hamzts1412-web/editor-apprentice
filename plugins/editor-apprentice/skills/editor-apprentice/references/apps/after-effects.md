# After Effects

## Talking to the open app (no MCP needed)
`python <scripts>/ae_run.py <scene.jsx> --lib` runs a script inside the running After Effects as one Undo step and prints
what it returns. `--inspect [--only <name part>]` summarizes the open project (comps, layers, parents, effects with
match names, text and fonts, keyframed properties) — use it to learn the editor's motion work before building anything,
and again on their final to see what they changed.
- One-time setting: Preferences › Scripting & Expressions › **Allow Scripts to Write Files and Access Network**.
- Windows runs `AfterFX.exe -r` (it uses the open instance; quoting the path can make it exit, so the tool passes a
  short path). macOS runs AppleScript `DoScriptFile`.
- If nothing comes back: a modal dialog or a render is blocking AE — ask the editor to look at the AE window.
- A binary `.aep` can't be read offline in any useful way; read it live with `--inspect`. If AE isn't available and
  the editor tells you what they did, take their word and record it.

## MCP servers (optional)
Community servers exist (a panel inside AE polls a folder for commands). They need the panel open with auto-run on, and
it must be reopened after every AE restart. Prefer `ae_run.py` unless the editor already uses one.

## Building scenes
1. Identity and the approved concept frame first (`learn-a-stage.md`). Take content and colors from the frame; compose
   like a person (asymmetric, a little smaller, air around, text on the reading side).
2. Write one `.jsx` per scene: set `EA` (folder, size, fps, font, colors, icons) from the client profile, then
   `ae_run.py --lib`. Your comps go in your own folder (`EA.folder`); `newComp` only ever replaces a comp of the same name
   inside that folder.
3. Real assets beat drawn ones: download icons (SVG, permissive license) and illustrations, or crop them from the
   approved frame — don't redraw them from shapes.
4. Look at your work: `snap(comp, [times])` saves PNGs; then `python <scripts>/frames.py --sheet <pngs…>` tiles them
   into one contact sheet. Open it, fix what's wrong, rebuild. `saveFrameToPng` finishes after the script returns — don't
   delete or rebuild that comp in the same run.
5. Leave layers clean and separate so the editor can polish (glow, scale, timing) — that part is often theirs.

## ExtendScript facts that cost time
- ES3: no `let`, arrow functions, `JSON` may be missing (use `toJSON` from lib), reserved words (`in`, `class`…) can't
  be object keys.
- `sourceRectAtTime()` from a script is stale right after you style a text layer; read the box through a scratch
  expression (`measure()` in lib).
- Right-to-left text: right/left justification often doesn't stick and the measured horizontal box is wrong — centre it
  and place it by its centre. Left-to-right words in an RTL project need direction LTR or they mirror.
- `comp.bgColor` doesn't show in Premiere or renders; add a solid.
- Grid effect (`ADBE Grid`): set Blending Mode to Normal, or the layer turns transparent.
- SVG imports as vector footage: turn on collapse transformations to keep it crisp; recolor with a Fill effect.
- Parenting to a layer that is at scale 0 at that moment throws children off: parent first, animate after.
- Track matte: `layer.setTrackMatte(matteLayer, TrackMatteType.ALPHA)`; looping footage: Time Remap + `loopOut()`.
- Never write non-Latin text files with tools that guess the encoding (e.g. Windows PowerShell `Set-Content`); write them
  as UTF-8 with the file tools. `ae_run.py` reads scene files as UTF-8.
- Expressions are a second way to animate (wiggle, loopOut, linking properties to a slider). Prefer keyframes the
  editor can grab and adjust, unless they work with expression rigs.

## Dynamic Link
Comps placed in Premiere through Dynamic Link update live. Never rename or delete a comp the editor placed; build a new
version next to it.
