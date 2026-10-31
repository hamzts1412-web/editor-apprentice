"""Transcribe raw footage with word timestamps, island by island.

The audio is split into speech islands (runs of sound between silences) and each island is transcribed on its own:
in isolation Whisper writes what was actually said — stutters, restarts and cut-off words — instead of smoothing
them away, which is exactly what a rough cut needs to see.

  python transcribe.py <media> [<media> ...] [--lang ar] [--model NAME] [--device cuda|cpu] [--channel K] [--force]
                       [--terms "Name1" "Product 2" …] [--profile profile.json] [--from s --to s]
  -> <media>.islands.json next to each file:
     {source, duration, language, speech_level, threshold, islands: [{s, e, peak, text, words: [{w, s, e, p}]}]}

--terms (or profile "terms": a list, or a {spelling: hint} map) biases Whisper towards names and foreign words the
talent uses — without it they are often dropped or misspelled, leaving blanks in sentences that list names.
--from/--to transcribes only that range (seconds) into <media>.<from>-<to>.islands.json: use it to re-check a range
before ever saying "there is no speech here".
At the end it lists islands where sound was clearly heard but no words came out — check those by ear or re-run them.
"""
import argparse, os, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C


def _cuda_dlls():
    # pip-installed CUDA libraries (nvidia-cublas-cu12 / nvidia-cudnn-cu12) are not on the DLL path on Windows
    if os.name != 'nt':
        return
    nv = os.path.join(os.path.dirname(np.__file__), '..', 'nvidia')
    for sub in ('cublas', 'cudnn', 'cuda_nvrtc'):
        b = os.path.abspath(os.path.join(nv, sub, 'bin'))
        if os.path.isdir(b):
            os.add_dll_directory(b)
            os.environ['PATH'] = b + os.pathsep + os.environ['PATH']


MIN_GAP = 0.15      # a silence shorter than this doesn't split an island
MIN_LEN = 0.10      # drop clicks
MAX_LEN = 25.0      # Whisper window; longer islands split at their quietest point
PAD = 0.10


def find_islands(db, sil):
    runs, st = [], None
    for k, s in enumerate(sil):
        if not s and st is None:
            st = k
        elif s and st is not None:
            runs.append([st, k])
            st = None
    if st is not None:
        runs.append([st, len(sil)])
    merged = []
    for r in runs:
        if merged and (r[0] - merged[-1][1]) / 100 < MIN_GAP:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    out = []
    for a, b in merged:
        if (b - a) / 100 < MIN_LEN:
            continue
        stack = [(a, b)]
        while stack:
            a, b = stack.pop()
            if (b - a) / 100 <= MAX_LEN:
                out.append((a, b))
                continue
            mid = a + 200 + int(np.argmin(db[a + 200:b - 200]))
            stack += [(mid, b), (a, mid)]
    return sorted(out)


