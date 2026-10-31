"""One timeline format for every NLE — read finished projects, write new timelines.

Canonical timeline (all times in seconds):
  {"name", "fps", "width", "height",
   "items": [{"trk": "V1"|"A2"…, "kind": clip|still|graphic|adjustment|audio|transition|other,
              "t0", "t1",            # timeline in/out
              "s0",                  # source in point
              "file", "name",
              "link": "id",          # same link on a V and an A item = linked clip (talking head video + its audio)
              "gain_db": -20,        # audio level (audio items)
              "fx": {"scale": [[t, %], …], "pos": [[t, x, y], …], "opacity": [[t, %], …]}  # t relative to the item start;
                                     # pos x/y = offset from the frame centre as a fraction of width/height
             }],
   "markers": [{"t", "name", "comment"}]}

Read:  python timeline.py read <project.prproj | .xml (FCP7/Premiere/Resolve export) | .fcpxml | .fcpxmld> [--seq NAME] [-o out.json]
       python timeline.py seqs <project.prproj>           list sequences
Write: python timeline.py write <timeline.json> <out.xml | out.fcpxml>   (.xml = FCP7 XML for Premiere / Resolve,
                                                                         .fcpxml = Final Cut Pro)
"""
import argparse, gzip, json, os, re, subprocess, sys
import xml.etree.ElementTree as ET
from fractions import Fraction
from urllib.parse import quote, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

STILL_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff', '.gif', '.psd', '.heic'}
GRAPHIC_EXT = {'.aegraphic', '.mogrt', '.motn', '.moti', '.setting', '.comp'}
AUDIO_EXT = {'.wav', '.mp3', '.aif', '.aiff', '.m4a', '.flac', '.ogg', '.aac'}


def kind_of(path, trk, tag='', name=''):
    if 'Transition' in tag:
        return 'transition'
    if 'Caption' in tag or trk.startswith('C'):
        return 'caption'
    if trk.startswith('A'):
        return 'audio'
    if path and re.fullmatch(r'\d+', path):   # Premiere synthetic media: adjustment layer, text graphic, colour matte…
        n = name.lower()
        return 'adjustment' if 'adjust' in n else ('graphic' if 'graphic' in n or 'text' in n or 'title' in n else 'other')
    ext = os.path.splitext(path or '')[1].lower()
    if ext in GRAPHIC_EXT:
        return 'graphic'
    if trk.startswith('A'):
        return 'audio'
    if ext in STILL_EXT:
        return 'still'
    if not path:
        return 'adjustment'
    return 'clip'


def trk_key(t):
    return (t[0] != 'V', int(t[1:]))


def sort_items(items):
    items.sort(key=lambda x: (trk_key(x['trk']), x['t0']))
    return items

# ================================================================ readers
# ---------------------------------------------------------------- Premiere .prproj (gzip XML, objects linked by id)

TPS = 254016000000  # Premiere ticks per second


def prproj_load(path):
    raw = open(path, 'rb').read()
    x = gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw
    root = ET.fromstring(x)
    objs = {}
    for el in root:
        k = el.get('ObjectID') or el.get('ObjectUID')
        if k:
            objs[k] = el
    return root, objs


def _ref(el, objs):
    if el is None:
        return None
    return objs.get(el.get('ObjectRef') or el.get('ObjectURef'))


def _num(el, tag, default=0):
    t = el.find('.//' + tag) if el is not None else None
    return int(t.text) if t is not None and t.text else default


def _media_path(clip_el, objs):
    src = _ref(clip_el.find('.//Source'), objs)
    for _ in range(4):
        if src is None:
            return None
        for tag in ('ActualMediaFilePath', 'FilePath'):
            t = src.find('.//' + tag)
            if t is not None and t.text:
                return t.text
        m = src.find('.//Media')
        nxt = _ref(m, objs) if m is not None else None
        if nxt is None:
            nxt = _ref(src.find('.//OriginalMedia'), objs)
        src = nxt
    return None


