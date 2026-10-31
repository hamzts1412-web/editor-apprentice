"""Multi-camera podcast: sync every camera and mic by their audio, then cut to whoever is talking.

  python multicam.py <project> --cam host=A.mp4 --cam guest=B.mp4 --cam wide=C.mp4 \
                     --mic host=host_mic.wav --mic guest=guest_mic.wav [--mic guest=recorder.wav:1] \
                     [--wide wide] [--profile <client>/profile.json] [--start SEC] [--end SEC] [--fcpxml]

  --cam  label=file           one per camera; the label of a speaker's close-up must equal that speaker's --mic label
  --mic  label=file[:channel] one per speaker (separate files, or channels of one multitrack recorder file)
  --wide label                the wide / two-shot camera (used for overlaps, laughs, and to break long monologues)
  --ref  file                 sync reference (default: the first mic)
Output: <project>/_auto/multicam.timeline.json + multicam.xml (V1 = the switched cameras, A1..An = every mic in sync),
        multicam_sync.json (offsets — check them), multicam_shots.tsv (each shot + why).
Rules come from profile.multicam (see DEFAULTS) — measure them on the client's finished episodes and confirm with the editor.
"""
import argparse, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import timeline as T

DEFAULTS = {
    'min_shot': 2.0,        # never cut away from a shot younger than this (s)
    'switch_delay': 0.4,    # the new speaker must hold the floor this long before we cut to them
    'lead': 0.15,           # cut lands this long before the new speaker's first word
    'margin_db': 6,         # a speaker "has the floor" when their mic is this much louder than the others
    'max_shot': 14.0,       # a single-speaker shot longer than this gets a cutaway…
    'cutaway': 'wide',      # …to the wide shot ('wide') or to the listener's close-up ('listener') or nothing ('none')
    'cutaway_len': 2.5,
    'overlap': 'wide',      # both talking -> wide shot ('wide') or stay ('stay')
}


def env100(path, channel=None):
    db = C.energy_db(path, channel=channel)
    return db


