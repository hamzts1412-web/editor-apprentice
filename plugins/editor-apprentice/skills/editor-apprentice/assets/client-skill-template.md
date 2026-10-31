---
name: client-<slug>
description: <CLIENT NAME>'s project pipeline (<channel / content type, language>) as taught by the editor <EDITOR NAME> — <the stages Claude does for this client, in the editor's words> and learning from the editor's final cut. Use it whenever the editor mentions <every spelling of the client's name and channel>, a new <client> episode/project/folder, or asks to continue or redo any stage of a <client> edit — even if they don't say "skill".
---

# <CLIENT NAME> — pipeline

Editor: <name>. Reply in <language/dialect>, short and concrete, in editing terms.
Tools: the editor-apprentice scripts folder (`<scripts>` below; resolve it from the editor-apprentice skill's base
directory). Numbers: `profile.json` next to this file. Every lesson so far, with reasons: `notes.md`.
Status: <draft after meeting the client | taught on projects 1–N>. Editor's general rules: skill `editor-<slug>`.

## Who decides
<What the editor decides (order, ranking, style, which scenes…) — Claude asks with options and leaves blanks until
answered. What Claude may decide alone (technical details inside an approved plan).>

## Stages (the editor's, for this client)
Stage by stage; stop after each with a short report and wait for OK, unless the editor says "do all and leave the
mistakes to me".

| # | Stage | File | Who |
|---|-------|------|-----|
| 0 | <setup: find the material, transcribe> | `stages/0-<name>.md` | Claude |
| 1 | <…> | `stages/1-<name>.md` | <editor / client / Claude> |
| … | … | … | … |
| — | <steps the editor keeps — prepared for, never done uninvited> | `stages/<n>-editor.md` | editor |
| L | Learn from the final | `<editor-apprentice>/references/04-learn-from-final.md` | Claude |

## Rules that cut across stages (each with its reason)
- <rule> — <why>.

## Raw material and folders
<what arrives, from whom, formats, where each project lives, naming, where the client's ready assets are>

## Identity
<colors, fonts, references (files in this skill), what the client likes/rejects> — numbers in `profile.json → identity`.

## Layout at hand-off
<tracks / comp folders / naming the editor expects; what they do afterwards that changes it>

## After the project
Save the hand-off (`_auto/ours.timeline.json`, a copy of motion projects you built); when the editor says it's done, run
the learn-from-final mode and update `profile.json`, the stage files and `notes.md`.