def prproj_sequences(path):
    root, objs = prproj_load(path)
    out = {}
    for el in root.iter('Sequence'):
        name = el.findtext('Name')
        if name and el.get('ObjectUID'):
            out.setdefault(name, el)
    return root, objs, out


def read_prproj(path, seq_name=None):
    root, objs, seqs = prproj_sequences(path)
    if not seq_name:   # the sequence with the most track items (mogrt-internal sequences hold one item)
        seq_name = max(seqs, key=lambda n: len(_prproj_items(seqs[n], objs)))
    seq = seqs[seq_name]
    items = _prproj_items(seq, objs)
    fps = 25
    for el in seq.iter('FrameRate'):
        try:
            fps = round(TPS / int(el.text), 3)
            break
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    return {'name': seq_name, 'fps': fps, 'items': sort_items(items), 'markers': [], 'source': os.path.abspath(path)}


def _prproj_items(seq, objs):
    items = []
    for tgi in seq.findall('.//TrackGroups/TrackGroup'):
        grp = _ref(tgi.find('Second'), objs)
        if grp is None:
            continue
        kind = {'VideoTrackGroup': 'V', 'AudioTrackGroup': 'A'}.get(grp.tag, 'C')   # C = caption tracks
        for ti, trk_ref in enumerate(grp.findall('.//Tracks/Track')):
            trk = _ref(trk_ref, objs)
            if trk is None:
                continue
            for it_ref in trk.findall('.//TrackItems/TrackItem'):
                it = _ref(it_ref, objs)
                if it is None:
                    continue
                ti_el = it.find('.//TrackItem')
                st, en = _num(ti_el, 'Start'), _num(ti_el, 'End')
                sub = _ref(it.find('.//SubClip'), objs)
                clip = _ref(sub.find('.//Clip'), objs) if sub is not None else None
                name = (sub.findtext('.//Name') if sub is not None else '') or ''
                f = _media_path(clip, objs) if clip is not None else None
                cin = _num(clip, 'InPoint') if clip is not None else 0
                t = f'{kind}{ti + 1}'
                items.append({'trk': t, 'kind': kind_of(f, t, it.tag, name), 'name': name, 'file': f,
                              't0': round(st / TPS, 4), 't1': round(en / TPS, 4), 's0': round(cin / TPS, 4),
                              'id': it.get('ObjectID'), 'tag': it.tag})
    return items

# ---------------------------------------------------------------- FCP7 XML (xmeml) — Premiere / Resolve / FCP7 exports


def _rate(el):
    tb = el.find('rate/timebase') if el is not None else None
    if tb is None:
        return None
    fps = float(tb.text)
    if (el.findtext('rate/ntsc') or '').upper() == 'TRUE':
        fps = fps * 1000 / 1001
    return fps


def _path_from_url(u):
    if not u:
        return None
    p = urlparse(u)
    path = unquote(p.path)
    if re.match(r'^/[A-Za-z]:', path):
        path = path[1:]
    return path.replace('/', os.sep) if os.name == 'nt' else path


