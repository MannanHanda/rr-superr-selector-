MODEL: Fable (or Opus, if the Fable window has closed). Paste everything below the line into Claude Code
after /clear.
---

You are reviewing an analysis before it is written up. You designed the method (docs/METHODOLOGY_SPEC.md);
another model implemented it. Your job is to find what is wrong, weak or surprising. Don't praise. Don't
rewrite the code yourself.

## Read
CLAUDE.md, DECISIONS.md, docs/METHODOLOGY_SPEC.md, then the files in outputs/ (tables and figures; open the
figures). Read a src/ script only when an output looks wrong and you need to see why.

## Check, in this order
1. **WP model:** is it calibrated? Any leakage, for example features that use information from after the ball?
   Do its predictions make cricket sense in a few states you test? (For example: needing 20 off 6 balls with
   2 wickets left; or 180/2 after 15 overs batting first.)
2. **Pressure:** is the leverage distribution sensible? Does the league-wide validation chart actually show that
   pressure changes outcomes?
3. **Rankings:** do the top 10s pass a cricket smell test? For any surprising name, check its sample size,
   tier mix and match-level detail. Any player with a tiny sample, mostly associate cricket, or one freak game?
4. **Reliability:** do the bootstrap intervals overlap so much that the order 1–10 is meaningless? If so, what
   should the report say? Is the time-split result reported honestly?
5. **Brief coverage:** go through the brief's five required report items in CLAUDE.md and mark each as
   covered / weak / missing.

## Output
Write docs/REVIEW_1.md: a numbered list of issues. For each: severity (MUST FIX / SHOULD FIX / NOTE), the
evidence (file and number), and the specific fix for Opus to apply. Put MUST FIX items first. Keep it under
about 60 lines.
Then give me a summary of at most 8 lines in chat.
