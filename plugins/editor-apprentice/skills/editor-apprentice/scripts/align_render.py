"""Recover the cut of a RENDERED final (no project file) by matching its audio against the raw audio.

  python align_render.py <final video> <raw audio/video> [--minutes 10] [--start 0] [-o final.timeline.json]

Slides 1 s pieces of the final's audio along the raw recording (10 ms energy envelopes, normalised cross-correlation,
searching forward from the last match) and joins pieces with the same offset into kept ranges. The result is a timeline
(A1 = the raw file with the kept source ranges) that final_diff.py can compare with our cut. Music/SFX in the final lower
the match score of a piece; pieces below --min-score are left out (reported as unmatched time).
"""
import argparse, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C


def feat(db):
    x = np.clip(db, -70, 0) + 70
    return x.astype(np.float32)


def best_match(piece, raw, lo, hi):
    """normalised cross-correlation of piece over raw[lo:hi]; returns (index, score)"""
    seg = raw[lo:hi + len(piece)]
    if len(seg) < len(piece) or len(piece) < 10:
        return None, 0.0
    p = piece - piece.mean()
    pn = np.sqrt((p ** 2).sum()) + 1e-6
    n = len(p)
    c = np.convolve(seg, p[::-1], mode='valid')                       # sum(seg_window * p)
    s1 = np.convolve(seg, np.ones(n), mode='valid')
    s2 = np.convolve(seg ** 2, np.ones(n), mode='valid')
    var = np.maximum(s2 - s1 ** 2 / n, 1e-6)
    score = c / (np.sqrt(var) * pn)
    k = int(np.argmax(score))
    return lo + k, float(score[k])


def by_words(final_isl, raw_isl, raw_file, raw_range=None):
    """Align the final's words to the raw words (robust to processed audio, music beds, loudness changes).
    Returns kept ranges as timeline items (word-level precision, ~0.1 s)."""
    import difflib
    F = [w for i in C.jload(final_isl)['islands'] for w in i['words']]
    Rd = C.jload(raw_isl)
    R = [w for i in Rd['islands'] for w in i['words']]
    if raw_range:
        R = [w for w in R if raw_range[0] <= w['s'] < raw_range[1]]
    ft = [C.tok(w['w']) for w in F]
    rt = [C.tok(w['w']) for w in R]
    sm = difflib.SequenceMatcher(None, ft, rt, autojunk=False)
    pairs = []
    for b in sm.get_matching_blocks():
        if b.size >= 2:   # single-word matches are too often accidental
            pairs += [(F[b.a + k], R[b.b + k]) for k in range(b.size)]
    ranges = []
    for fw, rw in pairs:
        off = fw['s'] - rw['s']
        # same offset as the previous range = the material between them plays on in the final, even where the two
        # transcripts spelled the words differently (tech terms, names) and nothing matched
        if ranges and abs(ranges[-1]['off'] - off) < 0.35:
            ranges[-1]['f1'] = fw['e']
            ranges[-1]['r1'] = rw['e']
            ranges[-1]['n'] += 1
        else:
            ranges.append({'off': off, 'f0': fw['s'], 'f1': fw['e'], 'r0': rw['s'], 'r1': rw['e'], 'n': 1})
    items = [{'trk': 'A1', 'kind': 'audio', 't0': r['f0'], 't1': r['f0'] + (r['r1'] - r['r0']), 's0': r['r0'],
              'file': os.path.abspath(raw_file), 'name': os.path.basename(raw_file), 'words': r['n']} for r in ranges if r['n'] >= 2]
    return items, len(F), sum(r['n'] for r in ranges)


