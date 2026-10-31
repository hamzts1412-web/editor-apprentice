"""What did the editor change after our hand-off? Compare our timeline with his final one.

  python final_diff.py <ours> <final> [--seq NAME] [--words DIR] [--dialog A1] [-o diff.json]
     ours / final: .prproj / .xml / .fcpxml / timeline .json (take "ours" right before the hand-off)

Everything is mapped through SOURCE time of the dialog (talking-head) audio, so his ripple edits don't shift the
comparison. Tracks are matched by content, not by number — if he inserted a track (e.g. a graded export on V2) our
V3 is found on his V4. A full-length single clip on a track (graded return, music bed) is reported and ignored.
Report sections: cuts (removed / added source with the words), per-layer changes (kept / moved / resized / removed /
added), new media he brought in, transitions. Ask the editor only the WHY of what you can't explain.
"""
import argparse, os, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import timeline as T


def base(x):
    return os.path.basename(x.get('file') or '') or x.get('name') or '?'


def load(path, seq):
    tl = T.read_any(path, seq) if not path.endswith('.json') else C.jload(path)
    items = tl['items'] if isinstance(tl, dict) else tl
    for x in items:
        x.setdefault('kind', T.kind_of(x.get('file'), x['trk'], x.get('tag', ''), x.get('name', '')))
    return items


