MODEL: Opus. Paste everything below the line into Claude Code. Use it again after each /clear,
changing only the "Start with" line.
---

You are implementing the methodology in docs/METHODOLOGY_SPEC.md. The design is fixed. Do not change methods.
If something in the spec is impossible, ambiguous or gives absurd results, stop and tell me. Don't quietly
work around it.

## Read first
CLAUDE.md, DECISIONS.md, then section 7 of docs/METHODOLOGY_SPEC.md (the implementation plan). Read other
spec sections only when the script you are writing needs them.

## How to work
- Build ONE script at a time, in the order given in section 7.
- After writing a script, run it from the repo root and check every acceptance check listed for it.
  Print a short pass/fail table.
- If a check fails, fix it, re-run, and re-check. If it still fails after two attempts, stop and report.
- After each script passes, tell me in at most 5 lines: what it produced, its key numbers, and anything
  surprising. Then suggest the git commit message, and WAIT for me to say "next" before starting the next script.
- Keep printed output small (see CLAUDE.md working rules). Save full tables to outputs/.
- Record any small implementation choice the spec didn't cover in DECISIONS.md.

Start with: script 02 (the first script in section 7).
