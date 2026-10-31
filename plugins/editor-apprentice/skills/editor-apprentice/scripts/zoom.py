"""Punch-in zooms on the talking head, placed like the client's editor does (profile.zoom).

  python zoom.py <timeline.json | project> --profile <client>/profile.json [--seq NAME] [--start-after SEC]
                 [-o zoomed.timeline.json] [--xml out.xml] [--fcpxml out.fcpxml] [--scores-only]

1. scores every cut on the dialog video track: how visible the jump is (last frame before vs first after, from the raws;
   <1 invisible, ~4 hand move, ~8 body shift, 20+ big jump) -> <project>/_auto/jump_scores.json
2. plans zooms with the profile rules:
   ramp  — a layer starts ON a cut: scale 100 -> scale_in in ease_in s, slow drift back to 100 by `layer` s; the next layer
           starts on the most visible cut gap_min..gap_max s after; NEVER zoom straight into zoom (gap_min wide shot);
           a big jump (>= restart) inside a running layer after min_len s ends the layer on it (back to wide hides it)
   punch — static push-in (punch_scale) that toggles on visible cuts, never two pushed clips in a row on the same take
3. applies them: method=keyframes -> Scale/Position keyframes on the dialog clips (imports with the XML into any NLE);
   method=adjustment -> a list of layer start/end times to place an adjustment layer in the NLE (see references/nle).
"""
import argparse, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import timeline as T