def find_offset(ref_db, db, max_lag_s=600):
    """offset (s) such that time_in_ref = time_in_file + offset (cross-correlation of 10 ms energy envelopes)."""
    a = np.clip(ref_db, -60, 0) + 60
    b = np.clip(db, -60, 0) + 60
    a = a - a.mean()
    b = b - b.mean()
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    xc = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    lags = np.concatenate([np.arange(0, len(a)), np.arange(-len(b) + 1, 0)])
    vals = np.concatenate([xc[:len(a)], xc[n - len(b) + 1:]])
    ok = np.abs(lags) <= max_lag_s * 100
    k = int(np.argmax(np.where(ok, vals, -np.inf)))
    peak = vals[k]
    conf = float(peak / (np.sqrt((a ** 2).sum() * (b ** 2).sum()) + 1e-9))
    return lags[k] / 100.0, conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('--cam', action='append', default=[]); ap.add_argument('--mic', action='append', default=[])
    ap.add_argument('--wide'); ap.add_argument('--ref'); ap.add_argument('--profile')
    ap.add_argument('--start', type=float, default=0); ap.add_argument('--end', type=float); ap.add_argument('--fcpxml', action='store_true')
    a = ap.parse_args()
    prof = C.load_profile(a.profile)
    R = dict(DEFAULTS, **(prof.get('multicam') or {}))
    out = C.out_dir(a.project)
    cams = dict(c.split('=', 1) for c in a.cam)
    mics = {}
    for m in a.mic:
        lab, spec = m.split('=', 1)
        ch = None
        if ':' in spec[2:]:
            spec, ch = spec.rsplit(':', 1)
            ch = int(ch)
        mics[lab] = (spec, ch)
    if not cams or not mics:
        raise SystemExit('need at least one --cam and one --mic')
    speakers = list(mics)
    ref_path, ref_ch = (a.ref, None) if a.ref else mics[speakers[0]]

    # ---------------- sync
    print('reading audio envelopes…', flush=True)
    ref_db = env100(ref_path, ref_ch)
    sync = {}
    for lab, (p, ch) in mics.items():
        db = env100(p, ch)
        off, conf = (0.0, 1.0) if (p, ch) == (ref_path, ref_ch) else find_offset(ref_db, db)
        sync['mic:' + lab] = {'file': p, 'channel': ch, 'offset': off, 'confidence': round(conf, 3), 'db': db}
    for lab, p in cams.items():
        db = env100(p)
        off, conf = find_offset(ref_db, db)
        sync['cam:' + lab] = {'file': p, 'offset': off, 'confidence': round(conf, 3), 'db': db}
    for k, v in sync.items():
        flag = '  <-- LOW: check by eye/ear (clap, slate)' if v['confidence'] < 0.3 else ''
        C.uprint(f'{k:16} offset {v["offset"]:+9.2f}s  confidence {v["confidence"]:.2f}  {os.path.basename(v["file"])}{flag}')
    C.jdump({k: {kk: vv for kk, vv in v.items() if kk != 'db'} for k, v in sync.items()}, os.path.join(out, 'multicam_sync.json'), indent=1)

    # ---------------- who has the floor, on the reference clock (10 ms frames)
    def on_ref(db, off):
        n = len(ref_db)
        res = np.full(n, -100.0)
        k0 = int(round(off * 100))
        lo, hi = max(0, k0), min(n, k0 + len(db))
        if hi > lo:
            res[lo:hi] = db[lo - k0:hi - k0]
        return res

    lv = {s: on_ref(sync['mic:' + s]['db'], sync['mic:' + s]['offset']) for s in speakers}
    lvl = {s: C.speech_level(sync['mic:' + s]['db']) for s in speakers}
    n = len(ref_db)
    t_end = min(n, int((a.end or n / 100) * 100))
    t_start = int(a.start * 100)
    sm = {s: np.convolve(lv[s], np.ones(30) / 30, mode='same') for s in speakers}   # 0.3 s smoothing
    active = {s: sm[s] > lvl[s] - 14 for s in speakers}
    floor = np.full(n, '', dtype=object)
    for k in range(t_start, t_end):
        act = [s for s in speakers if active[s][k]]
        if len(act) == 1:
            floor[k] = act[0]
        elif len(act) > 1:
            best = max(act, key=lambda s: sm[s][k] - lvl[s])
            others = max(sm[s][k] - lvl[s] for s in act if s != best)
            floor[k] = best if (sm[best][k] - lvl[best]) - others >= R['margin_db'] else 'both'

    wide = a.wide if a.wide in cams else None

    def cam_for(label):
        if label == 'both':
            return wide if R['overlap'] == 'wide' and wide else None
        return label if label in cams else wide

    shots, cur, cur_t, cand, cand_t = [], None, t_start, None, None
    for k in range(t_start, t_end):
        f = floor[k]
        if not f:
            continue
        cam = cam_for(f)
        if cam is None or cam == cur:
            cand = None
            continue
        if cand != cam:
            cand, cand_t = cam, k
        if (k - cand_t) / 100 >= R['switch_delay'] and (cur is None or (cand_t - cur_t) / 100 >= R['min_shot']):
            cut = max(cur_t + int(R['min_shot'] * 100) if cur else t_start, cand_t - int(R['lead'] * 100))
            if cur is not None:
                shots.append([cur, cur_t, cut, f'{cur} until {cam} takes over'])
            cur, cur_t, cand = cam, cut if cur is not None else t_start, None
    if cur is not None:
        shots.append([cur, cur_t, t_end, 'last'])

    # cutaways in long single-speaker shots
    final = []
    for cam, s, e, why in shots:
        L = (e - s) / 100
        alt = wide if R['cutaway'] == 'wide' else (next((c for c in cams if c in speakers and c != cam), None) if R['cutaway'] == 'listener' else None)
        if L > R['max_shot'] and alt and alt != cam:
            pieces = int(L // R['max_shot'])
            step = (e - s) / (pieces + 1)
            t = s
            for i in range(pieces):
                mid = int(s + step * (i + 1))
                final.append([cam, t, mid, why])
                ce = min(e, mid + int(R['cutaway_len'] * 100))
                final.append([alt, mid, ce, 'cutaway in a long shot'])
                t = ce
            final.append([cam, t, e, why])
        else:
            final.append([cam, s, e, why])

    # ---------------- timeline
    F = prof['fps']

    def fr(t):
        return round(t * F) / F

    items = []
    t0_ref = t_start / 100
    for i, (cam, s, e, why) in enumerate(final):
        off = sync['cam:' + cam]['offset']
        ts, te = fr(s / 100 - t0_ref), fr(e / 100 - t0_ref)
        if te - ts < 1 / F:
            continue
        items.append({'trk': 'V1', 'kind': 'clip', 't0': ts, 't1': te, 's0': fr(s / 100 - off), 'file': cams[cam], 'name': cam})
    end_t = fr((t_end - t_start) / 100)
    for j, s in enumerate(speakers):
        m = sync['mic:' + s]
        st = max(0.0, m['offset'] - t0_ref)
        s0 = max(0.0, t0_ref - m['offset'])
        dur = min(end_t - st, len(m['db']) / 100 - s0)
        if dur > 0:
            items.append({'trk': f'A{j + 1}', 'kind': 'audio', 't0': fr(st), 't1': fr(st + dur), 's0': fr(s0), 'file': m['file'], 'name': s})
    tl = {'name': os.path.basename(os.path.abspath(a.project)) + ' - multicam', 'fps': F, 'width': prof['width'], 'height': prof['height'],
          'items': items, 'markers': []}
    C.jdump(tl, os.path.join(out, 'multicam.timeline.json'))
    T.write_xmeml(tl, os.path.join(out, 'multicam.xml'))
    if a.fcpxml:
        T.write_fcpxml(tl, os.path.join(out, 'multicam.fcpxml'))
    with open(os.path.join(out, 'multicam_shots.tsv'), 'w', encoding='utf-8') as f:
        f.write('start\tend\tcamera\twhy\n')
        for cam, s, e, why in final:
            f.write(f'{C.tc(s / 100 - t0_ref)}\t{C.tc(e / 100 - t0_ref)}\t{cam}\t{why}\n')
    L = np.array([(e - s) / 100 for _, s, e, _ in final])
    from collections import Counter
    use = Counter()
    for cam, s, e, _ in final:
        use[cam] += (e - s) / 100
    C.uprint(f'{len(final)} shots | length p10/50/90 {np.percentile(L, [10, 50, 90]).round(1).tolist() if len(L) else []} s | screen time ' +
             ', '.join(f'{c} {v / max(1, sum(use.values())):.0%}' for c, v in use.most_common()))
    C.uprint('out:', out)


if __name__ == '__main__':
    main()
