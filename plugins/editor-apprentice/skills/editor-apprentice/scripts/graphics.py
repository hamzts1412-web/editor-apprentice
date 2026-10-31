"""Place the client's graphics/templates on the words the talent says — with their sound effects, in the same pass.

  python graphics.py <project> --profile <client>/profile.json [--timeline _auto/zoomed.timeline.json] [--xml out.xml] [--fcpxml out.fcpxml]

Input rows: <project>/_auto/graphics_src.json — written by Claude after reading the cut transcript (_auto/cut_text.txt):
  [kind, text, anchor_regex, "m:ss", until?, caption?]
    kind     a key of profile.graphics.kinds (e.g. "name", "place", "date", "cta")
    text     what goes in the template (what the talent SAID, spelled from the script)
    anchor   regex of the word it lands on; "m:ss" = roughly where in the cut (search ±8 s)
    until    optional: seconds, or a regex of the word where the talent moves on (ends 0.2 s before it)
    caption  optional: second text field
profile.graphics.kinds.<kind> = {"dur": 4.2, "lead": 0.3, "track": "V5", "file": "<template file>",
                                 "parts": [{"file": "...", "offset": 0.44, "track_up": 1}],   # sets (bg + label)
                                 "sfx": [{"file": "whoosh.wav", "s0": 4.2, "dur": 0.44, "offset": 0, "gain_db": -20, "track": "A3"}]}
Output: _auto/graphics_plan.json (t0/t1/level per graphic) + the timeline with SFX clips, one marker per graphic
(text + kind), and the template itself when it is a still/video file the XML can carry (.png/.mov with alpha…).
Templates that live inside the NLE (.mogrt, Fusion/Motion titles) are placed from the plan (references/nle/*.md).
Overlaps: a graphic never cuts another — an overlapping one goes `level` tracks up.
"""
import argparse, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import timeline as T

NORM = str.maketrans('أإآةىؤئ', 'اااهيوي')


def nrm(s):
    return re.sub(r'[ً-ْـ]', '', s).translate(NORM).casefold()


def find(words, rx, t, win=8):
    hits = [w for w in words if abs(w['s'] - t) <= win and re.search(nrm(rx), nrm(w['w']))]
    return min(hits, key=lambda w: abs(w['s'] - t)) if hits else None


