# Mode 3 — A project, stage by stage, under the editor's corrections

## Before the first stage
- Read the client skill (if any) and the editor skill. Confirm with the editor which stages you do this time and where
  the project stands — they may have done some already.
- Find the material yourself (project folder, subfolders, previous projects) and list what you found and what's missing.
- Back up any project file you'll touch (`_auto/backup_<name>`).

## The loop, for every stage
1. **Do the stage** with the client's stage file (or `learn-a-stage.md` if there is none yet) and the profile.
2. **Check your own work** before reporting: read the result back (saved project, `timeline.py read`, rendered frames
   via `frames.py` tiled into one contact sheet), count things, compare against the rules. Look at the picture
   yourself; fix what you can see is wrong before the editor has to.
3. **Stop and report** (their language, about 10 lines): what you did with numbers, how to open it, what you were unsure
   of, facts that need their decision. Questions with options.
4. **Corrections arrive** — usually as timecodes in *their* timeline, or as their own edits in the app. Map timecodes to
   your data before acting. If they edited in the app, read the saved project again: their edits are the truth; never
   overwrite them with an older version of yours.
5. **Turn each correction into a rule**: fix it → write the general rule and reason → put it where it will be read next
   time (profile key, stage file, editor skill) → change the tool if the tool caused it → re-run to confirm.
6. If the editor said "do everything and leave the mistakes to me", run all stages without stopping, then hand over one
   fix list (per item: where, what, why you weren't sure).

## Examples of corrections → rules (made-up, to show the shape)
| What an editor might say | General rule to write |
|---|---|
| "You left a breath and half a wrong word at 3:06" | breaths stay only inside continuous speech; a stumble's partial word goes with it |
| "He said that line three times; keep the third" | on repeated attempts keep the last complete one |
| "The title has no sound" | a template and its SFX are one unit, placed in the same pass |
| "Two labels overlap and one got cut" | overlapping templates go one track up instead of cutting each other |
| "This scene looks generated" | take content and colors from the reference, compose like a person: asymmetric, smaller, air around |
| "Why did you stop? The images are in the folder" | look in the project folders before asking for a file |

## Keeping the editor in control
- Never delete or overwrite their media, sequences, compositions or exports; add new versions next to them.
- Name what you create so they can tell it apart (`_auto/`, a prefix, a separate bin or folder).
- Install, download, send or publish nothing without a yes.

## End of the project
Save your hand-off (`_auto/ours.timeline.json`, a copy of any motion project you built) so it can be compared with the
final. Then `04-learn-from-final.md` when they say it's done.