def logmel(path, n_mels=40):
    """log-mel spectrogram, 10 ms hop, 16 kHz mono -> (frames, n_mels), each frame standardised"""
    a = C.read_wav(C.extract_wav(path))
    n_fft, hop = 512, 160
    win = np.hanning(n_fft).astype(np.float32)
    freqs = np.linspace(0, 8000, n_fft // 2 + 1)
    mel = lambda f: 2595 * np.log10(1 + f / 700)
    edges = 700 * (10 ** (np.linspace(mel(60), mel(7600), n_mels + 2) / 2595) - 1)
    fb = np.zeros((n_mels, len(freqs)), np.float32)
    for m in range(n_mels):
        l, c, r = edges[m:m + 3]
        fb[m] = np.clip(np.minimum((freqs - l) / (c - l), (r - freqs) / (r - c)), 0, None)
    n = max(0, (len(a) - n_fft) // hop + 1)
    out = np.empty((n, n_mels), np.float32)
    for s in range(0, n, 20000):
        e = min(n, s + 20000)
        idx = np.arange(s, e)[:, None] * hop + np.arange(n_fft)[None, :]
        spec = np.abs(np.fft.rfft(a[idx] * win, axis=1)) ** 2
        out[s:e] = np.log(spec @ fb.T + 1e-8)
    out -= out.mean(axis=1, keepdims=True)
    out /= out.std(axis=1, keepdims=True) + 1e-6
    return out


def hybrid(final, raw, final_isl, raw_isl, raw_range=None, f_range=None):
    """Word anchors give candidate offsets; log-mel matching picks the offset of every 0.5 s of the final and puts the
    cut points on the right 10 ms frame. Robust to processed audio and to transcripts that spell words differently."""
    import difflib
    from numpy.lib.stride_tricks import sliding_window_view
    F = [w for i in C.jload(final_isl)['islands'] for w in i['words']]
    R = [w for i in C.jload(raw_isl)['islands'] for w in i['words']]
    if raw_range:
        R = [w for w in R if raw_range[0] <= w['s'] < raw_range[1]]
    sm = difflib.SequenceMatcher(None, [C.tok(w['w']) for w in F], [C.tok(w['w']) for w in R], autojunk=False)
    anchors = []   # (final time, offset = final - raw)
    for b in sm.get_matching_blocks():
        if b.size >= 3:
            anchors += [(F[b.a + k]['s'], F[b.a + k]['s'] - R[b.b + k]['s']) for k in range(b.size)]
    if not anchors:
        return []
    fm, rm = logmel(final), logmel(raw)
    lo_f = int((f_range[0] if f_range else 0) * 100)
    hi_f = min(len(fm), int(f_range[1] * 100)) if f_range else len(fm)
    W, H, SPAN = 50, 25, 30          # 0.5 s pieces every 0.25 s; refine ±0.3 s around each candidate
    at = np.array([x[0] for x in anchors])
    ao = np.array([x[1] for x in anchors])
    piece_off = []
    for k in range(lo_f, hi_f - W, H):
        t = k / 100
        near = ao[np.abs(at - t) < 40]
        if not len(near):
            continue
        P = fm[k:k + W].ravel()
        best = (-1, None)
        for off in np.unique(np.round(near, 1)):
            j0 = int(round((t - off) * 100)) - SPAN
            j0 = max(0, j0)
            j1 = min(len(rm) - W, j0 + 2 * SPAN)
            if j1 <= j0:
                continue
            win = sliding_window_view(rm[j0:j1 + W], (W, rm.shape[1]))[:, 0].reshape(-1, W * rm.shape[1])
            sc = win @ P / (W * rm.shape[1])
            i = int(np.argmax(sc))
            if sc[i] > best[0]:
                best = (float(sc[i]), k - (j0 + i))
        if best[1] is not None and best[0] > 0.45:     # music/SFX-only pieces stay unmatched
            piece_off.append((k, best[1], best[0]))
    # runs of the same offset (±2 frames) = kept ranges; boundaries refined frame by frame
    runs = []
    for k, off, sc in piece_off:
        if runs and abs(runs[-1]['off'] - off) <= 2 and k - runs[-1]['k1'] <= 2 * H:
            runs[-1]['k1'] = k + W
            runs[-1]['n'] += 1
        else:
            runs.append({'off': off, 'k0': k, 'k1': k + W, 'n': 1})
    runs = [r for r in runs if r['n'] >= 2]

    def sim(k, off):
        j = k - off
        return float(fm[k] @ rm[j]) / fm.shape[1] if 0 <= j < len(rm) else -1.0

    for a, b in zip(runs, runs[1:]):
        if b['k0'] - a['k1'] > 2 * W:       # a real gap (unmatched music/graphics) — leave both edges as they are
            continue
        lo, hi = min(a['k1'], b['k0']) - W, max(a['k1'], b['k0']) + W
        sa = np.array([sim(k, a['off']) for k in range(lo, hi)])
        sb = np.array([sim(k, b['off']) for k in range(lo, hi)])
        score = np.concatenate([[0], np.cumsum(sa)]) + np.concatenate([np.cumsum(sb[::-1])[::-1], [0]])
        cut = lo + int(np.argmax(score))
        a['k1'], b['k0'] = cut, cut
    items = []
    for r in runs:
        if r['k1'] - r['k0'] < 10:
            continue
        s0 = (r['k0'] - r['off']) / 100
        if raw_range and not (raw_range[0] - 1 <= s0 <= raw_range[1]):
            continue
        items.append({'trk': 'A1', 'kind': 'audio', 't0': r['k0'] / 100, 't1': r['k1'] / 100, 's0': s0,
                      'file': os.path.abspath(raw), 'name': os.path.basename(raw), 'pieces': r['n']})
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('final'); ap.add_argument('raw')
    ap.add_argument('--hybrid', nargs=2, metavar=('FINAL_ISLANDS', 'RAW_ISLANDS'),
                    help='best method when transcripts exist: word anchors + log-mel matching (frame-accurate cuts)')
    ap.add_argument('--words', nargs=2, metavar=('FINAL_ISLANDS', 'RAW_ISLANDS'),
                    help='align by transcribed words instead of audio envelopes (use for processed/music-bed finals)')
    ap.add_argument('--raw-range', help='"start-end" seconds of the raw to consider (when only part of it was cut)')
    ap.add_argument('--minutes', type=float, default=0, help='only the first N minutes of the final (0 = all)')
    ap.add_argument('--start', type=float, default=0)
    ap.add_argument('--min-score', type=float, default=0.6)
    ap.add_argument('-o')
    a = ap.parse_args()
    if a.hybrid:
        rr = tuple(float(x) for x in a.raw_range.split('-')) if a.raw_range else None
        fr_ = (a.start, a.start + a.minutes * 60) if a.minutes else None
        items = hybrid(a.final, a.raw, a.hybrid[0], a.hybrid[1], rr, fr_)
        cov = sum(x['t1'] - x['t0'] for x in items)
        C.uprint(f'{len(items)} kept ranges, {cov / 60:.1f} min of the final matched to the raw')
        for x in items[:15]:
            C.uprint(f"  final {C.mmss(x['t0'])}-{C.mmss(x['t1'])}  <- raw {C.mmss(x['s0'])}-{C.mmss(x['s0'] + x['t1'] - x['t0'])}")
        C.jdump({'name': os.path.basename(a.final) + ' (recovered)', 'fps': 30, 'items': items, 'markers': []},
                a.o or os.path.splitext(a.final)[0] + '.recovered.timeline.json')
        return
    if a.words:
        rr = tuple(float(x) for x in a.raw_range.split('-')) if a.raw_range else None
        items, nf, nm = by_words(a.words[0], a.words[1], a.raw, rr)
        if rr:   # drop the final's time that maps outside the raw range
            items = [x for x in items if rr[0] <= x['s0'] < rr[1]]
        C.uprint(f'{len(items)} kept ranges; {nm}/{nf} words of the final matched to the raw')
        for x in items[:15]:
            C.uprint(f"  final {C.mmss(x['t0'])}-{C.mmss(x['t1'])}  <- raw {C.mmss(x['s0'])}-{C.mmss(x['s0'] + x['t1'] - x['t0'])}  ({x['words']} words)")
        C.jdump({'name': os.path.basename(a.final) + ' (recovered by words)', 'fps': 30, 'items': items, 'markers': []},
                a.o or os.path.splitext(a.final)[0] + '.recovered.timeline.json')
        return
    fdb, rdb = feat(C.energy_db(a.final)), feat(C.energy_db(a.raw))
    f0 = int(a.start * 100)
    f1 = len(fdb) if not a.minutes else min(len(fdb), f0 + int(a.minutes * 6000))
    W, H = 100, 50                               # 1 s pieces every 0.5 s
    pos, matches = None, []
    for k in range(f0, f1 - W, H):
        piece = fdb[k:k + W]
        if piece.std() < 2:                       # silence: nothing to match
            continue
        if pos is None:
            lo, hi = 0, len(rdb) - W
        else:
            lo, hi = max(0, pos - 500), min(len(rdb) - W, pos + 30000)   # back 5 s, forward 5 min
        j, sc = best_match(piece, rdb, lo, hi)
        if j is None:
            continue
        if sc < a.min_score and pos is not None:  # retry over the whole raw (an out-of-order piece)
            j2, sc2 = best_match(piece, rdb, 0, len(rdb) - W)
            if sc2 > sc:
                j, sc = j2, sc2
        if sc >= a.min_score:
            matches.append((k, j, sc))
            pos = j
    # join pieces with the same offset (final - raw) into kept ranges, then refine edges at 10 ms
    ranges = []
    for k, j, sc in matches:
        off = k - j
        if ranges and abs(ranges[-1]['off'] - off) <= 2 and k - ranges[-1]['f1'] <= H + W:
            ranges[-1]['f1'] = k + W
            ranges[-1]['n'] += 1
        else:
            ranges.append({'off': off, 'f0': k, 'f1': k + W, 'n': 1})
    for i, r in enumerate(ranges):   # grow each range while the envelopes keep agreeing
        nxt = ranges[i + 1]['f0'] if i + 1 < len(ranges) else f1
        prv = ranges[i - 1]['f1'] if i else f0
        while r['f1'] < nxt and 0 <= r['f1'] - r['off'] < len(rdb) and abs(fdb[r['f1']] - rdb[r['f1'] - r['off']]) < 6:
            r['f1'] += 1
        while r['f0'] > prv and 0 <= r['f0'] - 1 - r['off'] < len(rdb) and abs(fdb[r['f0'] - 1] - rdb[r['f0'] - 1 - r['off']]) < 6:
            r['f0'] -= 1
    items = []
    for i, r in enumerate(ranges):
        t0, t1 = r['f0'] / 100, r['f1'] / 100
        items.append({'trk': 'A1', 'kind': 'audio', 't0': t0, 't1': t1, 's0': (r['f0'] - r['off']) / 100,
                      'file': os.path.abspath(a.raw), 'name': os.path.basename(a.raw), 'score_pieces': r['n']})
    covered = sum(x['t1'] - x['t0'] for x in items)
    span = (f1 - f0) / 100
    C.uprint(f'{len(items)} kept ranges recovered over {span / 60:.1f} min of the final; matched {covered / span:.0%} of it '
             f'(the rest = silence, music/SFX-only parts, or material not from this raw)')
    for x in items[:12]:
        C.uprint(f"  final {C.mmss(x['t0'])}-{C.mmss(x['t1'])}  <- raw {C.mmss(x['s0'])}-{C.mmss(x['s0'] + x['t1'] - x['t0'])}")
    tl = {'name': os.path.basename(a.final) + ' (recovered)', 'fps': 30, 'items': items, 'markers': []}
    C.jdump(tl, a.o or os.path.splitext(a.final)[0] + '.recovered.timeline.json')


if __name__ == '__main__':
    main()