def jump_scores(clips):
    import cv2
    caps = {}

    def frame(path, t):
        if path not in caps:
            caps[path] = cv2.VideoCapture(path)
        c = caps[path]
        c.set(cv2.CAP_PROP_POS_MSEC, max(0, t) * 1000)
        ok, f = c.read()
        if not ok:
            return None
        g = cv2.cvtColor(cv2.resize(f, (160, 90), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(g, (5, 5), 0).astype(np.float32)

    out = []
    for a, b in zip(clips, clips[1:]):
        s1 = a['s0'] + a['t1'] - a['t0']
        fa, fb = frame(a['file'], s1 - 0.06), frame(b['file'], b['s0'] + 0.02)
        score = float(np.mean(np.abs(fa - fb))) if fa is not None and fb is not None else 0.0
        out.append({'t': round(b['t0'], 3), 'score': round(score, 2),
                    'same_take': a['file'] == b['file'] and abs(b['s0'] - s1) < 0.02})
        if len(out) % 200 == 0:
            print(f'  scored {len(out)}/{len(clips) - 1} cuts', flush=True)
    return out


def plan_ramp(sc, z):
    layers = []
    if not sc:
        return layers
    t = sc[0]['t']
    while True:
        s, e = t, t + z['layer']
        nxt = next((c for c in sc if s + z['min_len'] <= c['t'] < e and c['score'] >= z['restart']), None)
        if nxt:
            e = nxt['t']
        layers.append({'t0': round(s, 3), 't1': round(e, 3), 'why': 'ends on jump' if nxt else ''})
        win = [c for c in sc if e + z['gap_min'] <= c['t'] <= e + z['gap_max']]
        if win:
            t = max(win, key=lambda c: c['score'])['t']
        else:
            after = [c for c in sc if c['t'] >= e + z['gap_min']]
            if not after:
                break
            t = after[0]['t']
    return layers


def plan_punch(clips, sc, z):
    """static punch-in toggled on visible cuts; contiguous same-take cuts (invisible) don't toggle."""
    vis = {c['t'] for c in sc if c['score'] >= z.get('punch_threshold', 2.5) or not c['same_take']}
    state, out = False, []
    for c in clips:
        if round(c['t0'], 3) in vis:
            state = not state
        if state:
            out.append({'t0': c['t0'], 't1': c['t1'], 'why': 'punch'})
    merged = []
    for l in out:
        if merged and abs(l['t0'] - merged[-1]['t1']) < 0.01:
            merged[-1]['t1'] = l['t1']
        else:
            merged.append(dict(l))
    return merged


def curve(z, l, t):
    """scale %, y offset (fraction of height) at timeline time t for ramp layer l"""
    if not (l['t0'] <= t < l['t1']):
        return 100.0, 0.0
    u = t - l['t0']
    peak = z['scale_in'] - 100
    if u < z['ease_in']:
        k = 1 - (1 - u / z['ease_in']) ** 3          # ease-out push-in
    else:
        k = max(0.0, 1 - (u - z['ease_in']) / max(0.01, z['layer'] - z['ease_in']))
    return 100 + peak * k, z['pos_y'] * k


def apply_keyframes(clips, layers, z):
    for c in clips:
        c.pop('fx', None)
    if z['style'] == 'punch':
        for c in clips:
            if any(l['t0'] - 1e-3 <= c['t0'] < l['t1'] for l in layers):
                c['fx'] = {'scale': [[0, float(z['punch_scale'])]]}
        return
    for c in clips:
        ls = [l for l in layers if l['t0'] < c['t1'] - 1e-3 and l['t1'] > c['t0'] + 1e-3]
        if not ls:
            continue
        pts = {c['t0'], c['t1'] - 1 / 1000}
        for l in ls:
            for f in (0, 0.25, 0.5, 0.75, 1):           # linear keyframes that follow the eased push-in
                pts.add(l['t0'] + f * z['ease_in'])
            pts.add(l['t1'] - 1 / 1000)                 # last frame of the layer, then straight back to wide
            pts.add(l['t1'])
        pts = sorted(p for p in pts if c['t0'] <= p < c['t1'])
        sc, ps = [], []
        for p in pts:
            l = next((l for l in ls if l['t0'] <= p < l['t1']), None)
            v, dy = curve(z, l, p) if l else (100.0, 0.0)
            sc.append([round(p - c['t0'], 3), round(v, 3)])
            ps.append([round(p - c['t0'], 3), 0.0, round(dy, 5)])
        if any(abs(v - 100) > 0.01 for _, v in sc):
            c['fx'] = {'scale': sc, 'pos': ps} if any(abs(p[2]) > 1e-5 for p in ps) else {'scale': sc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('timeline'); ap.add_argument('--profile'); ap.add_argument('--seq')
    ap.add_argument('--start-after', type=float); ap.add_argument('-o'); ap.add_argument('--xml'); ap.add_argument('--fcpxml')
    ap.add_argument('--scores-only', action='store_true'); ap.add_argument('--project', help='where _auto/ goes (default: next to the input)')
    a = ap.parse_args()
    prof = C.load_profile(a.profile)
    z = prof['zoom']
    if z['style'] == 'none':
        raise SystemExit('profile.zoom.style is "none" — this client has no punch-ins')
    tl = T.read_any(a.timeline, a.seq)
    dv = prof['tracks'].get('dialog_v', 'V1')
    clips = sorted([x for x in tl['items'] if x['trk'] == dv and x.get('kind', 'clip') == 'clip' and x.get('file')], key=lambda x: x['t0'])
    d = os.path.dirname(os.path.abspath(a.timeline))
    out = C.out_dir(a.project or (os.path.dirname(d) if os.path.basename(d) == '_auto' else d))
    sp = os.path.join(out, 'jump_scores.json')
    if os.path.exists(sp) and len(C.jload(sp)) == len(clips) - 1:
        sc = C.jload(sp)
    else:
        print(f'scoring {len(clips) - 1} cuts from the raws…', flush=True)
        sc = jump_scores(clips)
        C.jdump(sc, sp)
    s = np.array([c['score'] for c in sc]) if sc else np.zeros(1)
    print('cut visibility p25/50/75/90/97:', np.percentile(s, [25, 50, 75, 90, 97]).round(2).tolist())
    if a.scores_only:
        return
    start = a.start_after if a.start_after is not None else z.get('start_after', 0)
    sc = [c for c in sc if c['t'] >= start]
    layers = plan_ramp(sc, z) if z['style'] == 'ramp' else plan_punch([c for c in clips if c['t0'] >= start], sc, z)
    end_v = clips[-1]['t1'] if clips else 0
    for l in layers:
        l['t1'] = min(l['t1'], end_v)
    layers = [l for l in layers if l['t1'] - l['t0'] > 0.2]
    C.jdump(layers, os.path.join(out, 'zoom_plan.json'))
    dur = np.array([l['t1'] - l['t0'] for l in layers])
    gaps = np.array([b['t0'] - a['t1'] for a, b in zip(layers, layers[1:])])
    talk = end_v - start
    wide_jumps = [c for c in sc if c['score'] >= z['obvious'] and not any(l['t0'] - 0.01 <= c['t'] < l['t1'] for l in layers)]
    C.uprint(f'{len(layers)} zooms ({z["style"]}) | zoomed {dur.sum() / max(1, talk):.0%} of the talking head | '
             f'length p10/50 {np.percentile(dur, [10, 50]).round(2).tolist() if len(dur) else []} | wide gaps p25/50/75 '
             f'{np.percentile(gaps[gaps > 0.01], [25, 50, 75]).round(2).tolist() if (gaps > 0.01).any() else []} | '
             f'back-to-back {int((gaps < 0.01).sum())} | obvious jumps left in wide shots {len(wide_jumps)}')
    if z['method'] == 'keyframes':
        apply_keyframes(clips, layers, z)
        C.uprint(f'keyframed {sum(1 for c in clips if c.get("fx"))} dialog clips')
    else:
        zt = prof['tracks'].get('zoom', 'V3')
        tl['items'] = [x for x in tl['items'] if not (x['trk'] == zt and x.get('kind') == 'adjustment')]
        tl['items'] += [{'trk': zt, 'kind': 'adjustment', 't0': l['t0'], 't1': l['t1'], 's0': 0, 'file': None, 'name': 'zoom'} for l in layers]
        C.uprint(f'adjustment-layer plan on {zt}: place one layer at each start (references/nle/<nle>.md); first 5: ' +
                 ', '.join(C.tc(l['t0'], prof['fps']) for l in layers[:5]))
    o = a.o or os.path.join(out, 'zoomed.timeline.json')
    C.jdump(tl, o)
    if a.xml:
        T.write_xmeml(tl, a.xml)
    if a.fcpxml:
        T.write_fcpxml(tl, a.fcpxml)
    C.uprint('out:', o)


if __name__ == '__main__':
    main()
