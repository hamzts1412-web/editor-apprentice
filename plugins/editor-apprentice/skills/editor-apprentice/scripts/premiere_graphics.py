"""Premiere only: what is written inside every Essential Graphics template (.mogrt) on a sequence — texts, font sizes,
position, and the image replaced inside it. Use it to learn the editor's template conventions from a finished episode
and to verify templates after placing them.

  python premiere_graphics.py <file.prproj> [--seq NAME] [--after SEC] [-o out.json]

Texts are base64 UTF-16 JSON (textEditValue / fontSizeEditValue) in the mogrt's capsule params; identical values are
stored once and later copies only carry a BinaryHash. A replaced image lives in a hidden sequence:
param SubClip -> MasterClip -> Clip Source -> VideoSequenceSource -> Sequence -> its track item -> media name.
"""
import argparse, base64, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import timeline as T


def graphics(path, seq_name=None):
    root, objs, seqs = T.prproj_sequences(path)
    if not seq_name:
        seq_name = max(seqs, key=lambda n: len(T._prproj_items(seqs[n], objs)))
    items = T._prproj_items(seqs[seq_name], objs)
    blobs = {e.get('BinaryHash'): e.text for e in root.iter('StartKeyframeValue') if e.get('BinaryHash') and e.text}
    byuid = {e.get('ObjectUID'): e for e in root.iter() if e.get('ObjectUID')}

    def seq_media(uid):
        M = byuid.get(uid)
        if M is None:
            return None
        for c in M.iter():
            o = objs.get(c.get('ObjectRef') or '')
            if o is None:
                continue
            src = T._ref(o.find('.//Source'), objs)
            if src is None:
                continue
            for e in src.iter():
                if e.tag != 'Sequence' or not e.get('ObjectURef'):
                    continue
                S = byuid.get(e.get('ObjectURef'))
                out = []
                for t in S.iter():
                    g = objs.get(t.get('ObjectRef') or '')
                    if g is None or g.tag != 'VideoTrackGroup':
                        continue
                    for tr in g.iter('Track'):
                        TR = T._ref(tr, objs)
                        if TR is None:
                            continue
                        for ir in TR.findall('.//TrackItems/TrackItem'):
                            it = T._ref(ir, objs)
                            sub = T._ref(it.find('.//SubClip'), objs) if it is not None else None
                            if sub is not None:
                                out.append(sub.findtext('.//Name'))
                return out
        return None

    res = []
    for x in items:
        if x['kind'] != 'graphic' or not x['trk'].startswith('V'):
            continue
        texts, pos, size, media = [], None, None, []
        for c in objs[x['id']].iter():
            o = objs.get(c.get('ObjectRef') or '')
            if o is None or o.tag != 'VideoComponentChain':
                continue
            for cc in o.iter():
                oo = objs.get(cc.get('ObjectRef') or '')
                if oo is None or oo.tag != 'VideoFilterComponent':
                    continue
                for p in oo.iter():
                    q = objs.get(p.get('ObjectRef') or '')
                    if q is None:
                        continue
                    if q.tag == 'SubClip' and q.find('MasterClip') is not None:
                        m = seq_media(q.find('MasterClip').get('ObjectURef'))
                        media += m or [q.findtext('Name')]
                        continue
                    if q.findtext('Name') == 'Position' and pos is None:
                        pos = q.findtext('StartKeyframeValue')
                    if q.tag != 'ArbVideoComponentParam':
                        continue
                    e = q.find('StartKeyframeValue')
                    v = (e.text if e is not None else None) or (blobs.get(e.get('BinaryHash')) if e is not None else None)
                    if not v:
                        continue
                    try:
                        j = json.loads(base64.b64decode(v).decode('utf-16-le'))
                    except Exception:
                        continue
                    if 'textEditValue' in j:
                        texts.append(j['textEditValue'])
                        size = j.get('fontSizeEditValue', size)
            break
        res.append({'trk': x['trk'], 't0': x['t0'], 't1': x['t1'], 'template': os.path.basename(x['file'] or x['name']),
                    'texts': texts, 'size': size, 'pos': pos, 'media': media})
    return sorted(res, key=lambda r: r['t0'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('prproj'); ap.add_argument('--seq'); ap.add_argument('--after', type=float, default=0); ap.add_argument('-o')
    a = ap.parse_args()
    res = graphics(a.prproj, a.seq)
    for r in res:
        if r['t0'] >= a.after:
            C.uprint(f"{C.mmss(r['t0'])} {r['trk']:4} {r['t1'] - r['t0']:5.2f}s {r['template'][:22]:22} {r['texts']} size={r['size']} {r['media'] or ''}")
    if a.o:
        C.jdump(res, a.o)


if __name__ == '__main__':
    main()
