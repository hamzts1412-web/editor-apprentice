"""The words of the cut, in timeline time — for reading the edit, anchoring graphics and making captions.

  python words.py <project> [--timeline <prproj|xml|fcpxml|timeline.json>] [--seq NAME] [--dialog A1]
                  [--srt out.srt] [--from SEC] [--to SEC] [--max-chars 32] [--max-dur 3.0]

Maps every transcribed source word (<project>/*.islands.json) through the dialog clips of the timeline (the current one,
after any hand edits) -> _auto/cut_words.json [{w, s, e, src}] and _auto/cut_text.txt (one line per phrase with m:ss —
the thing to read before planning graphics). --srt writes captions for a range (hooks / shorts).
"""
import argparse, glob, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import timeline as T


def map_words(tl, project, dialog=None):
    src_words = {}
    for p in glob.glob(os.path.join(project, '*.islands.json')):
        d = C.jload(p)
        src_words[os.path.normcase(os.path.abspath(d['source']))] = [w for i in d['islands'] for w in i['words']]
        src_words.setdefault(os.path.basename(d['source']).lower(), src_words[os.path.normcase(os.path.abspath(d['source']))])
    items = tl['items']
    dlg = dialog or next((t for t in ('A1',) if any(x['trk'] == t for x in items)), 'A1')
    clips = sorted([x for x in items if x['trk'] == dlg and x.get('file')], key=lambda x: x['t0'])
    out = []
    for c in clips:
        ws = src_words.get(os.path.normcase(os.path.abspath(c['file']))) or src_words.get(os.path.basename(c['file']).lower()) or []
        s0, s1 = c['s0'], c['s0'] + c['t1'] - c['t0']
        for w in ws:
            mid = (w['s'] + w['e']) / 2
            if s0 <= mid < s1:
                out.append({'w': w['w'], 's': round(c['t0'] + max(0, w['s'] - s0), 3), 'e': round(c['t0'] + min(w['e'], s1) - s0, 3),
                            'src': f"{os.path.basename(c['file'])}@{w['s']:.2f}"})
    return out


def lines(words, gap=0.5, max_words=14):
    cur, res = [], []
    for w in words:
        if cur and (w['s'] - cur[-1]['e'] > gap or len(cur) >= max_words):
            res.append(cur)
            cur = []
        cur.append(w)
    if cur:
        res.append(cur)
    return res


def srt(words, path, max_chars=32, max_dur=3.0):
    caps, cur = [], []
    for w in words:
        txt = ' '.join(x['w'] for x in cur + [w])
        if cur and (len(txt) > max_chars or w['e'] - cur[0]['s'] > max_dur or w['s'] - cur[-1]['e'] > 0.6):
            caps.append(cur)
            cur = []
        cur.append(w)
    if cur:
        caps.append(cur)

    def ts(t):
        return f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round((t - int(t)) * 1000)) % 1000:03d}'

    with open(path, 'w', encoding='utf-8') as f:
        for i, c in enumerate(caps):
            end = min(c[-1]['e'], caps[i + 1][0]['s']) if i + 1 < len(caps) else c[-1]['e']
            f.write(f"{i + 1}\n{ts(c[0]['s'])} --> {ts(end)}\n{' '.join(x['w'] for x in c)}\n\n")
    return len(caps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('--timeline'); ap.add_argument('--seq'); ap.add_argument('--dialog')
    ap.add_argument('--srt'); ap.add_argument('--from', dest='frm', type=float, default=0); ap.add_argument('--to', type=float)
    ap.add_argument('--max-chars', type=int, default=32); ap.add_argument('--max-dur', type=float, default=3.0)
    a = ap.parse_args()
    out = C.out_dir(a.project)
    tlp = a.timeline or os.path.join(out, 'roughcut.timeline.json')
    tl = T.read_any(tlp, a.seq)
    words = map_words(tl, a.project, a.dialog)
    C.jdump(words, os.path.join(out, 'cut_words.json'))
    with open(os.path.join(out, 'cut_text.txt'), 'w', encoding='utf-8') as f:
        for ln in lines(words):
            f.write(f"{C.mmss(ln[0]['s'])}  {' '.join(w['w'] for w in ln)}\n")
    C.uprint(f'{len(words)} words -> _auto/cut_words.json, _auto/cut_text.txt')
    if a.srt:
        sel = [w for w in words if w['s'] >= a.frm and (a.to is None or w['e'] <= a.to)]
        n = srt(sel, a.srt, a.max_chars, a.max_dur)
        C.uprint(f'{n} captions -> {a.srt}')


if __name__ == '__main__':
    main()
