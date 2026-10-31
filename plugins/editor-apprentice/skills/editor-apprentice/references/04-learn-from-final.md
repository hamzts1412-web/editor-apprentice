# Mode 4 — Learn from the editor's final

The editor always changes things after your hand-off. Measuring exactly what changed — instead of asking "what did you
change?" — is what makes the next project better.

## 1. Get both versions
- Yours: `_auto/ours.timeline.json` saved at hand-off, the backup project, the copy of motion projects you built.
- Theirs: the final project (Premiere `.prproj`; Resolve/FCP: export XML), their motion project (open in the app and
  `ae_run.py --inspect`), or only the render (`align_render.py` recovers a timeline from it).
  Search their folders first; ask only if the final isn't where it should be.

## 2. Diff and measure
```
python <scripts>/final_diff.py _auto/ours.timeline.json "<final project>" --seq "<sequence>" --words <project folder> -o _auto/final_diff.json
python <scripts>/measure.py "<final project>" --seq "<sequence>"
python <scripts>/ae_run.py --inspect --only "<your comp folder or names>"     # motion: what they changed in your comps
python <scripts>/frames.py "<render>" --every 20 --sheet-out _auto/final_sheet.png
```
Read it as an editor would:
- **Cuts**: pieces removed (with the words) and added back. Many tiny trims = your air setting is loose. A sentence said
  twice in different words = a paraphrased retake you missed. Material added back = you cut something good.
- **Layers / templates / scenes**: kept, moved, resized, removed, added. Where each of your scenes landed and how long
  it ran (scenes are usually trimmed to the passage). What they rebuilt and how (composition, sizes, effects).
- **Added by the editor**: b-roll, transitions, sounds, effects, polish — what their territory looks like, so your next
  hand-off leaves room for it.

## 3. Ask only the why
At most 3–5 changes you can't explain, each with timecode and what changed; ask the reason, with options when you can
guess them. Everything you can explain, state as a finding ("you trimmed ~3 frames of air at 49 clip starts → I'll cut
tighter"). If the editor tells you what they did and you can't read it from the files, take their word and record it.

## 4. Fold it back
- **Rule change** → client `profile.json` / stage file / editor skill, with the reason.
- **Depends on the project** → record it as an option to offer next time, not a rule.
- **One-off taste** → `notes.md` only.
- **Your bug** (tool or procedure) → fix it, re-run on this project's data to confirm.
- **This skill's own mistake** → `skill-feedback.md`.
Write a project section in `notes.md`, update the client skill (`05-build-skills.md`), and tell the editor in 5–8 lines
what will be different next time.
