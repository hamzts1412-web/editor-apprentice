# Mode 1 — Meet the editor

Goal: an **editor skill** — what is true for this editor across all their clients — so meeting a client only has to
learn what is specific to that client. One conversation, then evidence.

## 1. The machine (run, don't ask)
`python <scripts>/setup_check.py` → OS, GPU, Python packages, ffmpeg, installed editing/motion apps, Node (for MCP
servers). Report anything missing in one line each; install only after a yes (`references/setup.md`).

## 2. The conversation (short rounds, their words)
Let them describe their work before you name categories. Then fill gaps, two or three questions at a time:
- **Kinds of work** they do and for whom; languages.
- **Their pipeline, in order, as they do it today**, and who does each step — them, the client, a teammate, you. Which
  steps eat the most time? Which do they enjoy and want to keep?
- **Software per step** (cutting, motion, color, audio, captions, AI tools) and versions.
- **What they'd hand to you vs. keep.** Write the kept steps down; never take one over uninvited.
- **How to work together**: stage by stage with a stop after each (recommended), or a whole pass then a fix list
  ("finish it and leave the mistakes to me"). How they give corrections (timecodes, screenshots, voice notes).
- **Assets that travel between clients**: SFX library, LUTs, template packs, fonts, AE/motion projects, where they live.
- **Hard rules** they always apply, with the reason.
- **Delivery**: resolution, fps, codec, loudness, naming, folders.
- **How they want to control the apps through you**: is an MCP server OK, or only files and computer use? Do they want
  you to install things, or prefer to do it themselves?

## 3. Evidence
Ask for one or two finished projects from *different* clients (project file plus media still on disk). Search their
drives first if they tell you roughly where. Measure (`measure.py`, `measure_video.py`, app-specific readers). What is the
same across clients is the editor's style; what differs belongs to each client. Show 3–5 headline findings in plain
editing words and let them correct you (e.g. "you leave about one frame before the voice and every title has a whoosh
on its first frame — right?").

## 4. Write the editor skill
`05-build-skills.md`, template `assets/editor-skill-template.md`. Show them the summary in their language; confirm.

## Stop
Report what you learned (5–8 lines), what's still unknown, and the next step (meet the first client).
