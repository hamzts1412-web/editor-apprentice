# profile.json keys

Times in seconds unless a key says frames. Missing keys fall back to defaults (scripts/common.py → DEFAULT_PROFILE).

Only the keys of stages you actually do for this client matter; leave the others out or at their defaults.
Every default is a neutral placeholder, not a recommendation — measure or ask.

| Key | Meaning | How to learn it |
|---|---|---|
| `terms` | spelling list: names, products, foreign words the talent says (map spelling → hint); feeds `transcribe.py` | ask + first transcript |
| `identity.*` | colors, fonts, reference files of the channel identity | brand book / the editor |
| `motion.*` | motion app, where its projects live, scene lengths the editor really used, what the editor adds after you | their projects + final cut |
| `language` | ISO code for transcription/normalisation (`ar`, `en`…) | ask |
| `fps`, `width`, `height` | sequence settings of the client's timelines | finished project |
| `tracks.dialog_v/a` | talking-head tracks; `tracks.zoom` = adjustment-layer track | finished project |
| `cut.lead_frames` | air before the first word when a clip starts after a silence | measure.py "air before the voice" p50; editor trims → lower |
| `cut.tail_frames` | air after the last word before a silence | measure.py "air after the last word" |
| `cut.intro_*_frames` | same, for the intro/hook (often tighter) | ask + measure the hook |
| `cut.intro_marker` | regex of the script line that ends the intro | script convention |
| `cut.breaths` | `mid_speech` (cut breaths after silences) or `all` | measure.py breaths at clip starts |
| `cut.merge_gap` | pauses up to this long between kept phrases stay natural (0 = tight cut) | measure.py pauses kept inside clips |
| `cut.retake_window` | how far ahead (s) a re-said passage is looked for | rarely changed |
| `cut.keep_last_take` | keep the last version of a passage said twice | ask (almost always yes) |
| `cut.meta_phrases` | regex pieces the talent uses when talking to the crew/editor | raws + editor |
| `cut.note_words` / `note_fill` | words meaning "pause here" and the words around them | raws + editor |
| `cut.fillers` / `keep_words` | extra filler patterns / words that are speech for this talent | editor |
| `cut.hallucinations` | Whisper inventions on noise to drop when alone | first episode review |
| `cut.quiet_db` | islands this much quieter than usual = muttering/rehearsal | rarely changed |
| `zoom.style` | `ramp`, `punch` or `none` | finished project |
| `zoom.method` | `keyframes` (in the XML) or `adjustment` (layer placed in the NLE) | editor's habit |
| `zoom.layer`, `scale_in`, `ease_in`, `pos_y` | ramp length, peak scale %, push-in time, vertical offset at peak (fraction of height, negative = up) | open one layer's keyframes |
| `zoom.gap_min/gap_max` | wide time between zooms (min is a hard rule) | measure.py gaps p10/p50 |
| `zoom.restart`, `min_len`, `obvious` | jump-score thresholds: end a zoom on a big jump / never leave an obvious jump wide | defaults, tune on review |
| `zoom.punch_scale`, `punch_threshold` | static punch-in % and the cut visibility that toggles it | finished project |
| `zoom.start_after` | seconds to skip (titles at the start) | hook length |
| `multicam.*` | see stages/multicam-podcast.md | finished episode + ask |
| `graphics.lead`, `max` | start this long before the anchor word; max length | finished project |
| `graphics.kinds.<k>.dur` | default length when no `until` is given | measure.py p50 per template |
| `…track`, `levels_used`, `own_track` | base track; tracks a set occupies; kinds that never stack (CTA) | finished project |
| `…file`, `parts[]` | template file(s); `parts` = extra pieces of a set with `offset` and `track_up` | measure.py "sets" |
| `…sfx[]` | `file`, `s0` (source in), `dur`, `offset` from the template start, `gain_db`, `track` | measure.py SFX section |
