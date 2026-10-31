"""Measure the style of a PUBLISHED video file (a client's reference episode) when no project file exists.

  python measure_video.py <video> [--minutes 15] [--start SEC] [-o style.json]

Reports: shot/cut rhythm (cuts per minute, shot length), punch-ins at cuts and slow zooms inside shots (scale estimated
from matched features between frames), how much is talking head (a face fills the frame) vs b-roll/graphics, the pauses
the editor leaves in speech, and loudness (LUFS). The first 10–15 minutes are usually enough.
Only measure videos the editor provided or approved downloading.
"""
import argparse, os, re, subprocess, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C


def scale_between(orb, bf, a, b):
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None or len(ka) < 20 or len(kb) < 20:
        return None, 0
    import cv2
    m = bf.match(da, db)
    if len(m) < 20:
        return None, 0
    pa = np.float32([ka[x.queryIdx].pt for x in m])
    pb = np.float32([kb[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=3)
    if M is None:
        return None, 0
    s = float(np.sqrt(M[0, 0] ** 2 + M[1, 0] ** 2))
    return s, int(inl.sum()) if inl is not None else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video'); ap.add_argument('--minutes', type=float, default=15); ap.add_argument('--start', type=float, default=0)
    ap.add_argument('-o')
    a = ap.parse_args()
    import cv2
    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    cap.set(cv2.CAP_PROP_POS_MSEC, a.start * 1000)
    n_max = int(a.minutes * 60 * fps)
    orb = cv2.ORB_create(600)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    # pass 1: tiny frames -> cut positions
    prev_s = None
    diffs = []
    while len(diffs) < n_max:
        ok, f = cap.read()
        if not ok:
            break
        s = cv2.cvtColor(cv2.resize(f, (64, 36), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
        diffs.append(float(np.mean(np.abs(s - prev_s))) if prev_s is not None else 0.0)
        prev_s = s
        if len(diffs) % int(fps * 120) == 0:
            print(f'  pass 1: {len(diffs) / fps / 60:.0f} min', flush=True)
    N = len(diffs)
    d = np.array(diffs)
    med = np.median(d[d > 0]) if (d > 0).any() else 1
    cut_thr = max(10.0, 6 * med)
    raw_cuts = [i for i in range(1, N) if d[i] > cut_thr and d[i] >= d[max(0, i - 2):i + 3].max()]
    # several "cuts" within half a second = one animated transition / flash / graphic pop, not a shot change
    cuts, flashes, grp = [], 0, []
    for i in raw_cuts + [10 ** 9]:
        if grp and i - grp[-1] > fps * 0.5:
            if len(grp) == 1:
                cuts.append(grp[0])
            else:
                flashes += 1
                cuts.append(grp[-1])
            grp = []
        grp.append(i)
    cuts = [c for c in cuts if c < N]
    bounds = [0] + cuts + [N]
    # pass 2: grab only the frames we need (around cuts, and two per shot for slow zoom + face check)
    need = set()
    for i in cuts:
        need |= {i - 2, i + 1}
    shots = []
    for s0, s1 in zip(bounds, bounds[1:]):
        a0, a1 = s0 + 2, min(s1 - 3, s0 + int(fps * 1.5))
        shots.append((s0, s1, a0, a1))
        need |= {a0, a1}
    sec_idx = list(range(0, N, max(1, int(round(fps)))))   # one frame per second for the layout (camera vs screen)
    need |= set(sec_idx)
    cap.set(cv2.CAP_PROP_POS_MSEC, a.start * 1000)
    frames = {}
    for k in range(N):
        ok, f = cap.read()
        if not ok:
            break
        if k in need:
            frames[k] = cv2.cvtColor(cv2.resize(f, (320, 180), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    punch, jumpcut = [], 0
    for i in cuts:
        fa, fb = frames.get(i - 2), frames.get(i + 1)
        if fa is None or fb is None:
            continue
        sc, inl = scale_between(orb, bf, fa, fb)
        if sc and inl >= 25:
            jumpcut += 1                      # same shot both sides of the cut
            if abs(sc - 1) >= 0.05:
                punch.append(round(sc, 3))
    slow, thumbs, lens = [], [], []
    for s0, s1, a0, a1 in shots:
        lens.append((s1 - s0) / fps)
        probe = frames.get(a1 if a1 > a0 else a0)
        if probe is not None:
            t = cv2.resize(cv2.GaussianBlur(probe, (9, 9), 0), (16, 9), interpolation=cv2.INTER_AREA).astype(np.float32)
            thumbs.append((t - t.mean()) / (t.std() + 1e-6))
        else:
            thumbs.append(None)
        if lens[-1] >= 2.0 and a1 - a0 >= fps * 0.8 and a0 in frames and a1 in frames:
            sc, inl = scale_between(orb, bf, frames[a0], frames[a1])
            if sc and inl >= 30 and abs(sc - 1) >= 0.015:
                slow.append(round((sc - 1) / ((a1 - a0) / fps), 4))
    # talking head = the camera setup(s) that keep coming back: shots that look like shots filling >= 20 % of the time
    tot_len = sum(lens)
    shot_info = []
    for i, ti in enumerate(thumbs):
        w = sum(lens[j] for j, tj in enumerate(thumbs) if ti is not None and tj is not None and np.mean(np.abs(ti - tj)) < 0.45)
        shot_info.append((lens[i], w >= 0.2 * tot_len))
    # layout: a screen recording (UI, code, pages) is mostly flat 8x8 blocks; a camera image almost never is
    flat = []
    for k in sec_idx:
        g = frames.get(k)
        if g is not None:
            b = g[:176].astype(np.float32).reshape(22, 8, 40, 8).std(axis=(1, 3))
            flat.append(float((b < 2.0).mean()))
    screen = np.array(flat) >= 0.18
    runs, cur, ln = [], None, 0
    for s in screen:
        if s == cur:
            ln += 1
        else:
            if cur is not None:
                runs.append((bool(cur), ln))
            cur, ln = s, 1
    if cur is not None:
        runs.append((bool(cur), ln))
    runs = [r for r in runs if r[1] >= 2] or runs     # ignore 1 s flickers (transitions, pops)
    cam_runs = [l for s, l in runs if not s]
    scr_runs = [l for s, l in runs if s]
    L = np.array([x[0] for x in shot_info])
    th = sum(x[0] for x in shot_info if x[1])
    tot = N / fps
    R = [f'# Published video — {os.path.basename(a.video)} ({tot / 60:.1f} min analysed from {C.mmss(a.start)}, {fps:.2f} fps)',
         f'- {len(cuts)} visible cuts = {len(cuts) / (tot / 60):.1f}/min ({flashes} of them animated transitions/flashes), '
         f'shot length p10/50/90 {np.percentile(L, [10, 50, 90]).round(2).tolist()} s — invisible jump cuts (same frame) are not counted',
         f'- {jumpcut} cuts are jump cuts (same shot both sides); {len(punch)} of them change scale (punch-in/out): '
         f'ratios p10/50/90 {np.percentile(punch, [10, 50, 90]).round(3).tolist() if punch else []}',
         f'- slow zoom inside shots: {sum(1 for v in slow if v > 0)} zooming in, {sum(1 for v in slow if v < 0)} out; speed p50 '
         f'{np.median(np.abs(slow)) * 100 if slow else 0:.2f} %/s',
         f'- main camera setup(s) (talking head, recurring look) ≈ {th / tot:.0%} of the time; other shots (b-roll/graphics/screens) '
         f'≈ {1 - th / tot:.0%} — rough: overlays on the talking head count as talking head',
         f'- layout: screen recording on screen ≈ {screen.mean():.0%} of the time (camera full-frame ≈ {1 - screen.mean():.0%}); '
         f'{len(runs) - 1} switches = {(len(runs) - 1) / (tot / 60):.1f}/min; camera stretches p50/max '
         f'{[float(np.median(cam_runs)), max(cam_runs)] if cam_runs else []} s, screen stretches p50/max '
         f'{[float(np.median(scr_runs)), max(scr_runs)] if scr_runs else []} s; opens on '
         f'{"screen" if runs and runs[0][0] else "camera"} for {runs[0][1] if runs else 0} s']
    # audio: pauses + loudness
    try:
        db = C.energy_db(a.video)
        seg = db[int(a.start * 100):int((a.start + tot) * 100)]
        lvl = C.speech_level(seg)
        sil = seg < lvl - 22
        runs, run = [], 0
        for s in sil:
            if s:
                run += 1
            elif run:
                if run >= 8:
                    runs.append(run / 100)
                run = 0
        r = np.array(runs)
        R.append(f'- pauses in the speech ≥ 0.08 s: {len(r)} ({len(r) / (tot / 60):.0f}/min), p50/90/max '
                 f'{[round(float(np.median(r)), 2), round(float(np.percentile(r, 90)), 2), round(float(r.max()), 2)] if len(r) else []} s')
        p = subprocess.run([C.ffmpeg(), '-hide_banner', '-nostats', '-ss', str(a.start), '-t', str(tot), '-i', a.video, '-vn',
                            '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        m = re.findall(r'I:\s+(-?[\d.]+) LUFS', p.stderr)
        if m:
            R.append(f'- loudness {m[-1]} LUFS integrated')
    except Exception as e:
        R.append(f'- audio not analysed ({e})')
    C.uprint('\n'.join(R))
    if a.o:
        C.jdump({'report': R, 'cuts_per_min': len(cuts) / (tot / 60), 'shot_p50': float(np.median(L)), 'punch_ratios': punch,
                 'talking_head_share': th / tot}, a.o, indent=1)


if __name__ == '__main__':
    main()
