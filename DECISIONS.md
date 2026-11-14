# Decisions log

Every methodological decision goes here, newest at the bottom. Format:
`D<n> (date, phase): decision. Why. Alternative rejected.`

## Made in Phase 0 (data cleaning)
- D1 (14 Nov, P0): Legal ball = not wide and not no-ball ("Overstep" and "other" are no-balls). Why: gives
  6 legal balls in 98.2% of overs, and the rest are innings-ending overs.
- D2 (14 Nov, P0): Bowler is charged bat runs + wide runs + no-ball penalty, not byes, leg-byes or penalties.
  Why: standard cricket scoring.
- D3 (14 Nov, P0): Bowler wickets = Caught, Bowled, LBW, Stump, Hit Wicket. Why: standard credit rules.
- D4 (14 Nov, P0): Chase target = revised_target if present, else innings-1 total + 1. Revised overs are read as
  balls. Why: verified against results (810 reconcile; the 11 that don't are DLS or super-over games).
- D5 (14 Nov, P0): Competition tiers = IPL, T20I_full (both sides full members), T20I_associate, Emerging
  (A-team cups). Why: opposition strength differs a lot, so tiers get different weights later.

## Made in Phase 1 (design; full detail in docs/METHODOLOGY_SPEC.md)
Numbers marked [proto] come from a throwaway prototype run in the design session, not from the pipeline.
- D6 (14 Nov, P1): WP model = two logistic regressions (first innings: projected total vs par; chase: runs
  ahead of an average side) on one Poisson "expected remaining runs" curve. Why: leverage needs a smooth WP
  surface, and ~800 matches is little data; [proto] test Brier 0.213 / 0.125, ECE 0.024 / 0.023.
  Rejected: LightGBM with monotonic constraints (stepped surface, noisy WP differences); kept as a benchmark only.
- D7 (14 Nov, P1): Par score = leave-one-out mean first-innings total by tier × year, no venue adjustment.
  Why: IPL par moved 171 → 196 from 2022 to 2026, so era is needed; venue ids are anonymous and thin.
  Rejected: shrunk venue effects (extra build time, small gain).
- D8 (14 Nov, P1): WP training rows = completed, non-DLS, non-associate matches; split 80/20 by match.
  Why: associate games are mismatches a state-only model cannot see (bat-first side wins 65%); ties and DLS
  have unreliable labels or states. Those matches are still scored. Rejected: training on everything.
- D9 (14 Nov, P1): Leverage = SD of WP after the ball over 8 outcomes weighted by league frequencies in the
  same innings × phase, divided by the all-ball mean (average ball = 1.0). Why: standard Leverage Index, one
  sentence to explain. Rejected: "WP after a four minus WP after a wicket" (ignores how likely each is).
- D10 (14 Nov, P1): Pressure ball = LI at or above the 75th percentile of its own innings; crunch = top 5%
  overall (descriptive); dead = li_raw < 0.002 (dropped from value metrics). Why: [proto] a global top-20% cut
  is 99.4% chase balls, so first-innings play would not be rated. Rejected: global cut (kept as variant V3);
  phase or required-rate rules.
- D11 (14 Nov, P1): Ball value = Impact = WP change ÷ li_raw, split into a run part and a wicket part,
  clipped to ±6. Why: raw WPA is bigger on pressure balls by construction, so pressure vs usual needs a
  leverage-neutral scale. Rejected: raw WPA as the rated quantity (kept for evidence and variant V12).
- D12 (14 Nov, P1): Credit: batter gets the run part on balls faced and the wicket part only if he is out;
  bowler gets every delivery and the wicket part only for bowler wickets. Non-striker run-outs are charged to
  no one; byes and leg-byes stay in. Why: consistent with D2/D3 at low build cost. Rejected: full
  counterfactual removal of byes (tiny effect).
- D13 (14 Nov, P1): Baseline = the player's own Impact on routine (non-pressure, non-dead) balls.
  Why: no overlap with the pressure sample. Rejected: all-balls baseline.
- D14 (14 Nov, P1): Pressure level P̂ = shrunk usual level + shrunk pressure shift. Why: [proto] raw
  pressure Impact barely repeats across periods (0.03 batters, 0.19 bowlers) while usual level + shrunk shift
  predicts later pressure Impact better (0.16, 0.31). Rejected: shrinking raw pressure Impact to the league mean.
- D15 (14 Nov, P1): Run and wicket parts are shrunk separately. Why: [proto] run evidence stabilises in
  ~150–370 balls, wicket evidence in ~370–4,300; one shrinkage lets a few wickets drive ranks.
  Rejected: single shrinkage (variant V11).
- D16 (14 Nov, P1): Consistency = shrunk share of pressure matches (≥ 3 pressure balls) with positive
  pressure WPA. Why: one sentence, robust to one-off huge games. Rejected: SD of match Impact (hard to read).
- D17 (14 Nov, P1): Rating = 0.60·z(P̂) + 0.15·z(shift) + 0.25·z(consistency), weights fixed before seeing
  any ranking. Why: level is best measured and matters most; the shift is the noisiest ([proto] ~0
  persistence). Rejected: ranking on the drop alone; fitting weights to the time split (too few players).
- D18 (14 Nov, P1): Shrinkage strength k by method of moments, capped at 5,000; pool = ≥ 200 balls and ≥ 60
  pressure balls. Why: data decides how much to trust small samples. Rejected: hand-picked k.
- D19 (14 Nov, P1): Eligibility (IPL + T20I_full balls only): ≥ 400 balls, ≥ 125 pressure balls, ≥ 10
  pressure matches, ≥ 60 balls in 2025–26. Why: [proto] gives 96 batters and 103 bowlers, inside the 60–120
  target. Rejected: 300/75 (130/141, too loose); 500/200 (69/62, drops recent breakouts).
- D20 (14 Nov, P1): Tiers: data-driven difficulty offset from players who appear in both the IPL and the
  tier, plus fixed relevance weights IPL 1.0, T20I_full 0.8, Emerging 0.5, T20I_associate 0.3.
  Why: separates "easier runs" (measured) from "less relevant to IPL 2027" (judgment, tested in sensitivity).
  Rejected: weights alone; dropping non-IPL data.
- D21 (14 Nov, P1): Recency weight = 0.5^((2026 − year)/2). Why: auction is for 2027; one season is too
  little on its own. Rejected: no decay (V7), one-year half-life (V8).
- D22 (14 Nov, P1): No explicit opposition-strength adjustment. Why: circular, thin at matchup level, not
  buildable in time; state-based expectations and tier offsets cover most of it. Stated as a limitation.
- D23 (14 Nov, P1): Reliability = match bootstrap (1,000 resamples) for rank intervals; time split 2022–24 →
  2025–26 against five predictors, reported whatever it shows; 12 sensitivity variants.
- D24 (14 Nov, P1): Coin-flip settled the simple way: the pressure shift enters symmetrically (no one-sided
  "penalise drops only" rule).

## Made in Phase 2 (build)
- D25 (14 Nov, P2): Expected remaining runs E_rem(b, w) is made non-decreasing in wickets in hand: the value
  at w is the highest fitted value at any lower w. Why: the fitted Poisson curve bends down at 9–10 wickets
  in hand late on (12 balls left: 25.8 runs at w=7, 22.1 at w=10), so chase WP fell with more wickets in hand
  on 6.6% of the sanity grid (worst: 32 off 13, WP 0.57 at w=9 vs 0.45 at w=10). After the fix: 100%
  monotone, Brier unchanged (0.2203 / 0.1162). Rejected: the spec's fallback of adding u² and w×u to the
  chase model (93.6% monotone, calibration slightly worse), because the fault is in E_rem, not the chase model.
- D26 (14 Nov, P2): The calibration bars (ECE, bin gaps, late-chase ECE) are judged on out-of-fold
  predictions from 5-fold cross-validation grouped by match; the 80/20 match split is kept for Brier, log
  loss, AUC and the LightGBM benchmark. Why: one 152-match test set is too noisy for these bars (first-innings
  ECE ranged 0.028–0.072 across split seeds 42–49, because all balls of a match share one result).
  CV results: ECE 0.018 / 0.007, worst bin gap 0.057. Rejected: a single 20% split for calibration.
- D27 (14 Nov, P2, implementation detail): WP functions live in src/lib_wp.py, shared by 02 and 03; models
  are saved as a dict of fitted sklearn objects. Par is computed for every match with ball data; matches
  outside the par set (shortened, tied, no first innings) get the cell or tier mean without leaving
  anything out. The sanity grid uses the IPL 2026 par (196.4) and r = 1–200, b = 1–120, w = 1–10.
  LightGBM benchmark features are raw state (score/runs needed, balls left, wickets in hand, par), with
  monotone constraints on everything except par and max_balls.

- D28 (14 Nov, P2, implementation detail): Validation bands (04): low = below the innings median LI,
  medium = median to the pressure cut, pressure = pressure but not crunch, crunch = top 5% overall. Dead balls
  sit in the low band (spec does not exclude them from validation). Pressure-minus-routine uses routine balls
  (dead excluded). The F2 example is the IPL 2026 completed, full-length chase with the highest mean LI
  (match 50375). The top-15 leverage table keeps one row per distinct state.

- D29 (14 Nov, P2): F4 (usual definition vs leverage) shows chase balls only; the all-innings and
  first-innings rows stay in outputs/naive_vs_leverage.csv. Why: in the first innings the comparison is
  partly circular (our first-innings pressure is mostly powerplay, the usual definition there is overs 16–20),
  which inflates "misses 77% of our pressure balls" (99% in innings 1, 54% in chases). Rejected: all innings.

- D30 (14 Nov, P2, implementation details for 05):
  (a) Tier offsets are computed and applied separately for the run and wicket parts of Impact (they sum to
  the spec's single offset), because 06 shrinks the two parts separately. Players' per-tier means are
  unweighted. Result: T20I_full +4.5 (bat) and +1.5 (bowl) Impact per 100 balls, from 58 and 66 players;
  Emerging and associate offsets are 0 (fewer than 15 players qualify).
  (b) Plain stats (SR, economy, dot %, boundary %, balls per dismissal/wicket) are unweighted counts over
  IPL + T20I_full balls, so cricket readers can check them against public records; "all" columns include
  dead balls. Impact, runs above expected and WPA use all tiers with ball weights.
  (c) Ball counts for bowlers (eligibility, ">= 3 pressure balls" for a pressure match) are legal balls;
  Impact for bowlers is averaged per delivery (wides and no-balls included), per spec 2.1.
  (d) Runs above expected: league mean runs per ball in the same discipline x innings x phase x flag x tier,
  live balls only (bowler runs per delivery for bowlers).
  (e) Pool sizes with the spec thresholds: 99 batters, 103 bowlers; no threshold change needed.

- D31 (14 Nov, P2, implementation details for 06): Shared rating code moved to src/lib_rating.py (05 now
  uses it; its outputs are byte-identical). EB pool = >= 200 live balls and >= 60 live pressure balls, all
  tiers. k for the shift uses the pressure-ball variance (spec form n_P / (n_P + k_D)). Consistency uses
  match weights; n = effective matches, m from beta-binomial moments, clamped to 10–60. z-scores use the
  population SD over the eligible pool.

## Open questions (Phase 2)
- Q3 (14 Nov, P2): First-innings pressure balls are 77% powerplay, 21% middle, 1% death (spec 1.4 expected
  48/45/7 from the prototype). Cause: the first-innings model values a run almost equally through the innings,
  while a wicket costs ~13 expected runs at over 2 and ~4 at over 18, so the biggest swings come early.
  Proceeding unchanged; revisit after 06 to check first-innings death specialists are not treated unfairly
  (compare with variant V3 and their first-innings vs chase pressure ball counts). Spec 1.4 numbers to be
  corrected before the report.

## Closed questions
- Q1 (closed 14 Nov): Rank purely on data; nobody is excluded or moved for being an RR player or a likely
  retention. The RR-fit section labels each pick's current franchise and lists ranks 11–15 as alternates.
- Q2 (closed 14 Nov): Super overs are excluded from the WP model and from ratings, and mentioned in the
  report. The 40 overs of tied matches are scored (a level finish = WP 0.5) but not used for training.