def read_xmeml(path):
    root = ET.parse(path).getroot()
    seq = root.find('.//sequence')
    fps = _rate(seq) or 25
    files = {}
    for f in root.iter('file'):
        if f.get('id') and f.find('pathurl') is not None:
            files[f.get('id')] = _path_from_url(f.findtext('pathurl'))
        elif f.get('id') and f.findtext('name') and f.get('id') not in files:
            files[f.get('id')] = None
    items = []
    for kind, tag in (('V', 'video'), ('A', 'audio')):
        media = seq.find(f'media/{tag}')
        if media is None:
            continue
        for ti, tr in enumerate(media.findall('track')):
            t = f'{kind}{ti + 1}'
            for el in tr:
                if el.tag not in ('clipitem', 'generatoritem', 'transitionitem'):
                    continue
                st, en = int(float(el.findtext('start') or -1)), int(float(el.findtext('end') or -1))
                if el.tag == 'transitionitem':
                    items.append({'trk': t, 'kind': 'transition', 'name': el.findtext('effect/name') or '',
                                  'file': None, 't0': st / fps, 't1': en / fps, 's0': 0})
                    continue
                fe = el.find('file')
                f = files.get(fe.get('id')) if fe is not None else None
                if st < 0 or en < 0:   # clip edge sits under a transition
                    prev = [x for x in items if x['trk'] == t and x['kind'] == 'transition']
                    if st < 0 and prev:
                        st = int(round(prev[-1]['t0'] * fps))
                    if en < 0:
                        en = st + int(float(el.findtext('out') or 0)) - int(float(el.findtext('in') or 0))
                k = 'adjustment' if el.tag == 'generatoritem' and 'adjust' in (el.findtext('name') or '').lower() else (
                    'graphic' if el.tag == 'generatoritem' else kind_of(f, t))
                item = {'trk': t, 'kind': k, 'name': el.findtext('name') or '', 'file': f, 't0': st / fps, 't1': en / fps,
                        's0': int(float(el.findtext('in') or 0)) / fps}
                fx = _read_motion(el, fps, int(float(el.findtext('in') or 0)))
                if fx:
                    item['fx'] = fx
                items.append(item)
    markers = [{'t': int(m.findtext('in') or 0) / fps, 'name': m.findtext('name') or '', 'comment': m.findtext('comment') or ''}
               for m in seq.findall('marker')]
    w = seq.findtext('.//format/samplecharacteristics/width')
    h = seq.findtext('.//format/samplecharacteristics/height')
    return {'name': seq.findtext('name') or os.path.basename(path), 'fps': fps, 'width': int(w or 1920), 'height': int(h or 1080),
            'items': sort_items(items), 'markers': markers, 'source': os.path.abspath(path)}


def _read_motion(el, fps, clip_in):
    fx = {}
    for eff in el.findall('filter/effect'):
        if (eff.findtext('effectid') or '') not in ('basic', 'basicmotion') and (eff.findtext('name') or '') != 'Basic Motion':
            continue
        for p in eff.findall('parameter'):
            pid = p.findtext('parameterid')
            kfs = p.findall('keyframe')
            if pid == 'scale':
                if kfs:
                    fx['scale'] = [[(int(float(k.findtext('when'))) - clip_in * KF_MEDIA_RELATIVE) / fps, float(k.findtext('value'))]
                                   for k in kfs]
                elif p.findtext('value') and abs(float(p.findtext('value')) - 100) > 0.01:
                    fx['scale'] = [[0, float(p.findtext('value'))]]
    return fx

# ---------------------------------------------------------------- FCPXML (Final Cut Pro; Resolve can export it too)


def _rt(s):
    """FCPXML rational time '1001/30000s' / '12s' -> seconds."""
    if not s:
        return 0.0
    s = s.rstrip('s')
    return float(Fraction(s)) if '/' in s else float(s)


def read_fcpxml(path):
    if os.path.isdir(path):   # .fcpxmld bundle
        path = os.path.join(path, 'Info.fcpxml')
    root = ET.parse(path).getroot()
    assets, fmts = {}, {}
    for a in root.iter('asset'):
        mr = a.find('media-rep')
        assets[a.get('id')] = _path_from_url(mr.get('src') if mr is not None else a.get('src'))
    for f in root.iter('format'):
        fmts[f.get('id')] = f
    seq = root.find('.//sequence')
    fmt = fmts.get(seq.get('format'))
    fps = 1 / _rt(fmt.get('frameDuration')) if fmt is not None and fmt.get('frameDuration') else 25
    items, markers = [], []

    def walk(el, t_par, start_par, lane_base):
        for ch in el:
            if ch.tag in ('asset-clip', 'clip', 'video', 'audio', 'title', 'ref-clip', 'mc-clip', 'sync-clip', 'gap'):
                off, st, du = _rt(ch.get('offset')), _rt(ch.get('start')), _rt(ch.get('duration'))
                t0 = t_par + (off - start_par)
                lane = int(ch.get('lane') or 0) + lane_base
                if ch.tag != 'gap':
                    trk = (f'V{lane + 1}' if lane >= 0 else f'A{-lane + 1}')
                    f = assets.get(ch.get('ref'))
                    is_audio = ch.tag == 'audio' or lane < 0
                    k = 'graphic' if ch.tag == 'title' else ('audio' if is_audio else kind_of(f, trk))
                    items.append({'trk': trk if not is_audio else (trk if trk.startswith('A') else 'A1'), 'kind': k,
                                  'name': ch.get('name') or '', 'file': f, 't0': t0, 't1': t0 + du, 's0': st})
                    if lane == 0 and ch.tag in ('asset-clip', 'clip') and f and kind_of(f, 'V1') == 'clip':
                        items.append({'trk': 'A1', 'kind': 'audio', 'name': ch.get('name') or '', 'file': f,
                                      't0': t0, 't1': t0 + du, 's0': st})
                for m in ch.findall('marker'):
                    markers.append({'t': t0 + _rt(m.get('start')) - st, 'name': m.get('value') or '', 'comment': m.get('note') or ''})
                walk(ch, t0, st, lane)   # connected clips: offsets are in this clip's source time

    spine = seq.find('spine')
    walk(spine, 0.0, 0.0, 0)
    return {'name': (root.find('.//project').get('name') if root.find('.//project') is not None else os.path.basename(path)),
            'fps': round(fps, 3), 'items': sort_items(items), 'markers': markers, 'source': os.path.abspath(path)}


