# editor-apprentice

**Teach Claude how you edit.** A Claude Code plugin for video editors, motion designers and montage editors.

Claude joins your workflow as an apprentice. It doesn't come with a style — it asks you how you work with each client,
splits your workflow into stages, and helps on the stages you hand over: one at a time, reporting after each, turning
every correction into a written rule. After each project it compares its work with your final cut and learns from
the difference. Everything it learns is saved as skills on your machine: one for you, one per client, so every next
project starts from what it already knows.

It works with the apps you already use — Premiere Pro, After Effects, DaVinci Resolve, Final Cut Pro, CapCut and
others — through project files (XML), the apps' own scripting, MCP servers you choose to install, or computer use. Any
language Whisper understands; Claude answers in yours.

## What it does for you
- **Listens first.** No plan before you've explained how you work. Questions come with options; anything that is your
  call (order, ranking, style) stays blank until you answer.
- **Checks before it claims.** It opens your project, listens to the audio and looks at frames before saying it can or
  can't do something.
- **Measures your finished work** — rhythm, air at cuts, template timing, SFX, zooms, scene lengths — instead of asking
  you for numbers.
- **Works stage by stage**: transcription, rough or second cut, multicam, zooms, templates with their sounds, captions,
  video maps, animation scenes in After Effects, prompts for image/video AI, b-roll research… whatever your stages are.
- **Looks at its own work** (saved project read back, rendered frames on one contact sheet) before showing you.
- **Learns from your final cut** and writes the lessons into the client's skill.

## Install
In Claude Code (desktop app or terminal):
```
/plugin marketplace add hamzts1412-web/editor-apprentice
/plugin install editor-apprentice@editor-apprentice
```
Then say, in any language: *"I'm a video editor, I want to teach you how I work."*

On first use Claude checks your machine and tells you what's missing (Python 3.10+, ffmpeg, faster-whisper, OpenCV) —
it installs only after you say yes. Optional: Node.js, if you want to use an MCP server for your editing app.

## Privacy
Everything stays on your machine: your projects, the transcripts, the skills Claude writes for you and your clients.
If the skill itself makes a mistake, Claude may log it locally in general terms (no names, no client data) and ask
whether you want to send it as a GitHub issue — only with your yes, after you've read it.

## Layout
```
plugins/editor-apprentice/skills/editor-apprentice/
  SKILL.md          the method: rules, the start-of-session gate, where to go
  references/       meet the editor · meet a client · work a project · learn a stage · learn from the final ·
                    build skills · capabilities per app · apps/* · setup · build a tool · skill feedback
  scripts/          transcribe, words, timeline (read/write NLE files), measure, measure_video, final_diff,
                    align_render, premiere_graphics, frames, ae_run, resolve_bridge, setup_check
                    + starters for common stages: autocut, multicam, zoom, graphics
  ae/lib.jsx        After Effects helpers (text, shapes, icons, keyframes, inspect, frame snapshots)
  assets/           templates for the editor skill, client skill, notes and profile.json
```

## License
MIT © Hamza Sayed
