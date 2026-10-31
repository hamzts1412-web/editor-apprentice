# Mode 5 — Write or update the editor skill and the client skills

- **Editor skill** (one per editor): kinds of work, tools, how Claude may act in their apps, pipeline order and who
  does what, collaboration style, hard rules, assets, delivery. Changes rarely.
- **Client skill** (one per client): the editor's stages for this client with their rules and numbers, identity,
  materials, and a running `notes.md` of every lesson. Changes after every project at first, then rarely.

## Where they go
User-level skills folder, so they work from any project folder: Windows `%USERPROFILE%\.claude\skills\<slug>\`,
macOS/Linux `~/.claude/skills/<slug>/`. `<slug>`: lowercase latin letters, digits, hyphens (`client-<name>`,
`editor-<name>`). For a team, offer to also put them in a shared folder or repository — one source of truth, say which.

## Client skill layout
```
client-<name>/
  SKILL.md            from assets/client-skill-template.md — who decides, stages table, cross-cutting rules
  profile.json        the numbers (assets/profile-template.json; keys in assets/profile-keys.md)
  notes.md            lesson log: every correction → rule, per project (assets/notes-template.md)
  stages/<n>-<stage>.md   one file per stage Claude does or prepares for — THEIR rules, commands, app procedure
  <assets>/           identity references, icons, example scene scripts — whatever the stages reuse
```
The stages are the editor's own for this client (from the conversation), not a fixed list. Include a file for what
the editor does after you (so you prepare for it without doing it). Each stage file ends with "Report (stop here): …".

## Writing rules (they decide whether the skill works)
- **Description** = when to trigger: every spelling of the client's name and channel the editor uses (all scripts and
  languages), and the kinds of requests ("new episode", "the intro", "the map"…). Be generous — under-triggering is the
  usual failure.
- A **why** next to every rule (one clause). A rule with its reason survives new situations; a bare MUST doesn't.
- Numbers live in `profile.json`; SKILL.md says what they mean.
- SKILL.md under ~150 lines; details in stage files read only when that stage runs.
- Refer to tools as "the editor-apprentice scripts folder" and resolve it at run time (plugin installs move).
- Reply language and tone in the first lines.
- Mark each rule confirmed (editor said so / measured twice), assumed (seen once — re-check), or per-project.
- Copy into the skill any reference files it needs (identity, icons, example scripts); never point at files that may
  move or be deleted (downloads, temp).

## Updating after a project
Append the project section to `notes.md`; change profile / stage files / SKILL.md for every rule change; bump
`version` and `updated` in `profile.json`; one line to the editor about what changed. Remove rules that turned out
wrong instead of stacking exceptions.

## Check before telling the editor it's ready
- Read the skill top to bottom as if you knew nothing about this client: could you run the next project from it alone?
- Every correction in `notes.md` is reflected somewhere (profile, stage file, or marked one-off).
- Every command runs (`--help`) and every path exists; `profile.json` parses.
- Tell the editor what the skill covers, what it doesn't yet, and how to start ("<client>, new episode: <folder>").