def read_any(path, seq=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.prproj':
        return read_prproj(path, seq)
    if ext in ('.fcpxml', '.fcpxmld'):
        return read_fcpxml(path)
    if ext == '.xml':
        head = open(path, 'rb').read(400).decode('utf-8', 'replace')
        return read_fcpxml(path) if '<fcpxml' in head else read_xmeml(path)
    if ext == '.json':
        return C.jload(path)
    raise SystemExit(f'unknown project type: {path} (export the timeline as FCP7 XML or FCPXML)')

# ================================================================ writers

# FCP7 XML keyframe <when>: frames counted from the clip's media start (in point included) — verified by importing a
# keyframed test timeline into Premiere 2026 and Resolve 21 (values landed on the expected frames).
KF_MEDIA_RELATIVE = 1


def probe(path):
    """duration (s), has video, has audio — via ffprobe; stills get a long duration."""
    ext = os.path.splitext(path)[1].lower()
    if ext in STILL_EXT:
        return {'dur': 3600.0, 'v': True, 'a': False, 'still': True, 'w': None, 'h': None}
    try:
        r = subprocess.run([C.ffmpeg().replace('ffmpeg', 'ffprobe'), '-v', 'error', '-show_entries',
                            'format=duration:stream=codec_type,width,height,r_frame_rate', '-of', 'json', path],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        d = json.loads(r.stdout or '{}')
        st = d.get('streams', [])
        vs = [s for s in st if s.get('codec_type') == 'video']
        fr_ = None
        if vs and vs[0].get('r_frame_rate', '0/0') != '0/0':
            fr_ = float(Fraction(vs[0]['r_frame_rate']))
        return {'dur': float(d.get('format', {}).get('duration') or 0), 'v': bool(vs),
                'a': any(s.get('codec_type') == 'audio' for s in st), 'still': False,
                'w': vs[0].get('width') if vs else None, 'h': vs[0].get('height') if vs else None, 'fps': fr_}
    except Exception:
        return {'dur': 0.0, 'v': ext not in AUDIO_EXT, 'a': True, 'still': False, 'w': None, 'h': None}


def pathurl(p):
    p = os.path.abspath(p).replace('\\', '/')
    return 'file://localhost/' + quote(p.lstrip('/'), safe='/:') if re.match(r'^[A-Za-z]:', p) else 'file://localhost' + quote(p, safe='/')


def esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def write_xmeml(tl, path):
    fps = tl.get('fps', 25)
    ib = int(round(fps))
    ntsc = 'TRUE' if abs(fps - round(fps)) > 0.01 else 'FALSE'
    rate = f'<rate><timebase>{ib}</timebase><ntsc>{ntsc}</ntsc></rate>'
    W, H = tl.get('width', 1920), tl.get('height', 1080)

    def fr(t):
        return int(round(t * fps))

    probes, ids, done = {}, {}, set()

    def mrate(p):
        """a clip's in/out and its file are counted in the MEDIA's own frame rate (29.97 camera in a 30 sequence would
        otherwise drift ~0.1 %: 0.7 s after 12 min)"""
        mf = p.get('fps') or fps
        if abs(mf - fps) < 0.001:
            return fps, rate
        return mf, f'<rate><timebase>{int(round(mf))}</timebase><ntsc>{"TRUE" if abs(mf - round(mf)) > 0.01 else "FALSE"}</ntsc></rate>'

    def file_el(f, media_kind):
        if f not in ids:
            ids[f] = f'file-{len(ids) + 1}'
            probes[f] = probe(f)
        fid = ids[f]
        if fid in done:
            return f'<file id="{fid}"/>'
        done.add(fid)
        p = probes[f]
        mf, mr = mrate(p)
        med = ''
        if p['v']:
            med += (f'<video><samplecharacteristics>{mr}<width>{p["w"] or W}</width><height>{p["h"] or H}</height>'
                    f'<pixelaspectratio>square</pixelaspectratio></samplecharacteristics></video>')
        if p['a']:
            med += '<audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics><channelcount>2</channelcount></audio>'
        return (f'<file id="{fid}"><name>{esc(os.path.basename(f))}</name><pathurl>{pathurl(f)}</pathurl>{mr}'
                f'<duration>{int(round(p["dur"] * mf))}</duration><timecode>{mr}<string>00:00:00:00</string><frame>0</frame>'
                f'<displayformat>NDF</displayformat></timecode><media>{med}</media></file>')

    items = [x for x in tl['items'] if x.get('kind') != 'transition' and x.get('file')]
    vtr = sorted({x['trk'] for x in items if x['trk'].startswith('V')} | {'V1'}, key=trk_key)
    atr = sorted({x['trk'] for x in items if x['trk'].startswith('A')} | {'A1'}, key=trk_key)
    vmax, amax = max(int(t[1:]) for t in vtr), max(int(t[1:]) for t in atr)
    # clip ids and link groups
    for n, x in enumerate(items):
        x['_id'] = f'c{n + 1}'
    links = {}
    for x in items:
        if x.get('link'):
            links.setdefault(x['link'], []).append(x)
    index_in_track = {}
    for t in vtr + atr:
        for k, x in enumerate(sorted([y for y in items if y['trk'] == t], key=lambda y: y['t0'])):
            index_in_track[x['_id']] = k + 1

    def clip_el(x):
        st, en = fr(x['t0']), fr(x['t1'])
        if en <= st:
            return ''
        is_a = x['trk'].startswith('A')
        fe = file_el(x['file'], 'audio' if is_a else 'video')
        p = probes[x['file']]
        # clip in/out in SEQUENCE frames = source time × sequence fps (time-exact); only the <file> carries the media's
        # own rate. Verified in Premiere by reading the imported in points back (see references/nle/premiere.md).
        mf, mr = fps, rate
        i0 = fr(x.get('s0', 0))
        i1 = i0 + (en - st)
        dur = max(fr(p['dur']), i1)
        lk = ''
        for y in links.get(x.get('link'), []):
            lk += (f'<link><linkclipref>{y["_id"]}</linkclipref><mediatype>{"audio" if y["trk"].startswith("A") else "video"}</mediatype>'
                   f'<trackindex>{y["trk"][1:]}</trackindex><clipindex>{index_in_track[y["_id"]]}</clipindex></link>')
        if not is_a and not (x.get('fx') or {}).get('scale') and p.get('w') and p['w'] != W and not p.get('still'):
            # a 4K screen recording in a 1080p sequence imports at 100 % = cropped; fit it to the frame
            x = dict(x, fx=dict(x.get('fx') or {}, scale=[[0, round(min(W / p['w'], H / (p['h'] or H)) * 100, 3)]]))
        filt = _xmeml_filters(x, mf, i0, is_a)
        return (f'<clipitem id="{x["_id"]}"><name>{esc(x.get("name") or os.path.basename(x["file"]))}</name><enabled>TRUE</enabled>'
                f'<duration>{dur}</duration>{mr}<start>{st}</start><end>{en}</end><in>{i0}</in><out>{i1}</out>{fe}'
                f'<sourcetrack><mediatype>{"audio" if is_a else "video"}</mediatype><trackindex>1</trackindex></sourcetrack>'
                f'{filt}{lk}</clipitem>')

    def track_xml(t):
        return '<track>' + ''.join(clip_el(x) for x in sorted([y for y in items if y['trk'] == t], key=lambda y: y['t0'])) + '</track>'

    total = max([fr(x['t1']) for x in items] + [0])
    vx = ''.join(track_xml(f'V{k}') for k in range(1, vmax + 1))
    ax = ''.join(track_xml(f'A{k}') for k in range(1, amax + 1))
    mk = ''.join(f'<marker><name>{esc(m.get("name", "")[:60])}</name><comment>{esc(m.get("comment", ""))}</comment>'
                 f'<in>{fr(m["t"])}</in><out>-1</out></marker>' for m in tl.get('markers', []))
    x = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="seq-1">'
         f'<name>{esc(tl.get("name", "timeline"))}</name><duration>{total}</duration>{rate}'
         f'<timecode>{rate}<string>00:00:00:00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>'
         f'<media><video><format><samplecharacteristics>{rate}<width>{W}</width><height>{H}</height>'
         f'<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>{vx}</video>'
         f'<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate>'
         f'</samplecharacteristics></format>{ax}</audio></media>{mk}</sequence></xmeml>')
    open(path, 'w', encoding='utf-8').write(x)
    return total / fps


def _xmeml_filters(x, fps, i0, is_audio):
    out = ''
    g = x.get('gain_db')
    if is_audio and g is not None:
        out += ('<filter><effect><name>Audio Levels</name><effectid>audiolevels</effectid><effectcategory>audiolevels</effectcategory>'
                '<effecttype>audiolevels</effecttype><mediatype>audio</mediatype><parameter><parameterid>level</parameterid>'
                f'<name>Level</name><valuemin>0</valuemin><valuemax>3.98109</valuemax><value>{10 ** (g / 20):.5f}</value>'
                '</parameter></effect></filter>')
    fx = x.get('fx') or {}
    if is_audio or not (fx.get('scale') or fx.get('pos')):
        return out
    base = i0 * KF_MEDIA_RELATIVE

    def when(t):
        return base + int(round(t * fps))

    params = ''
    sc = fx.get('scale')
    if sc:
        kf = ''.join(f'<keyframe><when>{when(t)}</when><value>{v:.3f}</value></keyframe>' for t, v in sc) if len(sc) > 1 else ''
        params += (f'<parameter authoringApp="PremierePro"><parameterid>scale</parameterid><name>Scale</name><valuemin>0</valuemin>'
                   f'<valuemax>1000</valuemax><value>{sc[0][1]:.3f}</value>{kf}</parameter>')
    ps = fx.get('pos')
    if ps:
        # FCP7 'center' = offset from the frame centre in fractions of the frame (verified on import: Premiere 2026 and
        # Resolve 21 both move the picture vert × 1080 px; horiz assumed × width — not yet verified)
        kf = ''.join(f'<keyframe><when>{when(t)}</when><value><horiz>{px:.5f}</horiz><vert>{py:.5f}</vert></value></keyframe>'
                     for t, px, py in ps) if len(ps) > 1 else ''
        params += (f'<parameter authoringApp="PremierePro"><parameterid>center</parameterid><name>Center</name>'
                   f'<value><horiz>{ps[0][1]:.5f}</horiz><vert>{ps[0][2]:.5f}</vert></value>{kf}</parameter>')
    return out + (f'<filter><effect><name>Basic Motion</name><effectid>basic</effectid><effectcategory>motion</effectcategory>'
                  f'<effecttype>motion</effecttype><mediatype>video</mediatype>{params}</effect></filter>')


def write_fcpxml(tl, path):
    """FCPXML 1.9: V1 (+ its linked audio) is the primary storyline; every other track becomes connected clips
    on lanes (V2 -> lane 1 …, A2 -> lane -1 …). Experimental — check the first import in Final Cut Pro."""
    fps = tl.get('fps', 25)
    num, den = (1001, int(round(fps * 1001))) if abs(fps - round(fps)) > 0.01 else (1, int(round(fps)))
    W, H = tl.get('width', 1920), tl.get('height', 1080)

    def rt(t):   # seconds -> frame-exact rational
        f = int(round(t * fps))
        return f'{f * num}/{den}s' if num != 1 or den != 1 else f'{f}s'

    items = [x for x in tl['items'] if x.get('kind') != 'transition' and x.get('file')]
    assets = {}
    for x in items:
        if x['file'] not in assets:
            assets[x['file']] = (f'r{len(assets) + 2}', probe(x['file']))
    res = [f'<format id="r1" frameDuration="{num}/{den}s" width="{W}" height="{H}"/>']
    for f, (aid, p) in assets.items():
        res.append(f'<asset id="{aid}" name="{esc(os.path.basename(f))}" start="0s" duration="{rt(p["dur"])}" '
                   f'hasVideo="{1 if p["v"] else 0}" hasAudio="{1 if p["a"] else 0}" format="r1">'
                   f'<media-rep kind="original-media" src="{esc("file:///" + quote(os.path.abspath(f).replace(chr(92), "/").lstrip("/"), safe="/:"))}"/></asset>')
    prim = sorted([x for x in items if x['trk'] == 'V1'], key=lambda x: x['t0'])
    linked_a = {x.get('link') for x in prim if x.get('link')}
    others = [x for x in items if x['trk'] != 'V1' and not (x['trk'] == 'A1' and x.get('link') in linked_a)]

    def fx_xml(x):
        fx = x.get('fx') or {}
        if not fx.get('scale') and not fx.get('pos'):
            return ''
        s0 = x.get('s0', 0)
        parts = []
        if fx.get('scale'):
            kf = ''.join(f'<keyframe time="{rt(s0 + t)}" value="{v / 100:.4f} {v / 100:.4f}"/>' for t, v in fx['scale'])
            parts.append(f'<param name="scale" key="1" value="{fx["scale"][0][1] / 100:.4f} {fx["scale"][0][1] / 100:.4f}">'
                         f'<keyframeAnimation>{kf}</keyframeAnimation></param>' if len(fx['scale']) > 1 else '')
        if fx.get('pos'):   # FCP position is in % of frame height (vertical) — convert from fractions
            kf = ''.join(f'<keyframe time="{rt(s0 + t)}" value="{px * W / H * 100:.3f} {-py * 100:.3f}"/>' for t, px, py in fx['pos'])
            parts.append(f'<param name="position" key="2"><keyframeAnimation>{kf}</keyframeAnimation></param>')
        static = f' scale="{fx["scale"][0][1] / 100:.4f} {fx["scale"][0][1] / 100:.4f}"' if fx.get('scale') and len(fx['scale']) == 1 else ''
        return f'<adjust-transform{static}>{"".join(parts)}</adjust-transform>'

    def gain_xml(x):
        return f'<adjust-volume amount="{x["gain_db"]:.1f}dB"/>' if x.get('gain_db') is not None else ''

    def clip_xml(x, offset, lane=None, inner=''):
        aid = assets[x['file']][0]
        la = f' lane="{lane}"' if lane else ''
        return (f'<asset-clip ref="{aid}"{la} offset="{offset}" name="{esc(x.get("name") or os.path.basename(x["file"]))}" '
                f'start="{rt(x.get("s0", 0))}" duration="{rt(x["t1"] - x["t0"])}" tcFormat="NDF">'
                f'{fx_xml(x)}{gain_xml(x)}{inner}</asset-clip>')

    # spine: primary clips + gaps; connected clips attach to the spine element they start over
    spine, t = [], 0.0
    for x in prim:
        if x['t0'] > t + 1e-6:
            spine.append({'kind': 'gap', 't0': t, 't1': x['t0']})
        spine.append({'kind': 'clip', 'x': x, 't0': x['t0'], 't1': x['t1']})
        t = x['t1']
    end = max([x['t1'] for x in items] + [t])
    if end > t + 1e-6:
        spine.append({'kind': 'gap', 't0': t, 't1': end})
    for el in spine:
        el['kids'] = []
    for x in sorted(others, key=lambda x: x['t0']):
        host = next((e for e in spine if e['t0'] - 1e-6 <= x['t0'] < e['t1']), spine[-1])
        host['kids'].append(x)
    for m in tl.get('markers', []):
        host = next((e for e in spine if e['t0'] - 1e-6 <= m['t'] < e['t1']), spine[-1])
        host.setdefault('marks', []).append(m)
    out = []
    for e in spine:
        local0 = e['x'].get('s0', 0) if e['kind'] == 'clip' else 0.0   # child offsets are in the host's own time
        inner = ''
        for k in e['kids']:
            n = int(k['trk'][1:])
            lane = n - 1 if k['trk'].startswith('V') else -(n - 1 if n > 1 else 1)
            inner += clip_xml(k, rt(local0 + k['t0'] - e['t0']), lane)
        for m in e.get('marks', []):
            inner += f'<marker start="{rt(local0 + m["t"] - e["t0"])}" duration="{rt(1 / fps)}" value="{esc(m.get("name", ""))}" note="{esc(m.get("comment", ""))}"/>'
        if e['kind'] == 'gap':
            out.append(f'<gap name="Gap" offset="{rt(e["t0"])}" start="0s" duration="{rt(e["t1"] - e["t0"])}">{inner}</gap>')
        else:
            out.append(clip_xml(e['x'], rt(e['t0']), None, inner))
    name = esc(tl.get('name', 'timeline'))
    x = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<fcpxml version="1.9"><resources>{"".join(res)}</resources>'
         f'<library><event name="{name}"><project name="{name}"><sequence format="r1" duration="{rt(end)}" tcStart="0s" tcFormat="NDF" '
         f'audioLayout="stereo" audioRate="48k"><spine>{"".join(out)}</spine></sequence></project></event></library></fcpxml>')
    open(path, 'w', encoding='utf-8').write(x)
    return end


