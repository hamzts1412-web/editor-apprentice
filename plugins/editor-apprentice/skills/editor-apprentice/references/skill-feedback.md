# When this skill itself gets something wrong

Two kinds of mistakes happen:
- **The editor's taste or the client's rules** — a correction about *their* work. That goes into their editor/client
  skill (rule 5). It is not a mistake of this skill.
- **This skill's method or tools** — Claude followed this skill and it led somewhere wrong: it planned instead of asking,
  a rule was missing, a tool failed or gave wrong numbers, an instruction didn't fit how real editors work. Those
  improve the skill for everyone.

## Log it locally
Append to `~/.claude/editor-apprentice-feedback.md` (create it if missing), one entry per mistake:
```
## <date> — <one-line title>
- What happened: <what Claude did, following which part of the skill>
- What the editor expected: <in general terms>
- Fix that worked: <how it was solved>
- Suggested change to the skill: <file + what to change>
```
**Write it in general terms only**: no client or editor names, no channel, no quotes from their recordings, no file
paths with names, no numbers that identify a project. "A talking-head client with a script" — not who.

## Offer to share it
At the end of a session that logged entries (not mid-work), show the editor the entries and ask whether to send them to
the skill's maintainers as a GitHub issue on the repository in the plugin's README. Only on a clear yes, and only
after they've read exactly what will be sent. If they say no, keep the log local.
