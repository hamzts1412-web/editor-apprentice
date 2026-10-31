"""Drive DaVinci Resolve through its scripting API (Resolve must be running; Preferences › System › General ›
"External scripting using" = Local). The free version may refuse external scripting — then import the XML by hand
(File › Import › Timeline) and export with File › Export › Timeline.

  python resolve_bridge.py info                                   version, project, timelines
  python resolve_bridge.py import <timeline.xml|fcpxml> [--name N] import a timeline (+ its media) into the current project
  python resolve_bridge.py export <out.xml|out.fcpxml|out.otio>   export the current timeline (for measure.py / final_diff.py)
  python resolve_bridge.py markers <timeline.json>                 add the timeline's markers to the current timeline
"""
import argparse, os, platform, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C


def connect():
    if platform.system() == 'Windows':
        base = os.environ.get('RESOLVE_INSTALL', r'C:\Program Files\Blackmagic Design\DaVinci Resolve')
        api = os.environ.get('RESOLVE_SCRIPT_API', r'C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting')
        lib = os.environ.get('RESOLVE_SCRIPT_LIB', os.path.join(base, 'fusionscript.dll'))
        if hasattr(os, 'add_dll_directory') and os.path.isdir(base):
            os.add_dll_directory(base)
    elif platform.system() == 'Darwin':
        api = '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting'
        lib = '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so'
    else:
        api = '/opt/resolve/Developer/Scripting'
        lib = '/opt/resolve/libs/Fusion/fusionscript.so'
    os.environ.setdefault('RESOLVE_SCRIPT_API', api)
    os.environ.setdefault('RESOLVE_SCRIPT_LIB', lib)
    sys.path.insert(0, os.path.join(api, 'Modules'))
    try:
        import DaVinciResolveScript as dvr
    except ImportError:
        import importlib.machinery, importlib.util
        loader = importlib.machinery.ExtensionFileLoader('fusionscript', lib)
        spec = importlib.util.spec_from_file_location('fusionscript', lib, loader=loader)
        dvr = importlib.util.module_from_spec(spec)
        loader.exec_module(dvr)
    r = dvr.scriptapp('Resolve')
    if r is None:
        raise SystemExit('Resolve is not reachable: open it, set Preferences › System › General › External scripting = Local, '
                         'and retry. (The free version may not allow external scripting — then import/export by hand.)')
    return r


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('info')
    i = sp.add_parser('import'); i.add_argument('file'); i.add_argument('--name')
    e = sp.add_parser('export'); e.add_argument('out')
    m = sp.add_parser('markers'); m.add_argument('timeline')
    a = ap.parse_args()
    r = connect()
    pm = r.GetProjectManager()
    proj = pm.GetCurrentProject()
    if a.cmd == 'info':
        C.uprint(r.GetProductName(), r.GetVersionString(), '| project:', proj.GetName() if proj else None)
        if proj:
            for k in range(1, proj.GetTimelineCount() + 1):
                tl = proj.GetTimelineByIndex(k)
                C.uprint(f'  timeline {k}: {tl.GetName()}  {tl.GetStartFrame()}-{tl.GetEndFrame()}')
        return
    if proj is None:
        raise SystemExit('open (or create) a project in Resolve first')
    mp = proj.GetMediaPool()
    if a.cmd == 'import':
        opts = {'timelineName': a.name or os.path.splitext(os.path.basename(a.file))[0], 'importSourceClips': True}
        tl = mp.ImportTimelineFromFile(os.path.abspath(a.file), opts)
        C.uprint('imported:', tl.GetName() if tl else 'FAILED (check media paths / file)')
    elif a.cmd == 'export':
        tl = proj.GetCurrentTimeline()
        ext = os.path.splitext(a.out)[1].lower()
        kind = {'.xml': r.EXPORT_FCP_7_XML, '.fcpxml': getattr(r, 'EXPORT_FCPXML_1_10', getattr(r, 'EXPORT_FCPXML_1_9', None)),
                '.otio': getattr(r, 'EXPORT_OTIO', None)}.get(ext)
        ok = tl.Export(os.path.abspath(a.out), kind, r.EXPORT_NONE) if kind is not None else False
        C.uprint('exported' if ok else 'export FAILED', a.out)
    elif a.cmd == 'markers':
        tl = proj.GetCurrentTimeline()
        fps = float(tl.GetSetting('timelineFrameRate'))
        n = 0
        for mk in C.jload(a.timeline).get('markers', []):
            if tl.AddMarker(int(round(mk['t'] * fps)), 'Blue', mk.get('name', '')[:60], mk.get('comment', ''), 1):
                n += 1
        C.uprint(f'{n} markers added')


if __name__ == '__main__':
    main()