def write_any(tl, path):
    return write_fcpxml(tl, path) if path.lower().endswith('.fcpxml') else write_xmeml(tl, path)


def summary(tl):
    from collections import Counter
    c = Counter((x['trk'], x['kind']) for x in tl['items'])
    end = max([x['t1'] for x in tl['items']] + [0])
    lines = [f"{tl.get('name')}  fps {tl.get('fps')}  length {C.tc(end)}  items {len(tl['items'])}  markers {len(tl.get('markers', []))}"]
    for (t, k), n in sorted(c.items(), key=lambda z: (trk_key(z[0][0]), z[0][1])):
        names = Counter(os.path.basename(x['file'] or x['name'] or '?') for x in tl['items'] if x['trk'] == t and x['kind'] == k)
        lines.append(f'  {t:4} {k:10} {n:5}  ' + ', '.join(f'{a} x{b}' for a, b in names.most_common(3)))
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('read'); r.add_argument('project'); r.add_argument('--seq'); r.add_argument('-o')
    s = sp.add_parser('seqs'); s.add_argument('project')
    w = sp.add_parser('write'); w.add_argument('timeline'); w.add_argument('out')
    a = ap.parse_args()
    if a.cmd == 'seqs':
        _, _, seqs = prproj_sequences(a.project)
        for n, el in seqs.items():
            C.uprint(f'{sum(1 for _ in el.iter("TrackItem")):6}  {n}')
    elif a.cmd == 'read':
        tl = read_any(a.project, a.seq)
        C.uprint(summary(tl))
        if a.o:
            C.jdump(tl, a.o)
    else:
        tl = C.jload(a.timeline)
        n = write_any(tl, a.out)
        C.uprint(f'wrote {a.out}  ({C.tc(n)})')


if __name__ == '__main__':
    main()