def dialog_track(items, files=None):
    cov = defaultdict(float)
    for x in items:
        if x['trk'].startswith('A') and x['kind'] == 'audio' and (files is None or base(x) in files):
            cov[x['trk']] += x['t1'] - x['t0']
    # a single full-length clip is a mixdown / graded return, not the dialog edit
    n = Counter(x['trk'] for x in items)
    best = sorted(cov, key=lambda t: (n[t] > 1, cov[t]), reverse=True)
    return best[0] if best else 'A1'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ours'); ap.add_argument('final')
    ap.add_argument('--seq'); ap.add_argument('--seq-final')
    ap.add_argument('--words', help='folder with the raw *.islands.json (to print the words of cut changes)')
    ap.add_argument('--dialog'); ap.add_argument('-o')
    ap.add_argument('--final-words', help="the final's own transcript (*.islands.json) — when the final's cut was recovered "
                                          "from a render, every 'removed' piece is double-checked against what the final says")
    a = ap.parse_args()
    ftoks = []
    if a.final_words:
        ftoks = [C.tok(w['w']) for i in C.jload(a.final_words)['islands'] for w in i['words']]

    def in_final(text):
        """share of the piece's words found in order somewhere in the final transcript (fuzzy per word)"""
        import difflib
        t = [C.tok(x) for x in text.split() if C.tok(x)]
        if len(t) < 3 or not ftoks:
            return None
        best = 0.0
        heads = {t[0], t[1]}
        for k, x in enumerate(ftoks):
            if x in heads or difflib.SequenceMatcher(None, x, t[0]).ratio() >= 0.75:
                win = ftoks[max(0, k - 1):k + len(t) + 2]
                hit = sum(1 for y in t if any(difflib.SequenceMatcher(None, y, z).ratio() >= 0.75 for z in win))
                best = max(best, hit / len(t))
        return best
    ours, fin = load(a.ours, a.seq), load(a.final, a.seq_final or a.seq)
    d_o = a.dialog or dialog_track(ours)
    dfiles = {base(x) for x in ours if x['trk'] == d_o}
    d_f = a.dialog or dialog_track(fin, dfiles)
    end_f = max(x['t1'] for x in fin)

    words = {}
    if a.words:
        for f in os.listdir(a.words):
            if f.endswith('.islands.json'):
                d = C.jload(os.path.join(a.words, f))
                words[os.path.basename(d['source'])] = [w for i in d['islands'] for w in i['words']]

    def txt(src, s, e):
        return ' '.join(w['w'] for w in words.get(src, []) if w['e'] > s + 0.02 and w['s'] < e - 0.02)

    def smap(items, trk):
        return sorted([(x['t0'], x['t1'], base(x), x['s0']) for x in items if x['trk'] == trk and x['kind'] == 'audio'])

    MO, MF = smap(ours, d_o), smap(fin, d_f)

    def to_src(t, m):
        for p, q, f, s in m:
            if p <= t < q:
                return f, s + t - p
        return None

    def from_src(fs, m):
        if not fs:
            return None
        f, s = fs
        for p, q, ff, s0 in m:
            if ff == f and s0 - 0.01 <= s < s0 + q - p:
                return p + s - s0
        return None

    def o2f(t):
        r = from_src(to_src(t, MO), MF)
        if r is None:   # time falls in a removed piece: use the nearest mapped neighbour
            for dt in (0.04, -0.04, 0.2, -0.2, 0.5, -0.5, 1, -1):
                r = from_src(to_src(t + dt, MO), MF)
                if r is not None:
                    return r - dt
        return r

    rep = []
    P = rep.append
    # ------------------------------------------------ ignored full-length tracks
    by_trk = defaultdict(list)
    for x in fin:
        by_trk[x['trk']].append(x)
    ignored = {t for t, xs in by_trk.items() if len(xs) == 1 and xs[0]['t1'] - xs[0]['t0'] >= 0.9 * end_f and t not in (d_f,)}
    if ignored:
        P('IGNORED full-length clips (graded return / mixdown / music bed): ' +
          ', '.join(f'{t} {base(by_trk[t][0])}' for t in sorted(ignored, key=T.trk_key)))
    P(f'dialog track: ours {d_o} -> final {d_f}')

    # ------------------------------------------------ cuts
    def cover(m):
        c = defaultdict(list)
        for p, q, f, s in m:
            c[f].append((s, s + q - p))
        return c

    def minus(x, y):
        out = []
        for p, q in x:
            segs = [(p, q)]
            for c, d in y:
                segs = [z for s, e in segs for z in ((s, min(e, c)), (max(s, d), e)) if z[1] - z[0] > 0.045]
            out += segs
        return out

    co, cf = cover(MO), cover(MF)
    rem = sorted((f, p, q) for f in set(co) | set(cf) for p, q in minus(co.get(f, []), cf.get(f, [])))
    add = sorted((f, p, q) for f in set(co) | set(cf) for p, q in minus(cf.get(f, []), co.get(f, [])))
    lo, lf = (MO[-1][1] if MO else 0), (MF[-1][1] if MF else 0)
    P(f'\n=== CUTS === ours {len(MO)} clips {C.tc(lo)} | final {len(MF)} clips {C.tc(lf)} | '
      f'removed {sum(q - p for _, p, q in rem):.1f}s in {len(rem)} pieces, added back {sum(q - p for _, p, q in add):.1f}s in {len(add)}')
    small = [r for r in rem if r[2] - r[1] < 0.3]
    P(f'  head/tail trims < 0.3 s: {len(small)} (median {sorted(q - p for _, p, q in small)[len(small) // 2] if small else 0:.2f}s) '
      '— many of these = our air/lead setting is too loose')
    P('-- removed by the editor --')
    doubt = 0
    for f, p, q in rem:
        if q - p >= 0.3:
            t = from_src((f, p), MO)
            said = txt(f, p, q)
            chk = in_final(said) if ftoks else None
            flag = ''
            if chk is not None and chk >= 0.7:
                flag = f'   [DOUBT: {chk:.0%} of these words are in the final transcript — alignment miss?]'
                doubt += 1
            P(f'  ours@{C.mmss(t) if t is not None else "?"} {f} {p:.2f}-{q:.2f} ({q - p:.2f}s) «{said}»{flag}')
    if ftoks:
        P(f'  ({doubt} removed pieces look present in the final transcript — treat them as not removed)')
    P('-- added back by the editor --')
    for f, p, q in add:
        if q - p >= 0.1:
            t = from_src((f, p), MF)
            P(f'  final@{C.mmss(t) if t is not None else "?"} {f} {p:.2f}-{q:.2f} ({q - p:.2f}s) «{txt(f, p, q)}»')

    # ------------------------------------------------ layers: match our items to his, track mapping by content
    layer_o = [x for x in ours if x['trk'] not in (d_o,) and x['kind'] != 'transition' and not (x['trk'].startswith('V') and x['trk'] == 'V1' and base(x) in dfiles)]
    layer_f = [x for x in fin if x['trk'] not in ignored | {d_f} and x['kind'] != 'transition'
               and not (x['trk'].startswith('V') and base(x) in dfiles and x['kind'] == 'clip')]
    for x in layer_o:
        x['_f0'] = o2f(x['t0'])
        x['_f1'] = o2f(x['t1'] - 0.01)
    pool = defaultdict(list)
    for y in layer_f:
        pool[base(y)].append(y)
    pairs = []
    for x in sorted(layer_o, key=lambda x: x['t0']):
        if x['_f0'] is None:
            continue
        cand = []
        for win in (1.5, 4.0):   # second pass: he moved it a few seconds (a CTA moved earlier, a label re-timed)
            cand = [y for y in pool[base(x)] if not y.get('_m') and y['trk'][0] == x['trk'][0] and abs(y['t0'] - x['_f0']) < win]
            if cand:
                break
        if cand:
            y = min(cand, key=lambda y: abs(y['t0'] - x['_f0']))
            y['_m'] = True
            x['_m'] = y
            pairs.append((x, y))
    tmap = Counter((x['trk'], y['trk']) for x, y in pairs)
    best = {}
    for (to, tf), n in tmap.most_common():
        best.setdefault(to, tf)
    moved_tracks = {k: v for k, v in best.items() if k != v}
    if moved_tracks:
        P('\ntrack mapping (ours -> his): ' + ', '.join(f'{k}->{v}' for k, v in sorted(moved_tracks.items(), key=lambda z: T.trk_key(z[0]))))

    P('\n=== LAYERS (ours -> his) ===')
    stats = defaultdict(Counter)
    detail = defaultdict(list)
    for x in layer_o:
        key = f"{x['trk']} {x['kind']} {base(x)[:28]}"
        y = x.get('_m')
        if not y:
            stats[key]['removed'] += 1
            detail[key].append(f"removed ours@{C.mmss(x['t0'])} ({x['t1'] - x['t0']:.2f}s)")
            continue
        d0 = y['t0'] - x['_f0']
        dl = (y['t1'] - y['t0']) - (x['t1'] - x['t0'])
        if abs(d0) < 0.08 and abs(dl) < 0.08:
            stats[key]['kept'] += 1
        else:
            stats[key]['moved' if abs(d0) >= 0.08 else 'resized'] += 1
            detail[key].append(f"{'moved' if abs(d0) >= 0.08 else 'resized'} ours@{C.mmss(x['t0'])} start {d0:+.2f}s length {dl:+.2f}s")
        if best.get(x['trk']) and y['trk'] != best[x['trk']]:
            stats[key]['other track'] += 1
            detail[key].append(f"on {y['trk']} instead of {best[x['trk']]} @{C.mmss(y['t0'])} (stacked to avoid an overlap?)")
    for k in sorted(stats, key=lambda k: T.trk_key(k.split()[0])):
        P(f'  {k:45} ' + ', '.join(f'{a} {b}' for a, b in stats[k].most_common()))
        for d in detail[k][:12]:
            P(f'      {d}')
        if len(detail[k]) > 12:
            P(f'      … {len(detail[k]) - 12} more')

    added = [y for y in layer_f if not y.get('_m')]
    P(f'\n=== ADDED BY THE EDITOR === {len(added)} items')
    groups = defaultdict(list)
    for y in added:
        groups[(y['trk'], y['kind'], base(y))].append(y)
    for (t, k, b), ys in sorted(groups.items(), key=lambda z: (T.trk_key(z[0][0]), -len(z[1]))):
        durs = sorted(y['t1'] - y['t0'] for y in ys)
        P(f'  {t:4} {k:10} {b[:40]:40} x{len(ys):<4} median {durs[len(durs) // 2]:.2f}s  first @' +
          ', '.join(C.mmss(y['t0']) for y in sorted(ys, key=lambda y: y['t0'])[:6]))
    ours_media = {base(x) for x in ours}
    new_media = sorted({base(y) for y in added if base(y) not in ours_media and y.get('file')})
    if new_media:
        P(f'\nnew media files he brought in ({len(new_media)}): ' + ', '.join(new_media[:40]))
    vids = [y for y in added if y['kind'] == 'clip' and y['trk'].startswith('V')]
    if vids:
        tot = sum(y['t1'] - y['t0'] for y in vids)
        P(f'b-roll / extra video: {len(vids)} clips, {tot:.0f}s = {tot / end_f:.0%} of the video')
    tr = Counter((x['trk'], x.get('name') or 'transition') for x in fin if x['kind'] == 'transition')
    to = Counter((x['trk'], x.get('name') or 'transition') for x in ours if x['kind'] == 'transition')
    if tr or to:
        P('\n=== TRANSITIONS === ours ' + ', '.join(f'{t} {n}x{c}' for (t, n), c in to.items()) +
          ' | his ' + ', '.join(f'{t} {n}x{c}' for (t, n), c in tr.items()))
    C.uprint('\n'.join(rep))
    if a.o:
        C.jdump({'report': rep, 'removed': rem, 'added': add, 'track_map': best}, a.o)


if __name__ == '__main__':
    main()
