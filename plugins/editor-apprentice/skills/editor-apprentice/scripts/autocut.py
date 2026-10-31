"""Rough cut of talking-head raw footage: drop retakes, stumbles, muttering, crew talk and silences; keep the last good take.

Input : <project>/*.islands.json (transcribe.py), optional script (.docx/.txt) in the project, the client's profile.json
Output: <project>/_auto/roughcut.timeline.json, roughcut.xml (FCP7 XML: Premiere / Resolve) [, roughcut.fcpxml],
        decisions.tsv (every island KEEP/DROP/PART + why — what the editor reviews), cut_words.json (words in timeline time)

  python autocut.py <project> --profile <client>/profile.json [--script file] [--overrides file] [--fcpxml] [--files 1.mp4 2.mp4]

Overrides (editor corrections that must survive a re-run) — JSON keyed "<file#>@<sec in that file>":
  "keep" | "drop" | "note" (a spoken direction = pause marker) | "-lastN" (trim N cut-off words) | "keep-lastN"
"""
import argparse, difflib, glob, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import timeline as T


def wsim(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0.0


def char_sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


class Cutter:
    def __init__(self, prof):
        self.p = prof
        c = prof['cut']
        self.c = c
        self.fps = prof['fps']
        self.lang = prof.get('language')
        self.STOP = C.stopwords(self.lang)
        fill = C.FILLERS.get(self.lang or '', []) + list(c.get('fillers') or [])
        self.FILLER = re.compile('^(?:' + '|'.join(fill) + ')$') if fill else None
        self.KEEP = {C.tok(w, self.lang) for w in c.get('keep_words') or []}
        self.META = re.compile('|'.join(c['meta_phrases'])) if c.get('meta_phrases') else None
        self.NOTE_HEAD = {C.tok(w, self.lang) for w in c.get('note_words') or []}
        self.NOTE_FILL = set(C.norm(' '.join(c.get('note_fill') or []), self.lang))
        self.LONE = {C.tok(w, self.lang) for w in C.LONE_HALLUCINATIONS.get(self.lang or '', []) + list(c.get('hallucinations') or [])}
        self.GLUED = {C.tok(w, self.lang) for w in C.LONE_HALLUCINATIONS.get(self.lang or '', [])}

    # ------------------------------------------------------------ load
    def load(self, files):
        units, sources, energy = [], [], []
        for fi, p in enumerate(files):
            d = C.jload(p)
            if not self.lang and d.get('language'):
                self.__init__(C.deep_merge(self.p, {'language': d['language']}))
            sources.append((d['source'], d['duration']))
            db = C.energy_db(d['source'])
            energy.append((db, d['speech_level']))
            peaks = [r['peak'] for r in d['islands'] if r['text']]
            med = float(np.median(peaks)) if peaks else -20
            for k, r in enumerate(d['islands']):
                words = [dict(w, t=C.tok(w['w'], self.lang)) for w in r['words']]
                words = [w for w in words if w['t']]
                units.append({'id': f'{fi + 1}:{k}', 'f': fi, 's': r['s'], 'e': r['e'], 'peak': r['peak'], 'med_peak': med,
                              'text': r['text'], 'words': words, 'why': ''})
        return units, sources, energy

    # ------------------------------------------------------------ word-level helpers
    def note_words(self, words):
        """spoken directions to the editor ('leave a pause here') -> drop the words, keep a marker"""
        if not self.NOTE_HEAD:
            return
        tok = [w['t'] for w in words]
        for j, t in enumerate(tok):
            if t not in self.NOTE_HEAD:
                continue
            a = j
            while a > 0 and tok[a - 1] in self.NOTE_FILL and j - a < 4:
                a -= 1
            b = j
            while b + 1 < len(tok) and tok[b + 1] in self.NOTE_FILL | self.NOTE_HEAD and b - j < 6:
                b += 1
            for k in range(a, b + 1):
                words[k]['drop'] = 'NOTE pause'

    def retake_words(self, words):
        """the talent restarts a sentence from its beginning, often with no pause — the span between the two
        openings is a failed attempt; the last attempt wins."""
        STOP = self.STOP
        tok = [w['t'] for w in words]
        n = len(words)
        for j in range(1, n):
            if not tok[j]:
                continue
            b5 = tok[j:j + 5]
            best = None
            for i in range(j - 1, max(-1, j - 70), -1):
                if words[j]['s'] - words[i]['s'] > 40:
                    break
                if tok[i] != tok[j] or j - i < 2 or words[i].get('drop'):
                    continue
                if i > 0 and tok[i - 1] == tok[j - 1]:
                    continue
                a5 = tok[i:i + 5]
                two = len(a5) > 1 and len(b5) > 1 and a5[1] == b5[1]
                content = not (tok[i] in STOP and (len(b5) < 2 or b5[1] in STOP))
                s = wsim(a5, b5)
                span = j - i
                if span <= 12:
                    hit = (two and content and s >= 0.5) or (s >= 0.7 and len(set(a5) - STOP) >= 2) or s >= 0.55
                elif span <= 30:
                    hit = (two and content and s >= 0.6) or (s >= 0.75 and len(set(a5) - STOP) >= 2)
                else:
                    hit = tok[i:i + 3] == tok[j:j + 3] and s >= 0.7 and len(set(a5[:3]) - STOP) >= 2
                if hit:
                    best = i
                    break
            if best is not None:
                for k in range(best, j):
                    if not words[k].get('drop'):
                        words[k]['drop'] = f'restart ({words[best]["w"]}…)'

    # ------------------------------------------------------------ decisions
    def decide(self, units):
        c, STOP, L = self.c, self.STOP, self.lang

        def drop_unit(u, why):
            for w in u['words']:
                if not w.get('drop'):
                    w['drop'] = why
            if not u['why']:
                u['why'] = why

        kept = self.kept
        for u in units:
            t = ' '.join(C.norm(u['text'], L))
            if not u['words']:
                u['why'] = 'no speech'
                continue
            if u['peak'] < u['med_peak'] - c['quiet_db']:
                drop_unit(u, 'mutter (quiet rehearsal)')
                continue
            for k, w in enumerate(u['words']):
                if self.FILLER and self.FILLER.match(w['t']) and w['t'] not in self.KEEP:
                    w['drop'] = 'filler'
                run = [x['t'] for x in u['words'][max(0, k - 3):k + 4]]
                if (k > 0 and u['words'][k - 1]['t'] == w['t']
                        and any(run[i:i + 4] == [w['t']] * 4 for i in range(len(run) - 3))):
                    w['drop'] = 'whisper loop'   # keep the first one: it was said, Whisper only looped on it
            if u['words'] and u['words'][0]['t'] in self.GLUED and len(u['words']) > 1:
                u['words'][0]['drop'] = 'whisper hallucination'
            kw = kept(u)
            if not kw:
                u['why'] = 'filler'
                continue
            if len(kw) <= 2 and sum(w['p'] for w in kw) / len(kw) < 0.6:
                drop_unit(u, 'unclear fragment')
                continue
            if all(w['t'] in STOP for w in kw) and not any(w['t'] in self.KEEP for w in kw):
                drop_unit(u, 'dangling function word')
                continue
            if all(w['t'] in self.LONE for w in kw):          # 'شكرا' / 'شكرا شكرا' on keyboard noise
                drop_unit(u, 'whisper hallucination')
                continue
            if self.META and self.META.search(t):
                drop_unit(u, 'meta talk')
                continue
            self.note_words(u['words'])
            if any(w.get('drop') == 'NOTE pause' for w in u['words']):
                u['note'] = True
            if re.search(r'(\.\.|…|\w-)\s*$', u['text']):      # Whisper marks a cut-off word with '..' / 'wor-'
                kw = kept(u)
                if len(kw) <= 2:
                    drop_unit(u, 'cut-off fragment')
                elif kw:
                    kw[-1]['drop'] = 'cut-off word'

        alive = [u for u in units if kept(u)]
        # island restarts: the next island re-opens with the same words
        for a, b in zip(alive, alive[1:]):
            if a['f'] != b['f'] or b['s'] - a['e'] > 15:
                continue
            ta, tb = [w['t'] for w in kept(a)], [w['t'] for w in kept(b)]
            if not ta or not tb:
                continue
            same_open = ta[0] == tb[0] or (len(ta[0]) >= 4 and char_sim(ta[0], tb[0]) >= 0.6)
            if same_open and (len(ta) <= 3 or wsim(ta, tb[:len(ta) + 1]) >= 0.5):
                drop_unit(a, f'restart -> {b["id"]}')
            elif len(ta) <= 3 and b['s'] - a['e'] < 4 and {C.stem(x) for x in ta} <= {C.stem(x) for x in tb}:
                drop_unit(a, f'piece of next -> {b["id"]}')

        # word-level restarts inside / across islands
        for fi in sorted({u['f'] for u in units}):
            self.retake_words([w for u in units if u['f'] == fi for w in kept(u)])

        # the same passage said again later (paraphrased re-take) -> keep the later one
        if c.get('keep_last_take', True):
            alive = [u for u in units if kept(u)]
            for i, u in enumerate(alive):
                if not kept(u):
                    continue
                group, a = [], []
                for g in alive[i:i + 6]:
                    if g['f'] != u['f'] or (group and g['s'] - group[-1]['e'] > 3):
                        break
                    group.append(g)
                    a += [C.stem(w['t']) for w in kept(g) if w['t'] not in STOP]
                    if len(a) >= 5:
                        break
                if len(a) < 3:
                    continue
                later = []
                for v in alive[i + len(group):]:
                    if v['f'] != u['f'] or v['s'] - u['e'] > c['retake_window']:
                        break
                    later += [C.stem(w['t']) for w in v['words'] if w['t'] not in STOP
                              and w.get('drop') not in ('mutter (quiet rehearsal)', 'meta talk')]
                best, heads = 0, set(a[:3])
                for k, t in enumerate(later):
                    if t in heads:
                        best = max(best, difflib.SequenceMatcher(None, a, later[k:k + int(len(a) * 1.5) + 2], autojunk=False).ratio())
                if best >= (0.6 if len(group) == 1 else 0.55):
                    for g in group:
                        drop_unit(g, f'said again later ({best:.2f})')

        for u in units:
            if u['words'] and not kept(u) and not u['why']:
                u['why'] = u['words'][0].get('drop', '')
        return units

    @staticmethod
    def kept(u):
        return [w for w in u['words'] if not w.get('drop')]

    # ------------------------------------------------------------ overrides
    def apply_overrides(self, units, ov):
        kept = self.kept
        missed = 0
        for key, v in ov.items():
            act = v['act'] if isinstance(v, dict) else v
            f, t = key.split('@')
            f, t = int(f) - 1, float(t)
            hit = [u for u in units if u['f'] == f and u['s'] - 0.2 <= t <= u['e'] + 0.2]
            hit.sort(key=lambda u: not (u['s'] <= t <= u['e']))
            if not hit:
                missed += 1
            for u in hit[:1]:
                if act == 'note':
                    for w in u['words']:
                        w['drop'] = 'NOTE pause'
                    u['note'] = True
                    u['why'] = 'override: note'
                    continue
                if act.startswith('keep-last'):
                    for w in u['words']:
                        if w.get('drop') not in ('NOTE pause', 'whisper loop', 'whisper hallucination'):
                            w.pop('drop', None)
                    act = act[4:]
                if act.startswith('-last'):
                    for w in kept(u)[-int(act[5:]):]:
                        w['drop'] = 'override'
                    u['why'] = 'override: ' + act
                    continue
                for w in u['words']:
                    if act == 'keep' and w.get('drop') not in ('NOTE pause', 'whisper loop', 'whisper hallucination'):
                        w.pop('drop', None)
                    elif act == 'drop':
                        w['drop'] = 'override'
                u['why'] = 'override: ' + act
        return missed

    # ------------------------------------------------------------ intro
    def intro_end(self, units, script_text):
        """id of the first island after the intro: the intro ends on the island that says the script's last intro line"""
        mk = self.c.get('intro_marker')
        if not mk or not script_text:
            return None
        parts = re.split(mk, script_text, maxsplit=1)
        if len(parts) < 2:
            return None
        tail = {C.stem(t) for t in C.norm(parts[0], self.lang)[-6:] if t not in self.STOP}
        kept = [u for u in units if self.kept(u) and u['f'] == 0 and u['s'] < 600]
        end = None
        for u, nxt in zip(kept, kept[1:]):
            ts = {C.stem(w['t']) for w in self.kept(u)}
            if tail and len(ts & tail) / len(tail) >= 0.3:
                end = nxt['id']
        return end

    # ------------------------------------------------------------ cut points
    def build_cuts(self, units, energy, intro_until):
        c, F = self.c, self.fps
        cuts, intro = [], intro_until is not None
        for u in units:
            if u['id'] == intro_until:
                intro = False
            kw = self.kept(u)
            if not kw:
                continue
            db, lvl = energy[u['f']]
            lead = (c['intro_lead_frames'] if intro else c['lead_frames']) / F
            tail = (c['intro_tail_frames'] if intro else c['tail_frames']) / F
            onset_thr, decay_thr = lvl - 12, lvl - 16
            skip_breath = c.get('breaths', 'mid_speech') != 'all'

            def quietest(t):
                k = int(t * 100)
                lo, hi = max(0, k - 8), min(len(db), k + 9)
                return (lo + int(np.argmin(db[lo:hi]))) / 100

            runs, cur = [], []
            for w in u['words']:
                if w.get('drop'):
                    if cur:
                        runs.append(cur)
                        cur = []
                else:
                    cur.append(w)
            if cur:
                runs.append(cur)
            for run in runs:
                if run[0] is u['words'][0]:
                    k = int(u['s'] * 100)                  # after a silence: skip the breath, find the voice
                    if skip_breath:
                        while k < int(u['e'] * 100) and db[k] < onset_thr:
                            k += 1
                        k0 = k
                        while k > 0 and k0 - k < 15 and db[k - 1] > lvl - 26:
                            k -= 1                         # back to where the word starts rising
                    s = max(0, k / 100 - lead)
                else:
                    s = quietest(run[0]['s'])
                if run[-1] is u['words'][-1]:
                    k = int(u['e'] * 100) - 1
                    if skip_breath:
                        while k > int(s * 100) and db[k] < decay_thr:
                            k -= 1                         # drop the trailing breath
                    e = min(u['e'] + (0 if skip_breath else tail), (k + 1) / 100 + tail)
                else:
                    e = quietest(run[-1]['e'])
                s = int(s * F) / F                         # in point snaps DOWN to a frame (round() can land on the attack)
                if e - s > 0.08:
                    cuts.append([u['f'], s, e, u])
        mg = c.get('merge_gap') or 0
        if mg > 0:   # natural pauses: neighbouring kept islands close in the source play as one clip
            merged = []
            for x in cuts:
                if merged and merged[-1][0] == x[0] and 0 <= x[1] - merged[-1][2] <= mg:
                    merged[-1][2] = x[2]
                else:
                    merged.append(x)
            cuts = merged
        return cuts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--profile')
    ap.add_argument('--script')
    ap.add_argument('--overrides')
    ap.add_argument('--files', nargs='*', help='islands.json files in order (default: all in the project, sorted by number)')
    ap.add_argument('--intro-until', help='"<file#>@<sec>": first island after the intro (instead of the script marker)')
    ap.add_argument('--fcpxml', action='store_true', help='also write roughcut.fcpxml (Final Cut Pro)')
    ap.add_argument('--name')
    ap.add_argument('--range', help='only cut this part of the (first) raw file: "start-end" in seconds, e.g. 0-720')
    ap.add_argument('--video', action='append', default=[],
                    help='separately recorded picture synced to the transcribed audio by sound: label=file '
                         '(repeat; first = V1, e.g. --video screen=rec.mov --video cam=dji.mp4). The audio stays the mic on A1.')
    a = ap.parse_args()
    prof = C.load_profile(a.profile)
    proj = os.path.abspath(a.project)
    out = C.out_dir(proj)
    files = a.files or sorted(glob.glob(os.path.join(proj, '*.islands.json')),
                              key=lambda p: (int(re.sub(r'\D', '', os.path.basename(p)) or 0), p))
    if not files:
        raise SystemExit('no *.islands.json — run transcribe.py on the raw files first')
    cut = Cutter(prof)
    units, sources, energy = cut.load(files)
    if a.range:
        r0, r1 = (float(x) for x in a.range.split('-'))
        units = [u for u in units if u['f'] > 0 or (u['s'] >= r0 and u['e'] <= r1)]
    cut.decide(units)
    ov_path = a.overrides or os.path.join(out, 'overrides.json')
    if os.path.exists(ov_path):
        missed = cut.apply_overrides(units, C.jload(ov_path))
        if missed:
            print(f'warning: {missed} overrides matched no island')
    script_path = a.script or next(iter(sorted(glob.glob(os.path.join(proj, '*.docx')) + glob.glob(os.path.join(proj, 'script*.txt')))), None)
    if a.intro_until:
        f, t = a.intro_until.split('@')
        intro_until = next((u['id'] for u in units if u['f'] == int(f) - 1 and u['s'] >= float(t) - 0.2), None)
    else:
        intro_until = cut.intro_end(units, C.read_script(script_path)) if script_path else None
    cuts = cut.build_cuts(units, energy, intro_until)

    F = prof['fps']

    def fr(t):
        return int(round(t * F))

    videos = []   # (track, label, file, offset): time_in_video = time_in_audio - offset
    if a.video:
        from multicam import find_offset
        ref_db = energy[0][0]
        for k, spec in enumerate(a.video):
            lab, path = spec.split('=', 1)
            off, conf = find_offset(ref_db, C.energy_db(path))
            videos.append((f'V{k + 1}', lab, path, off))
            C.uprint(f'sync {lab}: video starts {-off:+.2f}s relative to the audio (confidence {conf:.2f})'
                     + ('  <-- LOW: check by eye/ear' if conf < 0.3 else ''))
        C.jdump([{'track': t, 'label': l, 'file': p, 'offset': o} for t, l, p, o in videos], os.path.join(out, 'sync.json'), indent=1)

    items, markers, words_tl = [], [], []
    tf, prev = 0, None
    for n, (fi, s, e, u) in enumerate(cuts):
        if prev is not None:
            between = units[units.index(prev) + 1: units.index(u) + 1]
            if any(x.get('note') for x in between):
                markers.append({'t': tf / F, 'name': '⏸ pause', 'comment': 'the talent asked for a pause here'})
        prev = u
        d = fr(e) - fr(s)
        src = sources[fi][0]
        if videos:
            items.append({'trk': 'A1', 'kind': 'audio', 't0': tf / F, 't1': (tf + d) / F, 's0': fr(s) / F, 'file': src,
                          'name': os.path.basename(src), 'link': f'L{n + 1}'})
            for trk, lab, path, off in videos:
                items.append({'trk': trk, 'kind': 'clip', 't0': tf / F, 't1': (tf + d) / F, 's0': max(0.0, fr(s) / F - off),
                              'file': path, 'name': lab, 'link': f'L{n + 1}'})
        else:
            for trk, kind in (('V1', 'clip'), ('A1', 'audio')):
                items.append({'trk': trk, 'kind': kind, 't0': tf / F, 't1': (tf + d) / F, 's0': fr(s) / F, 'file': src,
                              'name': os.path.basename(src), 'link': f'L{n + 1}'})
        for w in cut.kept(u):
            if s - 0.05 <= w['s'] < e:
                words_tl.append({'w': w['w'], 's': round(tf / F + max(0, w['s'] - s), 3), 'e': round(tf / F + min(w['e'], e) - s, 3),
                                 'src': f'{fi + 1}@{w["s"]:.2f}'})
        tf += d
    name = a.name or os.path.basename(proj) + ' - roughcut'
    tl = {'name': name, 'fps': F, 'width': prof['width'], 'height': prof['height'], 'items': items, 'markers': markers}
    C.jdump(tl, os.path.join(out, 'roughcut.timeline.json'))
    T.write_xmeml(tl, os.path.join(out, 'roughcut.xml'))
    if a.fcpxml:
        T.write_fcpxml(tl, os.path.join(out, 'roughcut.fcpxml'))
    C.jdump(words_tl, os.path.join(out, 'cut_words.json'))
    with open(os.path.join(out, 'decisions.tsv'), 'w', encoding='utf-8') as f:
        f.write('id\tfile\tstart\tend\tdecision\treason\ttext\n')
        for u in units:
            kw = cut.kept(u)
            dec = 'DROP' if not kw else ('KEEP' if len(kw) == len(u['words']) else 'PART')
            txt = ' '.join(w['w'] if not w.get('drop') else f"[{w['w']}]" for w in u['words']) or u['text']
            why = u['why'] or '; '.join(sorted({w['drop'] for w in u['words'] if w.get('drop')}))
            f.write(f"{u['id']}\t{u['f'] + 1}\t{C.tc(u['s'])}\t{C.tc(u['e'])}\t{dec}\t{why}\t{txt}\n")
    raw = sum(d for _, d in sources)
    from collections import Counter
    reasons = Counter((u['why'] or 'partly').split(' (')[0].split(' ->')[0] for u in units if not cut.kept(u) or len(cut.kept(u)) < len(u['words']))
    C.uprint(f'raw {C.tc(raw)} -> cut {C.tc(tf / F)} ({tf / F / raw:.0%}) | clips {len(cuts)} | pause markers {len(markers)} | '
             f'intro ends at island {intro_until}')
    C.uprint('removed / trimmed islands by reason: ' + ', '.join(f'{k} {v}' for k, v in reasons.most_common()))
    C.uprint('out:', out)


if __name__ == '__main__':
    main()
