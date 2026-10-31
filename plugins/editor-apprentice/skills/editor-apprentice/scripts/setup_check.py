"""Check (and install) what the scripts need — written for editors who are not technical.

  python setup_check.py            report only
  python setup_check.py --install  pip-install the missing Python packages (ask the editor first)

Prints one line per item: OK / MISSING + the exact fix. Also finds the editing apps installed (Premiere, Resolve, FCP).
"""
import argparse, importlib, json, os, platform, shutil, subprocess, sys

PKGS = [  # (import name, pip name, why)
    ('numpy', 'numpy', 'audio maths'),
    ('faster_whisper', 'faster-whisper', 'transcription (speech -> words with timestamps)'),
    ('cv2', 'opencv-python-headless', 'reading video frames (jump-cut visibility, style from published videos)'),
]
CUDA_PKGS = ['nvidia-cublas-cu12', 'nvidia-cudnn-cu12==9.*']


def have(mod):
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False


def gpu():
    smi = shutil.which('nvidia-smi')
    if not smi:
        return None
    try:
        r = subprocess.run([smi, '--query-gpu=name,memory.total', '--format=csv,noheader'], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None
    except Exception:
        return None


APP_PREFIXES = {'Adobe Premiere Pro': 'Premiere Pro', 'Adobe After Effects': 'After Effects', 'Adobe Audition': 'Audition',
                'Adobe Photoshop': 'Photoshop', 'Adobe Illustrator': 'Illustrator', 'Adobe Media Encoder': 'Media Encoder',
                'DaVinci Resolve': 'DaVinci Resolve', 'Final Cut Pro': 'Final Cut Pro', 'CapCut': 'CapCut',
                'Blender': 'Blender'}


def apps():
    found = {}
    sysname = platform.system()
    if sysname == 'Windows':
        roots = [os.environ.get('ProgramFiles', r'C:\Program Files'),
                 os.path.join(os.environ.get('LOCALAPPDATA', ''), 'CapCut', 'Apps')]
        for root in roots:
            for sub in ('', 'Adobe', 'Blackmagic Design', 'Blender Foundation'):
                d0 = os.path.join(root, sub)
                if not os.path.isdir(d0):
                    continue
                for d in os.listdir(d0):
                    for pre, name in APP_PREFIXES.items():
                        if d.startswith(pre):
                            found[name] = os.path.join(d0, d)
        if os.path.isdir(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'CapCut')):
            found['CapCut'] = os.path.join(os.environ['LOCALAPPDATA'], 'CapCut')
    elif sysname == 'Darwin':
        for d in os.listdir('/Applications'):
            for pre, name in APP_PREFIXES.items():
                if d.startswith(pre):
                    found[name] = '/Applications/' + d
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--install', action='store_true')
    a = ap.parse_args()
    rep, missing = [], []
    ok = sys.version_info >= (3, 9)
    rep.append(('Python ' + platform.python_version(), ok, '' if ok else 'install Python 3.10+ from python.org (tick "Add to PATH")'))
    for mod, pipname, why in PKGS:
        h = have(mod)
        rep.append((f'{pipname} ({why})', h, '' if h else f'{sys.executable} -m pip install {pipname}'))
        if not h:
            missing.append(pipname)
    ff = shutil.which('ffmpeg') and shutil.which('ffprobe')
    fix = {'Windows': 'winget install Gyan.FFmpeg   (then reopen the terminal)', 'Darwin': 'brew install ffmpeg'}.get(platform.system(), 'sudo apt install ffmpeg')
    rep.append(('ffmpeg + ffprobe (read audio/video)', bool(ff), '' if ff else fix))
    g = gpu()
    rep.append((f'NVIDIA GPU: {g}' if g else 'NVIDIA GPU: none (transcription runs on the CPU — slower, ~real time or worse)', True, ''))
    if g and platform.system() == 'Windows' and have('faster_whisper'):
        cuda_ok = all(have(m) for m in ('nvidia.cublas', 'nvidia.cudnn'))
        rep.append(('CUDA libraries for faster-whisper', cuda_ok, '' if cuda_ok else f'{sys.executable} -m pip install ' + ' '.join(CUDA_PKGS)))
        if not cuda_ok:
            missing += CUDA_PKGS
    node = shutil.which('node')
    rep.append((f'Node.js (optional: only for MCP servers) {"found" if node else "not installed"}', True,
                '' if node else 'optional: install the LTS from nodejs.org if an MCP server is wanted'))
    has_ytdlp = bool(shutil.which('yt-dlp')) or have('yt_dlp')
    rep.append(('yt-dlp (optional: download reference videos / b-roll the editor approved)', True,
                '' if has_ytdlp else f'optional: {sys.executable} -m pip install yt-dlp'))
    for k, v in apps().items():
        rep.append((f'{k}: {v}', True, ''))
    for name, good, how in rep:
        print(f"{'OK     ' if good else 'MISSING'}  {name}" + (f'\n         fix: {how}' if how else ''))
    if a.install and missing:
        print('\ninstalling:', ' '.join(missing), flush=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', *missing], check=False)
    print(json.dumps({'missing': missing, 'ffmpeg': bool(ff), 'gpu': g, 'apps': apps()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
