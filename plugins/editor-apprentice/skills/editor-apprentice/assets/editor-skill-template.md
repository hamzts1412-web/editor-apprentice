---
name: editor-<slug>
description: How the video editor <NAME> works — kinds of work, tools, pipeline order, what Claude does vs. what they keep, how they want Claude to control their apps, hard rules, asset locations and delivery specs — shared by all of their clients. Use it whenever <NAME> asks for help with any edit, a new client, or a project, together with the client's own skill when one exists.
---

# <NAME> — how I work

Reply in <language/dialect>. <Tone: short, concrete, editing terms; how technical they are>.
Tools: the editor-apprentice scripts folder (resolve it from that skill's base directory).

## Machine and software
<OS, GPU, apps + versions for cut / motion / color / audio / AI tools; what's installed for Claude (Python packages,
ffmpeg, MCP servers); anything that blocks automation>

## How Claude may act in my apps
<files and XML only / scripting (e.g. ae_run.py) / MCP servers: which / computer use: yes or no; installs: ask first or
I do them myself>

## Pipeline (in order) and who does what
| Step | Who | Notes |
|---|---|---|
| <…> | <editor / client / Claude> | <…> |

## Working together
<stage by stage with stops / whole pass then a fix list; how they give corrections; what to never do without asking>

## Hard rules (with reasons)
- <rule> — <why>.

## Assets
<SFX library, LUTs, template packs, fonts, motion projects, AI tools and how they're driven — paths>

## Delivery
<resolution, fps, codec, loudness, naming, folders>

## Clients
| Client | Skill | Status |
|---|---|---|
| <name> | `client-<slug>` | <draft / taught on N projects> |
