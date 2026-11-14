# SupeRR Selector Season 2 — Round 1

Claude Code reads this file at the start of every session. Keep it accurate and short.

## The task
Rajasthan Royals (RR) analytics hackathon, run on Unstop. More than 10,000 entrants; the top 16 go to an in-person final.
**Brief:** build a data-driven system that measures how batters and bowlers perform in high-pressure
situations compared with their usual level, then rank the players who deliver most consistently when it matters.
The framing is RR's IPL 2027 auction strategy.

**Deadline: Wed 18 Nov 2026, 18:29 GMT. Our internal target is to submit by Wed 14:00.**

### What we submit
1. **Two ordered top-10 lists** (batters, bowlers), chosen from player dropdowns on Unstop. No repeats within a list.
   The dropdowns must match the report exactly.
2. **Methodology report** (PDF). The brief requires it to cover:
   - Pressure definition: which situations and indicators, and why
   - Performance measurement: batting and bowling metrics, player baselines, rating logic
   - Fair comparisons: sample sizes, eligibility, match context, how IPL and T20I data are combined
   - Evidence for the top 10: results, comparisons, tables or charts
   - Reliability and limitations: consistency across matches, and where the model is less certain
   It must be "transparent enough for someone else to understand and reproduce", and rankings must come from
   the data, "not reputation alone".
3. Optional extra: a short section or appendix on how each pick strengthens the RR squad.

### Our strategy (decided; details live in docs/METHODOLOGY_SPEC.md once written)
- Pressure = **leverage**: how much the win probability could swing on a ball, from a win-probability model
  trained on this data. Show the league-wide evidence that high-pressure balls really do change outcomes.
- Performance = context-adjusted, mainly **Win Probability Added** and runs above expected, plus plain stats
  (strike rate, economy, dot %, boundary %) so cricket people can read it.
- Reliable = good under pressure **and** a small drop from the player's own baseline **and** consistent from
  match to match. Never rank on the drop alone, because that rewards players who are poor in every situation.
- Fair comparisons: shrink small samples towards the average (empirical Bayes), minimum ball counts,
  competition-tier weights, recency weights.
- Reliability checks: bootstrap rank intervals, and a 2022–24 vs 2025–26 time-split test.

## Repo layout
```
data/raw/          the data pack CSVs (never edit, never commit)
data/processed/    parquet outputs of the scripts (never commit)
src/               numbered pipeline scripts: 01_clean.py, 02_..., each reads processed files and writes new ones
outputs/           tables (csv/md) and figures/ produced by the scripts
docs/              METHODOLOGY_SPEC.md (the design), notes
reports/           the final report (report.html -> PDF)
prompts/           the phase prompts the human pastes in
DECISIONS.md       log of every methodological decision and why
PLAYBOOK.md        the human's step-by-step schedule
```

## Commands (Windows, PowerShell, from the repo root)
```
.venv\Scripts\Activate.ps1
python src/01_clean.py
```

## Processed data (made by src/01_clean.py)
`data/processed/balls.parquet`: one row per delivery (200,999 rows). Key columns:
- ids: match_id, innings (3 and 4 = super overs), overid (1-20), innings_ball_num, striker_id, non_striker_id, bowler_id
- context: match_date, year, season, comp_name, comp_tier (IPL / T20I_full / T20I_associate / Emerging),
  stage, knock_out, venue_id, venue_country, status (completed / tie_super_over / no_result / abandoned), is_dls
- accounting: is_legal, is_wide, is_noball, is_ball_faced, total_runs, batter_runs, bowler_runs,
  is_dot_faced, is_four, is_six, is_wicket, is_bowler_wicket, striker_out, dismissed_player_id, dismissal_type
- state BEFORE the ball: score_before, wickets_before, legal_balls_before, max_balls, balls_remaining, phase,
  target, runs_needed, req_run_rate, cur_run_rate (chase fields are NaN in innings 1)
- labels: batting_team_won (1/0, NaN if no result), use_for_model (result known and not a super over)
- player detail: batting_type (RHB/LHB), bowling_type, pace_or_spin, batting_order, stroke, delivery_style

`data/processed/matches.parquet`: one row per match, with status, is_dls, comp_tier, win_team_id, revised_target.
`data/processed/players.parquet`: player_id, player_name, volumes, first/last year, tiers, all_teams, ipl_2026_team.
`outputs/data_quality.md`: coverage tables and every known data issue.

## Data facts and gotchas (verified)
- 883 matches (867 with ball data), Jan 2022 to Nov 2026: IPL 2022–26 (371), T20Is (482, including associates
  such as Hong Kong, Kuwait and Japan), and two emerging-team Asia Cups (30, "A" sides).
- Legal ball = not wide and not no-ball. No-balls are extras_type "Overstep" or "other".
- Bowler is charged bat runs + wide runs + no-ball penalty. Byes, leg-byes and penalty runs are not charged.
- Bowler wickets: Caught, Bowled, LBW, Stump, Hit Wicket. Run outs (45% of them dismiss the non-striker),
  retired out and obstructing the field are not credited to the bowler.
- Revised-overs columns are in BALLS. Chase target = revised_target if present, else first-innings total + 1.
- 4 DLS games have no revised_target (20182, 23674, 24822, 28334), so their chase state is unreliable.
  Exclude them from chase-pressure calculations.
- 40 no-result or abandoned matches: no outcome, so exclude them from win-probability training.
- Impact Player rule from IPL 2023 (playing_eleven.is_impact) means deeper batting lineups in IPL since then.
- bowl_speed is missing on 39% of balls. Don't use it.
- No venue names, only venue_id and venue_country.
- RR's IPL 2026 squad is in players.parquet (ipl_2026_team == "Rajasthan Royals").

## Working rules for Claude
- Read DECISIONS.md and docs/METHODOLOGY_SPEC.md (once it exists) before changing any method.
- Log every methodological choice in DECISIONS.md: what, why, and the alternative rejected.
- Never print raw data dumps. Print shapes, summaries and at most 20 rows. Save full tables to outputs/.
- Each pipeline step is its own numbered script in src/ that runs end to end from the repo root. No logic
  lives only in a notebook.
- Fix random seeds (42). Every number in the report must come from a file in outputs/.
- Don't edit data/raw/. Don't commit data/.
- Charts: one message per chart, labelled axes, readable at A4 width. Save PNGs to outputs/figures/.
- Prefer simple and explainable over clever. The judges are cricket analysts, and the deadline is fixed.
- After finishing a step, say in 3–5 lines what changed and what to check, then stop.
