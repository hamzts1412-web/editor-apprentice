"""Shared helpers: client profile, time formats, audio energy, text normalisation, script reading.

Every other script imports this. A client's numbers (rhythm, zoom, tracks, graphics…) live in the client skill's
profile.json; anything missing falls back to DEFAULT_PROFILE below.
"""
import copy, json, os, re, subprocess, sys, tempfile, unicodedata, wave, zipfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- profile

DEFAULT_PROFILE = {
    "client": "",
    "language": None,              # ISO code ("ar", "en"…); None = let Whisper detect
    "fps": 25, "width": 1920, "height": 1080,
    "cut": {
        "lead_frames": 1,          # air left before the voice when a clip starts after a silence
        "tail_frames": 2,          # air left after the last word before a silence
        "intro_lead_frames": 2, "intro_tail_frames": 1,
        "intro_end": None,         # seconds into the cut, or None = script marker / none
        "intro_marker": None,      # regex of the script line that closes the intro (ask how the script marks it)
        "breaths": "mid_speech",   # mid_speech = keep only breaths inside continuous speech | all | none
        "merge_gap": 0,            # kept phrases this close in the source play as one clip (natural pauses); 0 = tight
        "retake_window": 180,      # seconds to look ahead for a re-take of the same passage
        "keep_last_take": True,
        "meta_phrases": [],        # regex pieces: the talent talking to the crew / editor («let me redo that»)
        "note_words": [],          # words that mean "leave a dramatic pause here" (spoken direction to the editor)
        "note_fill": [],           # words around a note word that belong to the direction («here», the editor's name…)
        "fillers": [],             # extra filler regexes (language defaults below)
        "keep_words": [],          # words that look like fillers but are speech for this client
        "hallucinations": [],      # extra Whisper hallucinations to drop when alone
        "quiet_db": 9,             # an island this much quieter than the talent's median = muttering/rehearsal
    },
    "zoom": {
        "style": "ramp",           # ramp = quick push-in then slow drift back | punch = static scale per clip | none
        "method": "keyframes",     # keyframes = on the dialog clips (XML) | adjustment = layer on a zoom track (NLE UI)
        "layer": 6.0, "scale_in": 115, "ease_in": 0.6, "pos_y": 0.0,   # neutral placeholders: measure the editor's
        "punch_scale": 115, "punch_threshold": 2.5,
        "gap_min": 1.5, "gap_max": 8.0, "obvious": 9.0, "restart": 15.0, "min_len": 6.0,
        "start_after": 0,
    },
    "graphics": {"lead": 0.3, "max": 14, "kinds": {}},
    "tracks": {"dialog_v": "V1", "dialog_a": "A1", "zoom": "V3"},
    "multicam": {},
    "rules": [],
}


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_profile(path=None):
    """profile.json of a client skill (or a folder containing one); None -> defaults."""
    if path and os.path.isdir(path):
        path = os.path.join(path, 'profile.json')
    if path and os.path.exists(path):
        return deep_merge(DEFAULT_PROFILE, json.load(open(path, encoding='utf-8-sig')))
    return copy.deepcopy(DEFAULT_PROFILE)


def jload(path):
    return json.load(open(path, encoding='utf-8-sig'))


def jdump(obj, path, indent=0):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(obj, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=indent)

# ---------------------------------------------------------------- time


