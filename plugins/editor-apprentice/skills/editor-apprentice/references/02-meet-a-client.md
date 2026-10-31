# Mode 2 — Meet a client

Goal: a first draft of the client skill (stage list, `profile.json`, `notes.md`) good enough to run the first project
stage by stage. The editor tells the workflow; evidence fills the numbers.

## 1. Let the editor tell it
Open with: *how do you work with this client — content type, how the raw material arrives?* · *which stages, in order,
and who does each (the client, you, me)?* · *where does the current project stand?* Then, as relevant:
- **Raw material**: cameras, mics, screen recordings, AI-generated clips, stock; one file or many; a script or not.
  Does the client do part of the edit themselves (their own rough cut, their own selects)?
- **Deliverables**: long video, shorts, thumbnails, captions, versions per platform.
- **Channel identity** — as soon as graphics, animation or motion appear: brand book, colors, fonts, logo, motion style,
  existing templates and projects, what the client likes and rejects. Never invent a style.
- **Recurring terms**: names, products, jargon, words in another language inside the speech. Transcription drops or
  misspells them; keep a spelling list (it also feeds `transcribe.py --terms`).
- **Ready-made pieces** the editor reuses (templates, lower thirds, CTA, transitions with their sounds) and where they are.
- What the editor already knows the client likes or rejects.

## 2. Evidence (search first, then measure)
- Finished projects of this client → measure them (`measure.py`, `premiere_graphics.py`, `apps/<app>.md` for readers).
  If the raws of a finished project are still on disk, transcribe and compare raw vs final: what kind of material was
  removed is the strongest evidence for cut rules.
- Motion/AE projects → read their compositions (names, lengths, layers, effects, fonts) through `ae_run.py`.
- No projects? Published videos: watch parts in the browser; for numbers, `measure_video.py` needs a local file — ask for
  a render, or ask before downloading.
- Template files: list them and their fields (text, image, caption) and default lengths.

## 3. Turn evidence into the draft
- The client skill's **stages are the editor's stages for this client**, not a fixed list: a client who cuts their own
  raw and wants animation needs different stages from one who sends hours of takes.
- `profile.json` from `assets/profile-template.json`: fill only what you measured or were told; mark everything else
  "not yet confirmed" in `notes.md`.
- For each stage you'll do, run `learn-a-stage.md` until you can say how you'll do it.

## 4. Confirm in plain words
Read back the 5–8 rules that matter most as editing sentences, with their numbers; let the editor correct them. Write
the client skill draft (`05-build-skills.md`), marked draft until the first project is done.

## Stop
Report what you know, what is still a guess, and what you need for the first project.
