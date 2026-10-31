# Setup — tools, models, MCP servers, computer use

Many editors are not technical. You install; they approve. Before each install say in one line what it is, why, how
big, and that you'll ask again before anything else. Things only they can do (a setting inside an app, an admin
prompt, a panel copy that needs admin rights) — explain step by step and wait.

## 1. Check the machine
`python <scripts>/setup_check.py` → Python, packages, ffmpeg, GPU, Node, installed editing apps. No Python at all → ask
them to install Python 3.10+ from python.org (Windows: tick "Add python.exe to PATH"), then rerun.

## 2. Core installs (after a yes)
- Python packages: `python <scripts>/setup_check.py --install` (numpy, faster-whisper, opencv; on Windows with an
  NVIDIA GPU also the CUDA libraries faster-whisper needs).
- ffmpeg: Windows `winget install Gyan.FFmpeg` (reopen the terminal after), macOS `brew install ffmpeg`, Linux
  `sudo apt install ffmpeg`.
- Run Python scripts that read downloaded or client files with `python -I` (isolated mode).

## 3. Transcription model
- Default: faster-whisper `large-v3-turbo` (downloads ~1.5 GB once). NVIDIA GPU: ~1–3 min per hour of audio; CPU:
  about real time or slower — start it in the background and work on something else; it skips files already done.
- Apple Silicon: faster-whisper runs on CPU; for speed, whisper.cpp or mlx-whisper can be used — write a small adapter
  that outputs the same `.islands.json` format (`build-a-tool.md`) only if the editor needs the speed.
- Languages: Whisper covers ~100 languages; dialects and code-switching (foreign names inside speech) are where it
  drops words — always pass the client's terms (`--terms` / profile `terms`).

## 4. App control
- **Files and scripting** need nothing extra, except: After Effects › Preferences › Scripting & Expressions › "Allow
  Scripts to Write Files and Access Network" (for `ae_run.py`); Resolve Studio › Preferences › System › General ›
  "External scripting using: Local" (for `resolve_bridge.py`).
- **MCP servers** (optional, community-made): check the repository (maintained, license, supports their app version),
  tell the editor what gets installed (a panel inside the app + a local server, usually Node.js), install after a yes,
  register it (`claude mcp add …` or the project's `.mcp.json`). MCP servers load when a session starts — after
  adding one, a new session is needed; until then use files/scripting. Panels inside Adobe apps must be open (and
  often set to auto-run) and reopened after the app restarts.
- **Windows pitfalls**: PowerShell may block `npm` (`npm.ps1` cannot be loaded) — use `npm.cmd`; copying into
  `C:\Program Files\…` needs admin rights — if a copy fails silently, give the editor the exact source and target to
  copy by hand; Windows PowerShell 5 guesses file encodings — never write non-Latin text files with
  `Set-Content`/`Get-Content`, use the file tools or Python with UTF-8.
- **Computer use**: the Claude desktop app with computer use enabled and access granted per app. Anti-cheat software
  can block synthetic input — ask the editor to close it if clicks do nothing. Prefer files/scripting whenever possible:
  faster, exact, reversible.

## 5. What to say before long jobs
How long it will take, that it runs in the background, and what you'll do meanwhile.
