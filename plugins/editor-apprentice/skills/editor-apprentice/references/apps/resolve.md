# DaVinci Resolve

## Getting your timelines in
- Use **FCP7 XML** (`.xml`). `File › Import › Timeline…` (Ctrl+Shift+I) → pick the file → Load XML → OK (keep
  "Automatically import source clips into media pool" on). If Resolve says "Media Pool is Empty", use Ctrl+Shift+I as
  above, which imports the source clips itself.
- Tested on Resolve 21 (free): clips with in points, Zoom + Position keyframes on the right frames (Resolve smooths
  slightly between keyframes), a still on V2, an SFX at −20 dB, markers.
- FCPXML imports too, but Resolve lays out connected-clip audio differently — use FCP7 XML for Resolve.

## Scripting (Studio only)
Resolve **Studio**: Preferences › System › General › "External scripting using: Local", then `resolve_bridge.py info /
import / export / markers` with Resolve running. The free version has no external scripting: imports and exports by hand
(or computer use). Community MCP servers for Resolve also need Studio.

## Reading a finished Resolve edit
`File › Export › Timeline…` → FCP 7 XML (or FCPXML) → `timeline.py read` / `measure.py` / `final_diff.py`.
Studio: `resolve_bridge.py export <out.xml>`.

## Computer use notes
Shift+4 Edit page, Shift+1 Project Manager, Shift+Z fit timeline. Clicking the timeline ruler moves the playhead; the
Inspector shows Zoom/Position/Volume at the playhead. A project can't be deleted while open.
