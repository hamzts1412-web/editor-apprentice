"""Look at your own work: still frames from a video at given times, and/or one contact sheet of many images.

  python frames.py <video> --at 1.5 4 12.2 [-o _auto/frames]           # PNG per time
  python frames.py <video> --every 10 [-o …]                           # one frame every N seconds
  python frames.py --sheet <img1.png> <img2.png> … [--cols 3] -o _auto/contact.png
  python frames.py <video> --every 30 --sheet-out _auto/contact.png    # frames + sheet in one go

Contact sheets label each tile with its file name (or time) so a review can point at it. Needs ffmpeg.
"""
import argparse, os, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def duration(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def grab(video, times, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(video))[0]
    outs = []
    for t in times:
        p = os.path.join(out_dir, f'{base}_{t:08.2f}s.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', video, '-frames:v', '1', p], check=False)
        if os.path.exists(p):
            outs.append(p)
    return outs


def sheet(images, out, cols=3, width=640):
    """tile images (any size) into one PNG, each scaled to `width` and labelled with its name"""
    if not images:
        sys.exit('no images')
    tmp = tempfile.mkdtemp(prefix='ea_sheet_')
    try:
        # copy to ASCII names: ffmpeg's image2 pattern and drawtext dislike some paths
        for k, im in enumerate(images):
            shutil.copy(im, os.path.join(tmp, f'{k:04d}.png'))
        rows = (len(images) + cols - 1) // cols
        font = next((f for f in ('C:/Windows/Fonts/arial.ttf', '/System/Library/Fonts/Helvetica.ttc',
                                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf') if os.path.exists(f)), None)
        ff = f"fontfile='{font.replace(':', chr(92) + ':')}':" if font else ''
        vf = (f'scale={width}:-2,pad={width}:ih+28:0:28:color=0x202020,'
              f"drawtext={ff}text='%{{frame_num}}':start_number=1:x=8:y=6:fontsize=18:fontcolor=white,"
              f'tile={cols}x{rows}:padding=6:color=0x101010')
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '1', '-i', os.path.join(tmp, '%04d.png'),
                            '-vf', vf, '-frames:v', '1', out], capture_output=True, text=True)
        if r.returncode:   # drawtext needs a font; fall back to an unlabelled sheet
            vf = f'scale={width}:-2,tile={cols}x{rows}:padding=6:color=0x101010'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '1', '-i', os.path.join(tmp, '%04d.png'),
                            '-vf', vf, '-frames:v', '1', out], check=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.stdout.reconfigure(encoding='utf-8')
    print(out)
    for k, im in enumerate(images, 1):
        print(f'  {k:3d}  {os.path.basename(im)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video', nargs='?')
    ap.add_argument('--at', nargs='+', type=float)
    ap.add_argument('--every', type=float)
    ap.add_argument('-o', '--out', default='_auto/frames')
    ap.add_argument('--sheet', nargs='+', help='images to tile')
    ap.add_argument('--sheet-out')
    ap.add_argument('--cols', type=int, default=3)
    ap.add_argument('--width', type=int, default=640)
    a = ap.parse_args()
    if a.sheet:
        return sheet(a.sheet, a.out if a.out != '_auto/frames' else '_auto/contact.png', a.cols, a.width)
    if not a.video:
        ap.error('give a video or --sheet')
    times = a.at or []
    if a.every:
        d = duration(a.video)
        t = a.every / 2
        while t < d:
            times.append(round(t, 2))
            t += a.every
    outs = grab(a.video, times, a.out)
    for p in outs:
        print(p)
    if a.sheet_out:
        sheet(outs, a.sheet_out, a.cols, a.width)


if __name__ == '__main__':
    main()