def pick_device(dev):
    if dev:
        return dev
    try:
        import ctranslate2
        return 'cuda' if ctranslate2.get_cuda_device_count() > 0 else 'cpu'
    except Exception:
        return 'cpu'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('media', nargs='+')
    ap.add_argument('--lang', help='ISO language code; default: profile / auto-detect')
    ap.add_argument('--profile', help="client profile.json (for the language)")
    ap.add_argument('--model', default='mobiuslabsgmbh/faster-whisper-large-v3-turbo')
    ap.add_argument('--device')
    ap.add_argument('--channel', type=int, help='transcribe one channel of a multi-mic file')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--terms', nargs='+', help='names / foreign words the talent says (spelling as wanted)')
    ap.add_argument('--from', dest='t_from', type=float)
    ap.add_argument('--to', dest='t_to', type=float)
    a = ap.parse_args()
    prof = C.load_profile(a.profile)
    lang = a.lang or prof.get('language')
    terms = list(a.terms or [])
    pt = prof.get('terms') or []
    terms += list(pt.keys()) if isinstance(pt, dict) else list(pt)
    hotwords = ' '.join(dict.fromkeys(terms)) or None
    dev = pick_device(a.device)
    if dev == 'cuda':
        _cuda_dlls()
    from faster_whisper import WhisperModel, BatchedInferencePipeline
    model = WhisperModel(a.model, device=dev, compute_type='float16' if dev == 'cuda' else 'int8')
    batched = BatchedInferencePipeline(model=model)
    print(f'model {a.model} on {dev}', flush=True)
    for src in a.media:
        rng = f'.{a.t_from or 0:g}-{a.t_to:g}' if a.t_to else (f'.{a.t_from:g}-end' if a.t_from else '')
        out = os.path.splitext(src)[0] + (f'.c{a.channel}' if a.channel is not None else '') + rng + '.islands.json'
        if os.path.exists(out) and not a.force:
            print('skip (exists)', out, flush=True)
            continue
        t0 = time.time()
        wav = C.extract_wav(src, channel=a.channel)
        audio = C.read_wav(wav)
        db = C.energy_db(src, channel=a.channel)
        sil, lvl = C.silence_mask(db)
        isl = find_islands(db, sil)
        if a.t_from or a.t_to:
            lo, hi = (a.t_from or 0) * 100, (a.t_to or 1e9) * 100
            isl = [(max(x, int(lo)), min(y, int(hi))) for x, y in isl if y > lo and x < hi]
        dur = len(audio) / 16000
        clips = []
        for x, y in isl:   # padded, but never overlapping (continuous audio — music beds, finals — splits into touching islands)
            st = max(0, x / 100 - PAD, clips[-1]['end'] if clips else 0)
            en = min(dur, y / 100 + PAD)
            if en - st > 0.05:
                clips.append({'start': st, 'end': en})
        print(f'{os.path.basename(src)}: {dur / 60:.1f} min, {len(isl)} speech islands', flush=True)
        if not isl:
            C.jdump({'source': os.path.abspath(src), 'duration': dur, 'language': lang, 'speech_level': lvl,
                     'threshold': lvl - 22, 'islands': []}, out)
            continue
        segs, info = batched.transcribe(audio, language=lang, word_timestamps=True, beam_size=5, clip_timestamps=clips,
                                        batch_size=16 if dev == 'cuda' else 4, condition_on_previous_text=False,
                                        without_timestamps=False, hotwords=hotwords)
        used_lang = lang or info.language
        hall = C.HALLUCINATIONS.get(used_lang, [])
        res = [{'s': x / 100, 'e': y / 100, 'peak': float(np.percentile(db[x:y], 90)), 'words': [], 'text': ''} for x, y in isl]
        k = 0
        for s in segs:
            mid = (s.start + s.end) / 2
            while k + 1 < len(res) and res[k]['e'] + PAD < mid:
                k += 1
            low = s.text.casefold()
            if any(h in low for h in hall) or (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0):
                continue
            r = res[k]
            r['text'] = (r['text'] + ' ' + s.text.strip()).strip()
            r['words'] += [{'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3), 'p': round(w.probability, 3)}
                           for w in (s.words or []) if w.word.strip()]
            if k % 200 == 0:
                C.uprint(f'  {r["s"]:8.1f}s  {r["text"][:60]}', flush=True)
        C.jdump({'source': os.path.abspath(src), 'duration': dur, 'language': used_lang, 'speech_level': lvl,
                 'threshold': lvl - 22, 'islands': res}, out)
        print(f'done {out} in {time.time() - t0:.0f}s', flush=True)
        # loud enough to be speech, long enough to be words, but nothing came out → don't trust the silence
        mute = [r for r in res if not r['words'] and r['e'] - r['s'] >= 0.6 and r['peak'] >= lvl - 10]
        if mute:
            print(f'  {len(mute)} islands with sound but no words (check by ear, or re-run with --from/--to):', flush=True)
            for r in mute[:30]:
                print(f'    {C.tc(r["s"])} – {C.tc(r["e"])}', flush=True)


if __name__ == '__main__':
    main()
