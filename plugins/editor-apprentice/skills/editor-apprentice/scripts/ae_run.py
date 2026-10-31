"""Run an ExtendScript (.jsx) inside the After Effects that is already open, and print what it returns.

No MCP server or panel needed: Windows uses `AfterFX.exe -r`, macOS uses AppleScript `DoScriptFile`. The script runs
as one Undo step. Whatever its last expression evaluates to (a string — use toJSON() from ae/lib.jsx for objects) is
written to a result file and printed; errors come back with their line.

  python ae_run.py <script.jsx> [--lib] [--name "Undo name"] [--timeout 120] [--ae "<AfterFX.exe or app name>"]
  python ae_run.py --eval "app.project.numItems"
  python ae_run.py --inspect [--only "<comp name part>"]     # summary of the open project (comps, layers, effects, fonts)

--lib loads ae/lib.jsx first (helpers: inspect, newComp, txt, icon, keys, snap…).
After Effects must allow it once: Preferences › Scripting & Expressions › "Allow Scripts to Write Files and Access
Network" (the result comes back through a file).
"""
import argparse, glob, json, os, platform, subprocess, sys, tempfile, time, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(os.path.dirname(HERE), 'ae', 'lib.jsx')


def js_str(s):
    """a JS string literal that is pure ASCII (non-Latin paths survive any file encoding)"""
    return '"' + ''.join(c if 32 <= ord(c) < 127 and c not in '"\\' else ('\\' + c if c in '"\\' else f'\\u{ord(c):04x}')
                         for c in s) + '"'


def short_path(p):
    if os.name != 'nt' or ' ' not in p:
        return p
    import ctypes
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(p, buf, 1024)
    return buf.value if n else p


def find_ae():
    if platform.system() == 'Windows':
        pf = os.environ.get('ProgramFiles', r'C:\Program Files')
        hits = sorted(glob.glob(os.path.join(pf, 'Adobe', 'Adobe After Effects*', 'Support Files', 'AfterFX.exe')))
        return hits[-1] if hits else None
    if platform.system() == 'Darwin':
        hits = sorted(d for d in os.listdir('/Applications') if d.startswith('Adobe After Effects'))
        return hits[-1] if hits else None
    return None


def wrapper(body_files, inline, result, undo):
    # top level on purpose: eval at top level defines the lib's functions globally, so later code (and a scene file's
    # own eval(readUtf8(...)) of another file) can use them
    load = ''.join(f'__out = eval(readUtf8({js_str(os.path.abspath(f))}));\n' for f in body_files)
    return f"""var __res = new File({js_str(result)});
function readUtf8(p) {{ var f = new File(p); f.encoding = "UTF-8"; if (!f.open("r")) throw new Error("cannot read " + p);
  var s = f.read(); f.close(); return s; }}
var __out, __ok = true;
app.beginUndoGroup({js_str(undo)});
try {{
{load}{('__out = eval(' + js_str(inline) + ');') if inline else ''}
}} catch (e) {{ __ok = false; __out = "ERROR line " + e.line + ": " + e.toString(); }}
app.endUndoGroup();
__res.encoding = "UTF-8"; __res.open("w"); __res.write((__ok ? "OK\\n" : "ERR\\n") + String(__out)); __res.close();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('script', nargs='?')
    ap.add_argument('--eval')
    ap.add_argument('--inspect', action='store_true')
    ap.add_argument('--only')
    ap.add_argument('--lib', action='store_true')
    ap.add_argument('--name', default='Claude script')
    ap.add_argument('--timeout', type=float, default=120)
    ap.add_argument('--ae')
    a = ap.parse_args()
    ae = a.ae or find_ae()
    if not ae:
        sys.exit('After Effects not found — pass --ae "<path to AfterFX.exe>" (Windows) or the app name (macOS)')
    files, inline = [], a.eval
    if a.lib or a.inspect:
        files.append(LIB)
    if a.inspect:
        inline = 'inspect(' + ('{only: ' + js_str(a.only) + '}' if a.only else '') + ')'
    if a.script:
        files.append(a.script)
    if not files and not inline:
        ap.error('give a script, --eval or --inspect')
    tmp = tempfile.gettempdir()
    tag = uuid.uuid4().hex[:8]
    result = os.path.join(tmp, f'ea_result_{tag}.txt')
    wrap = os.path.join(tmp, f'ea_run_{tag}.jsx')
    with open(wrap, 'w', encoding='ascii') as f:
        f.write(wrapper(files, inline, result.replace('\\', '/'), a.name))
    if platform.system() == 'Windows':
        subprocess.Popen([ae, '-r', short_path(wrap)])   # runs in the open instance; quoting the path can make it exit
    else:
        app = os.path.splitext(os.path.basename(ae))[0]
        subprocess.run(['osascript', '-e', f'tell application "{app}" to DoScriptFile "{wrap}"'], check=False)
    t0 = time.time()
    while not os.path.exists(result):
        if time.time() - t0 > a.timeout:
            sys.exit('no result: is After Effects open and not busy (render, modal dialog)? Is "Allow Scripts to Write '
                     'Files and Access Network" on? (Preferences › Scripting & Expressions)')
        time.sleep(0.3)
    time.sleep(0.2)
    txt = open(result, encoding='utf-8-sig').read()
    for p in (result, wrap):
        try:
            os.remove(p)
        except OSError:
            pass
    status, _, out = txt.partition('\n')
    sys.stdout.reconfigure(encoding='utf-8')
    print(out)
    sys.exit(0 if status == 'OK' else 1)


if __name__ == '__main__':
    main()
