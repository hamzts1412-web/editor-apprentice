# Learning a stage you haven't done before

A stage is anything the editor names: a rough cut, a second cut of the client's cut, multicam switching, a video map,
chapter cards, an animated intro, captions, sound design, thumbnails, prompts for an image or video AI, b-roll research,
a color round trip, delivery. There is no fixed list. Learn each one the same way, and write what you learn into the
client's stage file so you never learn it twice.

## 1. The editor describes it
What goes in, what comes out, where it lives (which app, which track/comp/folder), how long it takes them, what "good"
looks like, what they always do and never do. Who does it now — and do they want you to do it, prepare it, or only
advise on it?

## 2. Find it in finished work
Open a finished project where this stage was done and measure it: counts, lengths, positions, tracks, sizes, fonts,
colors, timing relative to the words, sounds that go with it. Look at frames (`frames.py`). For motion work, read the
compositions (`ae_run.py`, `apps/after-effects.md`). Note what varies per project and what never changes.

## 3. Find your way in (`capabilities.md`)
How can you produce this stage's output for this editor's app? In order of preference:
1. **Files the app imports** (XML timelines, SRT, images, audio, .jsx scripts, JSON drafts) — exact and reversible.
2. **The app's own scripting** (ExtendScript in After Effects, Resolve's Python API, …) — exact, needs the app open.
3. **An MCP server** the editor agreed to install — convenient, varies in quality; check what it can really do.
4. **Computer use** (clicking the UI) — for what nothing else reaches; slow, verify after every batch.
If none fits, say so and suggest what you *can* prepare outside the app (a plan with timecodes, assets, a script the
editor runs).

## 4. Prove it small
Before promising, do the smallest real test on a copy: one clip, one title, one comp. Read it back. Only then say
"I can do it by …".

## 5. Propose, in their words
"I can help with this stage by 1, 2, 3; I can't do 4 because …; you'd still do 5." Wait for their OK and their choices
(content unit, order, style). Blanks stay blank until they answer.

## 6. Do one sample, then the rest
For anything visual or taste-heavy: one sample first (a frame, a scene, the first minute), their review, then the rest.
If the reference comes from an image AI or a mood board, take content and colors from it, but compose like a person
would (asymmetric, elements a little smaller, air around them, text on the reading side) — a 1:1 copy of a generated
frame looks generated.

## 7. Write the stage file
`client-<name>/stages/<n>-<stage>.md`: what goes in/out, the rules with reasons, the numbers (in `profile.json`), the
exact commands or app procedure, how you check it, what the editor does after you, and "Report (stop here): …".

## Common stages — what to measure and known pitfalls
Use as a checklist, not as the editor's rules.
- **Rough cut of talking-head raws**: air before the first word and after the last (frames), breaths kept or not,
  pauses kept inside speech, retakes (usually the last complete take wins; a list with repeated words is not a retake),
  self-corrections, talk to the crew, mutters, Whisper inventions on noise. An in point on the audio attack clicks — land
  it in the quiet just before. Starter: `autocut.py` + review pass over `decisions.tsv`.
- **Second cut of someone else's cut**: silences, breaths, speed-ups of static screens, re-layering. Read their sequence
  first; propose changes as a list with timecodes before touching anything.
- **Multicam**: minimum shot length, waiting for or anticipating the new speaker, what happens on overlaps and
  laughter, reaction shots, cutaways in long monologues. Starter: `multicam.py`.
- **Zoom punch-ins**: why (hide jump cuts, motion, emphasis), scale, speed, easing, drift back, gaps between zooms, any
  hard rule (e.g. no zoom straight into another). Starter: `zoom.py`.
- **Templates / titles with SFX**: what gets a template, how long it stays (fixed or as long as the talent talks about
  it), sets (B starts x s after A), the sound on its first frame, what happens on overlaps. Starter: `graphics.py`.
- **Captions**: where, characters per line, max duration, style, spelling from the spelling list. `words.py --srt`.
- **Hook / intro**: denser visuals, tighter cuts, CTA timing relative to the word, the transition into the body.
- **Video map / chapters**: the content unit (chapters? items compared?) — propose from the content, let the picture
  decide; a map is often shown whole once, then card by card before each part.
- **Animation scenes in After Effects**: identity first; concept frame (from the editor or an image AI) approved before
  building; build with `ae_run.py` + `ae/lib.jsx`; look at every scene on one contact sheet before reporting; leave
  layers clean and separate for the editor's own polish.
- **AI image/video prompts**: one fixed style block built from the identity and the editor's past work, then one prompt
  per scene with the sentence it illustrates; rejected options kept struck through.
- **B-roll / images**: who selects; real sources first; licenses noted; ask before downloading; name files in timeline
  order with their timecode.
- **Color round trip**: usually the editor's; help with LUT handling and checking the graded return lines up.
- **Sound design / mix**: often light SFX on what moves; loudness target from the editor skill; check a render.
- **Delivery and cleanup**: back up first; remove only what you added; verify the sequence after cleanup.