def tc(sec, fps=None):
    """h:mm:ss.ss (or h:mm:ss:ff with fps) — what editors type into a timecode field."""
    sec = max(0.0, float(sec))
    h, m = int(sec // 3600), int(sec % 3600 // 60)
    if fps:
        s = int(sec % 60)
        f = int(round((sec - int(sec)) * fps))
        if f >= fps:
            s, f = s + 1, 0
        return f'{h:02d}:{m:02d}:{s:02d}:{f:02d}'
    return f'{h:02d}:{m:02d}:{sec % 60:05.2f}'


def mmss(sec):
    return f'{int(sec // 60)}:{sec % 60:05.2f}'


def parse_time(s):
    """'1:02:03.5', '2:03', '123.4', '00:01:02:12@25' -> seconds."""
    if isinstance(s, (int, float)):
        return float(s)
    fps = None
    if '@' in s:
        s, fps = s.split('@')
        fps = float(fps)
    parts = [float(p) for p in s.split(':')]
    if fps and len(parts) == 4:
        return parts[0] * 3600 + parts[1] * 60 + parts[2] + parts[3] / fps
    t = 0.0
    for p in parts:
        t = t * 60 + p
    return t

# ---------------------------------------------------------------- audio


def ffmpeg():
    return os.environ.get('FFMPEG', 'ffmpeg')


def extract_wav(src, rate=16000, channel=None):
    """mono 16 kHz wav of a media file (cached in the temp folder). channel=k picks one input channel (multi-mic files)."""
    st = os.stat(src)
    tag = f'{os.path.basename(src)}.{st.st_size}.{int(st.st_mtime)}.{rate}{"" if channel is None else ".c%d" % channel}.wav'
    wav = os.path.join(tempfile.gettempdir(), 'ea_' + re.sub(r'[^\w.\-]', '_', tag))
    if not os.path.exists(wav):
        af = ['-af', f'pan=mono|c0=c{channel}'] if channel is not None else ['-ac', '1']
        subprocess.run([ffmpeg(), '-v', 'error', '-y', '-i', src, '-vn', *af, '-ar', str(rate), wav + '.part.wav'], check=True)
        os.replace(wav + '.part.wav', wav)
    return wav


def read_wav(wav):
    with wave.open(wav) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0


def energy_db(src, channel=None, hop=0.01):
    """RMS energy in dBFS every 10 ms (index k = time k/100 s)."""
    wav = extract_wav(src, channel=channel)
    out = []
    with wave.open(wav) as w:
        rate = w.getframerate()
        n = int(rate * hop)
        while True:
            buf = w.readframes(n * 6000)
            if not buf:
                break
            a = np.frombuffer(buf, np.int16).astype(np.float32) / 32768.0
            m = len(a) // n
            if m:
                out.append(np.sqrt(np.mean(a[:m * n].reshape(m, n) ** 2, axis=1) + 1e-10))
    return 20 * np.log10(np.concatenate(out)) if out else np.zeros(0)


def speech_level(db):
    """level of the talent's voice: 70th percentile of non-silent frames (robust to noise gates)."""
    voiced = db[db > -90]
    return float(np.percentile(voiced, 70)) if len(voiced) else -30.0


def silence_mask(db, below=22.0):
    lvl = speech_level(db)
    return db < lvl - below, lvl


def media_duration(src):
    r = subprocess.run([ffmpeg().replace('ffmpeg', 'ffprobe'), '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'default=nw=1:nk=1', src], capture_output=True, text=True, encoding='utf-8', errors='replace')
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None

# ---------------------------------------------------------------- text

AR_DIAC = re.compile(r'[ً-ْٰـ]')
PUNCT = re.compile(r'[^\w\s]|_')
DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')

STOPWORDS = {
    'ar': 'في و ان إن اللي ده دي دا كان كانت هو هي هم من على علي ل لـ ما لا يا بس كمان مع عن او أو بقى يعني '
          'وفي وان واللي ولكن لكن والـ ف فـ انه انها كده',
    'en': 'a an the and or but so of to in on at for with from by is are was were be been it its this that these those '
          'i you he she we they me him her us them my your our their as if then than there here not no do does did '
          'have has had will would can could just like',
}
FILLERS = {
    'ar': [r'امم+', r'ام+', r'اه+', r'ا+ه', r'(.)\1{2,}'],
    'en': [r'u+h+m*', r'u+m+', r'e+r+m*', r'h+m+', r'm+h*m+', r'a+h+'],
}
HALLUCINATIONS = {
    'ar': ['اشتركوا', 'ترجمة', 'شكرا للمشاهدة', 'موسيقى', 'نانسي', 'المترجم'],
    'en': ['thank you for watching', 'thanks for watching', 'subtitles by', 'please subscribe', 'amara.org'],
}
# words Whisper glues to the start of an island or writes alone on noise
LONE_HALLUCINATIONS = {'ar': ['شكرا'], 'en': ['you', 'thank you']}


def norm(t, lang=None):
    """text -> list of comparable tokens (no case, accents, punctuation; Arabic letter variants folded)."""
    t = unicodedata.normalize('NFKC', t).translate(DIGITS)
    if lang == 'ar' or re.search(r'[؀-ۿ]', t):
        t = AR_DIAC.sub('', t)
        t = re.sub('[أإآٱ]', 'ا', t)
        t = t.replace('ى', 'ي').replace('ة', 'ه').replace('ؤ', 'و').replace('ئ', 'ي')
    else:
        t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
    t = PUNCT.sub(' ', t.casefold())
    return t.split()


def tok(w, lang=None):
    return ''.join(norm(w, lang))


def stem(t, lang=None):
    """light stem so paraphrases compare."""
    if re.search(r'[؀-ۿ]', t):
        for p in ('وال', 'فال', 'بال', 'لل', 'ال', 'و', 'ف'):
            if t.startswith(p) and len(t) - len(p) >= 3:
                t = t[len(p):]
                break
        for s in ('هم', 'ها', 'ه'):
            if t.endswith(s) and len(t) - len(s) >= 3:
                t = t[:-len(s)]
                break
        return t
    for s in ('ing', 'ed', 'es', 's'):
        if t.endswith(s) and len(t) - len(s) >= 3:
            return t[:-len(s)]
    return t


def stopwords(lang):
    return set(norm(STOPWORDS.get(lang or '', ''), lang))


def read_script(path):
    """script text from .docx / .txt / .md (Google Docs: export as .docx or .txt first)."""
    if not path:
        return ''
    if path.lower().endswith('.docx'):
        with zipfile.ZipFile(path) as z:
            x = z.read('word/document.xml').decode('utf-8')
        x = re.sub(r'</w:p>', '\n', x)
        return re.sub(r'<[^>]+>', '', x)
    return open(path, encoding='utf-8-sig', errors='replace').read()


def detect_language(texts):
    s = ' '.join(texts)[:5000]
    if len(re.findall(r'[؀-ۿ]', s)) > len(s) * 0.2:
        return 'ar'
    return 'en'


def out_dir(project):
    d = os.path.join(os.path.abspath(project), '_auto')
    os.makedirs(d, exist_ok=True)
    return d


def uprint(*a, **k):
    """print that never dies on a Windows console code page."""
    try:
        print(*a, **k)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'utf-8'
        print(*(str(x).encode(enc, 'replace').decode(enc) for x in a), **k)


if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
