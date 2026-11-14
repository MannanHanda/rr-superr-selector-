MODEL: Opus. Paste everything below the line into Claude Code after /clear.
---

Read CLAUDE.md, DECISIONS.md and docs/REVIEW_1.md.
Apply the MUST FIX items first, then the SHOULD FIX items, one at a time. For each: make the change, re-run the
affected scripts from that point onwards, and confirm the issue is resolved with a number or a figure.
Log each change in DECISIONS.md. Then mark the item in docs/REVIEW_1.md as DONE, with one line on what changed.

After all items: re-run the full pipeline from src/01_clean.py to the last script in a clean run, and show me
the final top-10 batters and top-10 bowlers. For each player give: rank, rating, rank interval, pressure balls,
and tier mix. Save these as outputs/final_top10_batters.csv and outputs/final_top10_bowlers.csv.
Then stop.
