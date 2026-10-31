"""Measure an editor's style from a FINISHED project — the evidence the editor doesn't have to explain.

  python measure.py <project.prproj | .xml | .fcpxml | timeline.json> [--seq NAME] [--no-audio] [-o style.json]

Reads every track and reports: the talking-head rhythm (clip lengths, cuts/min, air left before/after the voice at cuts,
pauses kept inside clips, breaths), zoom layers / scale keyframes, graphics (which templates, how often, how long, stacking),
SFX and whether they sit on graphic starts, b-roll share, transitions, music, captions — plus suggested profile values.
Audio analysis needs the source media at the paths stored in the project (skip with --no-audio).
"""
import argparse, os, sys
from collections import Counter, defaultdict
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import timeline as T
from final_diff import base, dialog_track


def pct(a, q=(10, 50, 90)):
    return np.percentile(a, q).round(2).tolist() if len(a) else []


def measure(tl, audio=True, max_clips=400):
    items = tl['items']
    for x in items:
        x.setdefault('kind', T.kind_of(x.get('file'), x['trk'], x.get('tag', ''), x.get('name', '')))
    fps = tl.get('fps') or 25
    end = max(x['t1'] for x in items)
    R, S = [], {}
    P = R.append
    n_trk = Counter(x['trk'] for x in items)
    full = {t for t in n_trk if n_trk[t] == 1 and [x for x in items if x['trk'] == t][0]['t1'] - [x for x in items if x['trk'] == t][0]['t0'] >= 0.9 * end}
    d_a = dialog_track([x for x in items if x['trk'] not in full])
    dfiles = Counter(base(x) for x in items if x['trk'] == d_a)
    # camera angles = video tracks cut in sync with the dialog audio (separately recorded audio, 2-cam shoots)
    bounds = {round(x['t0'] * fps) for x in items if x['trk'] == d_a} | {round(x['t1'] * fps) for x in items if x['trk'] == d_a}
    angles = {}
    for t in {x['trk'] for x in items if x['trk'].startswith('V') and x['trk'] not in full}:
        xs = [x for x in items if x['trk'] == t and x['kind'] == 'clip']
        if len(xs) >= 10:
            hit = sum(1 for x in xs if {round(x['t0'] * fps) + d for d in (-1, 0, 1)} & bounds)
            if hit / len(xs) > 0.6:
                angles[t] = round(sum(x['t1'] - x['t0'] for x in xs) / end, 3)
    vt = Counter(x['trk'] for x in items if x['trk'].startswith('V') and base(x) in dfiles and x['kind'] == 'clip' and x['trk'] not in full)
    d_v = vt.most_common(1)[0][0] if vt else (min(angles, key=T.trk_key) if angles else 'V1')
    P(f"# Style measurement — {tl.get('name')}  ({C.tc(end)}, {fps} fps, {len(items)} items)")
    if full:
        P(f"full-length single clips ignored (graded return / mixdown / music bed): {', '.join(sorted(full))}")
    P(f'talking head: video {d_v}, audio {d_a}, sources: ' + ', '.join(f'{k} x{v}' for k, v in dfiles.most_common(6)))
    if len(angles) > 1 or (angles and d_v not in angles):
        P('camera angles cut in sync with the dialog: ' + ', '.join(f'{t} (covers {c:.0%}; sources ' +
          ', '.join(f'{a[:28]} x{b}' for a, b in Counter(base(x) for x in items if x['trk'] == t).most_common(2)) + ')'
          for t, c in sorted(angles.items(), key=lambda z: T.trk_key(z[0]))) +
          ' — the highest one is what is seen unless it is scaled/cropped (picture-in-picture?): check one frame in the NLE')
    S['angles'] = angles

    # ------------------------------------------------ rhythm
    clips = sorted([x for x in items if x['trk'] == d_a and x['kind'] == 'audio'], key=lambda x: x['t0'])
    L = np.array([x['t1'] - x['t0'] for x in clips])
    S['dialog'] = {'clips': len(clips), 'len_pct10_50_90': pct(L), 'cuts_per_min': round(len(clips) / (end / 60), 2)}
    P(f'\n## Rhythm\n- {len(clips)} talking-head clips, {len(clips) / (end / 60):.1f} cuts/min, clip length p10/50/90 {pct(L)} s')
    gaps = [b['t0'] - a['t1'] for a, b in zip(clips, clips[1:]) if b['t0'] - a['t1'] > 0.04]
    if gaps:
        P(f'- {len(gaps)} gaps between dialog clips on the timeline (b-roll/sound breaks?), p50 {np.median(gaps):.2f}s')
    srcs = {}
    for x in clips:
        if x.get('file') and os.path.exists(x['file']) and x['file'] not in srcs:
            srcs[x['file']] = None
    raw = sum(filter(None, (C.media_duration(f) for f in srcs))) if srcs else 0
    if raw:
        P(f'- kept {sum(L):.0f}s of {raw:.0f}s raw = {sum(L) / raw:.0%}')
        S['dialog']['kept_ratio'] = round(sum(L) / raw, 3)

    if audio and srcs:
        energy = {}
        for f in srcs:
            db = C.energy_db(f)
            energy[f] = (db, C.speech_level(db))
        head_air, tail_air, mid_heads, inner_pauses, breath_heads = [], [], 0, [], 0
        sample = clips if len(clips) <= max_clips else [clips[i] for i in np.linspace(0, len(clips) - 1, max_clips).astype(int)]
        for x in sample:
            if x['file'] not in energy:
                continue
            db, lvl = energy[x['file']]
            a, b = int(x['s0'] * 100), int((x['s0'] + x['t1'] - x['t0']) * 100)
            if b - a < 10 or b > len(db):
                continue
            seg = db[a:b]
            voiced = np.where(seg > lvl - 12)[0]
            if not len(voiced):
                continue
            if seg[:3].mean() > lvl - 14:
                mid_heads += 1                      # the clip starts inside speech (a cut between words)
            else:
                # same definition as autocut's lead: from the in point to where the first word starts rising
                k = k0 = voiced[0]
                while k > 0 and k0 - k < 15 and seg[k - 1] > lvl - 26:
                    k -= 1
                head_air.append(k / 100)
                pre = seg[:k]
                if len(pre) >= 8 and (pre > lvl - 26).sum() >= 8:
                    breath_heads += 1               # a breath kept before the first word
            loud = np.where(seg > lvl - 16)[0]      # autocut's tail: after the last frame above decay level
            tail_air.append((len(seg) - 1 - loud[-1]) / 100)
            sil = seg[voiced[0]:voiced[-1]] < lvl - 22
            run = 0
            for s in sil:
                if s:
                    run += 1
                elif run:
                    if run >= 12:
                        inner_pauses.append(run / 100)
                    run = 0
        ha, ta = np.array(head_air) * fps, np.array(tail_air) * fps
        P(f'- air before the voice where a clip starts after a silence: p10/50/90 {pct(ha)} frames ({len(ha)} clips); '
          f'{mid_heads} clips start mid-speech')
        P(f'- air after the last word: p10/50/90 {pct(ta)} frames')
        P(f'- breaths kept at clip starts after a silence: {breath_heads}/{len(ha)}')
        ip = np.array(inner_pauses)
        P(f'- pauses ≥ 0.12 s kept INSIDE clips: {len(ip)} in {len(sample)} clips, p50/90/max '
          f'{[round(float(np.median(ip)), 2), round(float(np.percentile(ip, 90)), 2), round(float(ip.max()), 2)] if len(ip) else []} s')
        S['air'] = {'head_frames_p10_50_90': pct(ha), 'tail_frames_p10_50_90': pct(ta), 'mid_speech_heads': mid_heads,
                    'breath_heads': breath_heads, 'inner_pauses': len(ip),
                    'inner_pause_p90': round(float(np.percentile(ip, 90)), 2) if len(ip) else 0}
        S['suggest_cut'] = {'lead_frames': int(round(np.median(ha))) if len(ha) else None,
                            'tail_frames': int(round(np.median(ta))) if len(ta) else None,
                            'breaths': 'all' if len(ha) and breath_heads / len(ha) > 0.5 else 'mid_speech',
                            'merge_gap': round(float(np.percentile(ip, 90)), 2) if len(ip) > len(sample) * 0.3 else 0}

    # ------------------------------------------------ layers by track
    P('\n## Tracks')
    for t in sorted({x['trk'] for x in items}, key=T.trk_key):
        xs = [x for x in items if x['trk'] == t and x['kind'] != 'transition']
        if not xs or t in (d_a,):
            continue
        cov = sum(x['t1'] - x['t0'] for x in xs)
        k = Counter(x['kind'] for x in xs)
        names = Counter(base(x) for x in xs)
        P(f'- {t:4} {len(xs):4} items, covers {cov / end:5.1%}  kinds {dict(k)}  top: ' +
          ', '.join(f'{a[:30]} x{b}' for a, b in names.most_common(3)))

    # ------------------------------------------------ zoom
    adj = sorted([x for x in items if x['kind'] == 'adjustment'], key=lambda x: x['t0'])
    kf = [x for x in items if x.get('fx', {}).get('scale')]
    P('\n## Zoom / punch-ins')
    if adj:
        d = np.array([x['t1'] - x['t0'] for x in adj])
        g = np.array([b['t0'] - a['t1'] for a, b in zip(adj, adj[1:])])
        zoomed = sum(d) / max(1e-6, sum(L)) if len(L) else 0
        P(f'- {len(adj)} adjustment layers on {sorted(Counter(x["trk"] for x in adj))}; length p10/50/90 {pct(d)} s; '
          f'wide gaps p10/50/90 {pct(g[g > 0.01])} s; back-to-back {int((g < 0.04).sum())}; ≈{zoomed:.0%} of the talking head')
        P('  (open one layer in the NLE or run nle-specific readers for its keyframes: scale in, ease, drift back)')
        S['zoom'] = {'method': 'adjustment', 'layers': len(adj), 'len_p50': float(np.median(d)),
                     'gap_p10_50': pct(g[g > 0.01], (10, 50)), 'back_to_back': int((g < 0.04).sum())}
    if kf:
        sc = [v for x in kf for _, v in x['fx']['scale']]
        P(f'- {len(kf)} clips with scale set/keyframed, values p10/50/90 {pct(np.array(sc))} %')
        S.setdefault('zoom', {})['keyframed_clips'] = len(kf)
    if not adj and not kf:
        P('- none found (or done inside effects this reader can\'t see — ask)')

    # ------------------------------------------------ graphics
    gr = sorted([x for x in items if x['kind'] == 'graphic' and x['trk'].startswith('V')], key=lambda x: x['t0'])
    P('\n## Graphics / templates')
    if gr:
        P(f'- {len(gr)} graphics = {len(gr) / (end / 60):.1f}/min')
        for nm, n in Counter(base(x) for x in gr).most_common(12):
            d = [x['t1'] - x['t0'] for x in gr if base(x) == nm]
            P(f'  - {nm[:40]:40} x{n:<4} length p10/50/90 {pct(np.array(d))} s, tracks {sorted(Counter(x["trk"] for x in gr if base(x) == nm), key=T.trk_key)}')
        pairs = Counter()
        for a in gr:
            for b in gr:
                if a is not b and 0 < b['t0'] - a['t0'] < 1.5 and b['trk'] != a['trk']:
                    pairs[(base(a), base(b), round(b['t0'] - a['t0'], 2))] += 1
        if pairs:
            P('- graphics that come as a set (B starts shortly after A, track above):')
            for (a, b, dt), n in pairs.most_common(6):
                if n >= 3:
                    P(f'  - {a[:28]} + {b[:28]} after {dt:.2f}s  x{n}')
        S['graphics'] = {'count': len(gr), 'per_min': round(len(gr) / (end / 60), 2),
                         'by_name': dict(Counter(base(x) for x in gr).most_common(20))}
    else:
        P('- none')

    # ------------------------------------------------ SFX
    sfx = [x for x in items if x['trk'].startswith('A') and x['trk'] not in full | {d_a} and base(x) not in dfiles]
    P('\n## Sound effects / music')
    if sfx:
        long = [x for x in sfx if x['t1'] - x['t0'] > 30]
        if long:
            P(f'- music beds / long audio: {len(long)} (' + ', '.join(sorted({base(x)[:30] for x in long})) + ')')
        short = [x for x in sfx if x['t1'] - x['t0'] <= 30]
        for nm, n in Counter(base(x) for x in short).most_common(8):
            xs = [x for x in short if base(x) == nm]
            P(f'  - {nm[:40]:40} x{n:<4} length p50 {np.median([x["t1"] - x["t0"] for x in xs]):.2f}s, '
              f'source in points {sorted(Counter(round(x["s0"], 1) for x in xs).most_common(3))}')
        if gr:
            on = 0
            for g in gr:
                if any(abs(s['t0'] - g['t0']) <= 2.5 / fps for s in short):
                    on += 1
            P(f'- {on}/{len(gr)} graphics have a sound starting on their first frame (±2 frames)')
            S['sfx_on_graphics'] = round(on / len(gr), 2)
    else:
        P('- none')

    # ------------------------------------------------ b-roll, transitions, captions
    br = [x for x in items if x['trk'].startswith('V') and x['trk'] != d_v and x['trk'] not in full and x['kind'] == 'clip'
          and base(x) not in dfiles and x['trk'] not in angles]
    st = [x for x in items if x['kind'] == 'still']
    P('\n## B-roll, stills, transitions, captions')
    if br:
        P(f'- b-roll: {len(br)} clips, {sum(x["t1"] - x["t0"] for x in br) / end:.0%} of the video, length p50 '
          f'{np.median([x["t1"] - x["t0"] for x in br]):.2f}s, sources: ' + ', '.join(f'{a[:25]} x{b}' for a, b in Counter(base(x) for x in br).most_common(4)))
    if st:
        P(f'- stills: {len(st)}, length p50 {np.median([x["t1"] - x["t0"] for x in st]):.2f}s; repeated overlays: ' +
          ', '.join(f'{a[:30]} x{b}' for a, b in Counter(base(x) for x in st).most_common(3) if b > 2))
    tr = Counter(x['trk'] for x in items if x['kind'] == 'transition')
    if tr:
        P('- transitions: ' + ', '.join(f'{t} x{n}' for t, n in sorted(tr.items(), key=lambda z: T.trk_key(z[0]))))
    cap = [x for x in items if x['kind'] == 'caption']
    if cap:
        P(f'- caption track items: {len(cap)} (from {C.mmss(min(x["t0"] for x in cap))} to {C.mmss(max(x["t1"] for x in cap))})')
    if tl.get('markers'):
        P(f'- markers: {len(tl["markers"])}: ' + ', '.join(m['name'][:20] for m in tl['markers'][:10]))
    return R, S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('--seq'); ap.add_argument('--no-audio', action='store_true'); ap.add_argument('-o')
    a = ap.parse_args()
    tl = T.read_any(a.project, a.seq)
    R, S = measure(tl, audio=not a.no_audio)
    C.uprint('\n'.join(R))
    if S.get('suggest_cut'):
        C.uprint('\nsuggested profile.cut values (confirm with the editor): ' + str(S['suggest_cut']))
    if a.o:
        C.jdump({'report': R, 'stats': S}, a.o, indent=1)


if __name__ == '__main__':
    main()