def up(trk, n):
    return f'{trk[0]}{int(trk[1:]) + n}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('--profile'); ap.add_argument('--timeline')
    ap.add_argument('--src'); ap.add_argument('--xml'); ap.add_argument('--fcpxml'); ap.add_argument('-o')
    a = ap.parse_args()
    prof = C.load_profile(a.profile)
    g = prof['graphics']
    kinds = g.get('kinds') or {}
    out = C.out_dir(a.project)
    words = C.jload(os.path.join(out, 'cut_words.json'))
    rows = C.jload(a.src or os.path.join(out, 'graphics_src.json'))
    plan = []
    drift = 0.0   # rough times drift when the cut changed after the rows were written; follow the last found anchor
    for row in rows:
        kind, text, anchor, approx = row[:4]
        until = row[4] if len(row) > 4 else None
        caption = row[5] if len(row) > 5 else ''
        k = kinds.get(kind)
        if k is None:
            C.uprint('UNKNOWN KIND', kind, '— add it to profile.graphics.kinds'); continue
        t_hint = C.parse_time(approx)
        w = find(words, anchor, t_hint + drift) or find(words, anchor, t_hint + drift, 20)
        if not w:
            C.uprint('ANCHOR NOT FOUND', kind, text, anchor, approx); continue
        drift = w['s'] - t_hint
        t0 = round(max(0, w['s'] - k.get('lead', g.get('lead', 0.3))), 2)
        t1 = t0 + k.get('dur', 4.0)
        if isinstance(until, (int, float)):
            t1 = t0 + until
        elif isinstance(until, str) and until:
            later = [x for x in words if x['s'] > w['s'] + 1 and re.search(nrm(until), nrm(x['w']))]
            if later:
                t1 = min(later, key=lambda x: x['s'])['s'] - 0.2
            else:
                C.uprint('UNTIL NOT FOUND', text, until)
        t1 = round(min(max(t1, t0 + k.get('min', 1.5)), t0 + k.get('max', g.get('max', 14))), 2)
        plan.append({'kind': kind, 'text': text, 'caption': caption, 't0': t0, 't1': t1, 'word': w['w']})
    plan.sort(key=lambda p: p['t0'])
    # stacking: kinds with their own track (own_track: true, e.g. a CTA) stay at level 0; the rest take the lowest free level
    ends = []
    for p in plan:
        if kinds[p['kind']].get('own_track'):
            p['level'] = 0
            continue
        span = kinds[p['kind']].get('levels_used', 1)   # a set (bg + label) occupies several tracks
        lvl = next((i for i, e in enumerate(ends) if e <= p['t0'] - 0.04), len(ends))
        if lvl == len(ends):
            ends.append(0)
        ends[lvl] = p['t1']
        p['level'] = lvl * span
    C.jdump(plan, os.path.join(out, 'graphics_plan.json'))

    tl = C.jload(a.timeline) if a.timeline else (C.jload(os.path.join(out, 'zoomed.timeline.json')) if os.path.exists(os.path.join(out, 'zoomed.timeline.json'))
                                                 else C.jload(os.path.join(out, 'roughcut.timeline.json')))
    tl['items'] = [x for x in tl['items'] if not x.get('from_graphics')]
    tl['markers'] = [m for m in tl.get('markers', []) if not m.get('from_graphics')]
    placed_files = 0
    for p in plan:
        k = kinds[p['kind']]
        tl['markers'].append({'t': p['t0'], 'name': f"{p['kind']}: {p['text']}"[:60], 'comment': p.get('caption', ''), 'from_graphics': True})
        parts = [{'file': k.get('file'), 'offset': 0, 'track_up': 0}] + list(k.get('parts') or [])
        for part in parts:
            f = part.get('file')
            if f and os.path.splitext(f)[1].lower() not in T.GRAPHIC_EXT and os.path.exists(f):
                t0 = p['t0'] + part.get('offset', 0)
                tl['items'].append({'trk': up(k.get('track', 'V5'), p['level'] + part.get('track_up', 0)), 'kind': 'still' if os.path.splitext(f)[1].lower() in T.STILL_EXT else 'clip',
                                    't0': t0, 't1': p['t1'], 's0': part.get('s0', 0), 'file': f, 'name': p['text'], 'from_graphics': True})
                placed_files += 1
        for s in k.get('sfx') or []:
            if not os.path.exists(s['file']):
                C.uprint('SFX FILE MISSING', s['file']); continue
            t0 = p['t0'] + s.get('offset', 0)
            tl['items'].append({'trk': s.get('track', 'A3'), 'kind': 'audio', 't0': t0, 't1': t0 + s['dur'], 's0': s.get('s0', 0),
                                'file': s['file'], 'name': os.path.basename(s['file']), 'gain_db': s.get('gain_db'), 'from_graphics': True})
    o = a.o or os.path.join(out, 'graphics.timeline.json')
    C.jdump(tl, o)
    if a.xml:
        T.write_xmeml(tl, a.xml)
    if a.fcpxml:
        T.write_fcpxml(tl, a.fcpxml)
    for p in plan:
        cap = f" [{p['caption']}]" if p['caption'] else ''
        C.uprint(f"{C.mmss(p['t0'])}  {p['t1'] - p['t0']:4.1f}s  {p['kind']:8} L{p['level']}  {p['text']}{cap}  ({p['word']})")
    sfx = sum(len(kinds[p['kind']].get('sfx') or []) for p in plan)
    C.uprint(f'{len(plan)} graphics, levels used {1 + max((p["level"] for p in plan), default=0)}, SFX clips {sfx}, '
             f'template files placed by XML {placed_files} (the rest: place from the plan in the NLE)\nout: {o}')


if __name__ == '__main__':
    main()
