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
  [Claim withdrawn by D40: the build's time split does not support "predicts better" for batters.]
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

- D32 (14 Nov, P2, implementation details for 07): `rate()` split into sums + `rate_from_sums()` so the
  bootstrap uses the identical formula on sparse player x match sums (un-resampled run matches 06 to 3e-14).
  Bootstrap resamples all matches with ball data, the same draws for both lists. Sensitivity variants re-rank
  the headline eligible pool (held fixed so overlaps are comparable); priors and k are re-estimated per
  variant; a player with no pressure or routine balls under a variant (e.g. no IPL balls in V9) is left
  unranked and counts as outside the top 10. Time split: players need >= 75 live pressure balls (IPL +
  T20I_full) in both periods; the late outcome is raw pressure Impact with tier weights but no recency
  decay; the usual-approach predictor uses economy with its sign flipped so higher = better for both lists.

- D33 (14 Nov, P2): RR needs (08) use IPL 2025–26 pressure balls, not 2026 only, and a cell is judged only if
  all ten teams have >= 30 pressure balls in it; the other cells are listed as "too thin to judge". Why: with
  2026 only, 3 of 12 cells lacked some teams and only 3 had every team on 30+ balls (RR death / top order had
  6 balls). Result: 6 usable cells, 2 needs (middle overs / top-order batting, middle overs / pace bowling,
  both RR 8th of 10). Rejected: role cards only (loses the RR angle); leverage-weighted Impact on all balls
  (a second definition of pressure in the same report). Role cards use IPL + T20I_full balls in 2025–26.

- D34 (14 Nov, P2): A pick "fits" an RR need cell if its role (position group, or pace/spin) matches and at
  least 30% of its 2025–26 balls fall in that cell's phase. Why: the main-phase-only rule missed top-order
  batters who bat through the middle overs (Kohli 47% middle overs, but a tie with powerplay broke the other
  way). Rejected: main phase only.

## Made after Review 1 (docs/REVIEW_1.md)
- D35 (14 Nov, R1 item 1): Chase WP in the last six balls = λ × exact backward induction + (1 − λ) × logistic,
  λ = (7 − b)/6, so the last ball is pure induction. The induction plays out every remaining ball with league
  outcome frequencies (0, 1, 2, 3, 4, 6, W, extra) of training chase balls with b ≤ 6, in three bands of runs
  needed per ball (≤ 1, 1–2, > 2; 240 / 230 / 1,638 balls), and the existing terminal rules. E_rem for
  b ≤ 3 is the empirical mean remaining runs (2.13 / 4.09 / 6.13 at b = 1 / 2 / 3; the Poisson curve gave 3.1
  at b = 1). Why: the `min(6r/b, 36)/10` term blew up as b → 1 (4 off 1 with 5 wickets was 0.78). Result
  (`wp_model_eval.md`, 5 wickets in hand): 6 off 1 0.13, 4 off 1 0.24, 12 off 3 0.11, 3 off 1 0.30, 8 off 3
  0.39 (was 0.70); mean batting ΔWP per ball on
  the last ball of a chase +1.94 points (SE 1.06, 253 balls; was −2.45), all other balls-left buckets within
  ±0.35 points; Brier and ECE unchanged (0.2203 / 0.1161, 0.018 / 0.007). The top-15 leverage states are
  still "last ball, 3–4 needed" (they are the biggest swings), now at WP 0.24–0.30.
  Deviation from the review's bar: "within ±0.5 points" is kept for every bucket except where 2 SE is wider
  (only the last chase ball, SE 1.06), because a perfectly calibrated model would fail ±0.5 on 253 balls most
  of the time. Rejected: one set of b ≤ 6 frequencies (the review's version; last-ball ΔWP +2.33, 2 off 1 at
  0.51 against 7 of 9 won), and four bands with a > 4 per ball cut (+1.81, more parameters for no clear gain).
- D36 (14 Nov, R1 item 2): Credited Impact is centred within situation. After the tier offset, `lib_rating.
  centre_impact` subtracts the league mean credited Impact of the same discipline × innings × over group (1–2,
  3–6, 7–10, 11–15, 16–18, 19–20) × pressure flag, run and wicket parts separately (unweighted, all tiers,
  live balls; recomputed inside every variant and the time split). Cell means: `outputs/impact_centering.csv`
  (largest: batters, innings 1, overs 1–2, pressure −10.8 per 100 over 9,236 balls). Why: the WP model's misfit
  differed by situation, so "pressure minus routine" partly measured where a player bats or bowls, not how he
  copes. Result (`impact_centering_check.csv`, eligible players): mean raw shift −2.91 → −0.13 per 100
  (batters) and +3.23 → +0.11 (bowlers); EB shift prior −0.034 → −0.006 and +0.026 → −0.004. The correlation
  between the role-mix shift and batters' raw shift falls from 0.42 to 0.29, not to 0: some role-linked shift
  is left inside the over groups (stated as a limitation). Bowlers' shift now has τ² ≈ 0 (k hits the 5,000
  guard), so for bowlers it barely moves anyone. F6 retitled: "Pressure level mostly follows usual level; the
  shift moves few players far". Rejected: adding wickets-down to the cells (thinner cells; not asked for, and
  the remaining 0.29 may be genuine).
- D37 (14 Nov, R1 item 3, closes Q4): Each shrunk component is standardised by the SD of its raw (unshrunk)
  values across the eligible pool, z = (shrunk − pool mean) / SD(raw), so a component that shrinkage pulls
  nearly flat counts for little; the consistency m has no upper cap (lower bound 10 kept). Weights stay
  60/15/25 nominal. Why: dividing by the SD after shrinkage re-inflated noise (bowlers' shift SD 0.5 counted
  like level SD 3.7). Result (`outputs/rating_scale_change.md`): effective weights level / shift / consistency
  74 / 13 / 13 (batters) and 83 / 2 / 16 (bowlers); m = 69 (bat) and 74 (bowl), was capped at 60. Left the top
  10: Iyer, Mendis (bat); Mujeeb, Muzarabani (bowl). In: Allen, Russell; Ngidi, Nawaz. V4 (level only) keeps
  9/10 in both lists. The 06 guard "|corr(rating, pressure balls)| < 0.3" now also passes when the rating's
  correlation is within 0.05 of the raw usual level's (bowlers 0.309 vs raw 0.320): better bowlers get more
  pressure overs, so the correlation is real, not made by shrinkage. Rejected: re-weighting to keep 60/15/25
  effective (would put the noise back); a cap on m (the data gives a value).
- D38 (14 Nov, R1 item 4, owner decided): Eligibility counts live balls in all four tiers (was IPL + T20I_full
  only, D19); minimums (400 / 125 / 10 / 60), tier weights and offsets unchanged; no IPL-ball minimum. The
  time split's ≥ 75 pressure balls per period follows the same count (D32 changed with it: n 60 bat, 57 bowl).
  Each player's IPL pressure balls are now reported (`ipl_pressure_balls` in ratings_*.csv, column in T3/T4).
  Why: owner's call; the weights and offsets already discount weaker cricket, and showing the IPL count lets
  readers judge each pick's evidence. Result (`eligibility_funnel.csv`): pool 105 batters (was 100), 109
  bowlers (was 103); both top 10s unchanged. Picks with little IPL evidence: Nawaz 0 and Ngidi 71 (bowl), Allen
  38 (bat) IPL pressure balls. Rejected: an IPL pressure-ball minimum (owner declined).
- D39 (14 Nov, R1 item 5): T3 / T4 (`top10_*.md`) move from 06 to a new step `src/09_top10_tables.py` (runs
  after 07, since it needs the bootstrap) and gain the 90% rank interval, the share of resamples in the top 10
  and a confidence band: secure ≥ 80%, probable 50–80%, marginal < 50% (called "confidence" so it is not
  confused with competition tiers). The report says the order inside a band is the point estimate only and
  that places 9–10 are coin-flips against 11–12. Result: batters 3 secure / 3 probable / 4 marginal, bowlers
  2 / 4 / 4; #9–12 top-10 shares 33 / 31 / 34 / 25% (bat) and 40 / 33 / 34 / 26% (bowl). Rejected: re-ordering
  by top-10 share (the rating is the estimate; the share describes its uncertainty).
- D40 (14 Nov, R1 item 6, closes Q5): The time split is reported as it is, after D35–D38, with two
  additions in 07: (a) early-period shrunk consistency as a predictor; (b) a noise ceiling, i.e. the split-half
  reliability of the 2025–26 outcome (matches split at random into halves, Spearman between players' halves,
  Spearman-Brown corrected, mean of 200 splits, seed 42); √reliability is the most any predictor could reach
  (`outputs/time_split_ceiling.csv`, dashed line on F8). Result (n 60 batters, 57 bowlers): full rating 0.01
  (bat) and 0.25 (bowl); shrunk pressure level 0.01 / 0.32; raw pressure Impact 0.19 / 0.23; raw shift 0.22 /
  −0.08; usual approach 0.23 / 0.31; usual level −0.01 / 0.33; consistency 0.12 / 0.00; split-half 0.16 /
  0.17, reliability 0.27 / 0.28, ceiling 0.52 / 0.53. So for bowlers the rating recovers about half of what
  is recoverable; for batters it shows no persistence, and the plain "usual approach" does as well as
  anything. The claim "usual level + shrunk shift predicts better" is deleted from spec 2.4 and D14. Weights
  are not retuned (n ≈ 60). Rejected: switching batters to raw pressure Impact or the usual approach on this
  evidence (intervals overlap zero and each other; it would be tuning on the test).
- D41 (14 Nov, R1 item 7, closes Q3; owner kept the per-innings cut): First-innings pressure is stated
  plainly as mostly new-ball pressure. 03 now writes the evidence to `leverage_summary.md`: 98.2% / 83.8% of
  first-innings over-1 / over-2 balls flagged; first-innings powerplay = 40.4% of all pressure balls; median
  LI of pressure balls 1.15 (innings 1) vs 2.17 (chases). T3/T4 (09) add each pick's share of pressure balls in
  the first innings and a chase-only pressure rank: the same shrunk pressure level computed on innings-2 balls
  only (priors and k re-estimated on chase balls), ranked within the eligible pool. Spec 1.4 corrected to the
  built mix 77.3 / 21.3 / 1.4 (was the prototype's 48 / 45 / 7). Result: picks who rank low when chasing are
  Arya 51st, Patidar 57th, Russell 67th (bat) and none of the bowlers below 21st; Allen has only 7 chase
  pressure balls (97% first innings). Rejected: a global cut (V3; owner decided, it means "chases only").
- D42 (14 Nov, R1 item 8): F3 redrawn by innings × phase as pressure minus routine within over ×
  wickets-down cells (0–5, 6+ down), averaged with precision weights nP·nR/(nP + nR), 90% match bootstrap
  (1,000, seed 42); crude gaps shown hollow. Rows in `pressure_validation.csv` (tables
  `pressure_minus_routine_within_cell` / `_crude`). Result, SR (within cell): chase middle −8.1 (−11.7 to
  −4.6), chase powerplay −5.1 (−9.9 to +0.2), chase death −0.1; first-innings powerplay +2.5 (−4.3 to +9.0),
  middle +10.6 (+4.9 to +16.5), death −5.0 (wide, 353 balls). Wicket %: chase death +0.7 (−0.2 to +1.6);
  first-innings powerplay −0.9 and middle −1.0 (both below 0). Crude first-innings powerplay gap −25.8. Title
  states only what holds: "Like for like, chases slow down on middle-overs pressure balls (SR −8); other gaps
  are small or mixed", and 04 checks that claim. The review's suggested wording ("death overs cost wickets,
  first innings shows no effect") does not survive: the death wicket gap's interval includes 0, and
  first-innings middle overs show the opposite effect. Rejected: pressure-ball weights (they lean on
  first-innings overs 1–2, where 98% of balls are pressure, giving −12.4 with an interval of −25 to 0).
- D43 (14 Nov, R1 item 9, spec 4.3): `outputs/top10_match_detail.csv` (written by 09): for every top-10 pick,
  the three best and three worst pressure matches (≥ 3 pressure balls, as for consistency) by credited raw
  pressure WPA, with date, competition, tier, team, opponent, innings and pressure balls, plus the player's
  total pressure WPA, the total without the best match and the best match's share. Result: no batter's total
  rests on one game except Allen (total 0.09 wins, −0.02 without his best match) and Russell (62% from one
  match). For bowlers, raw WPA and the rating disagree for three picks: Bumrah 0.22 total (−0.15 without his
  best match), Mustafizur 0.42 (−0.17), Ngidi −0.64. Why they can disagree: raw WPA is dominated by a handful
  of last-overs balls (one six conceded at the death can cost 0.3–0.4 wins), while the rating uses Impact
  (WPA ÷ leverage, centred by situation, tier- and recency-weighted), which counts every pressure ball on the
  same scale. Reported, not changed (it is variant V12, which already shows raw WPA ranks differ: 4/10 overlap).
- D44 (14 Nov, R1 item 10): No rule change. T3/T4 flag a pick "high variance" if any eligibility count is
  below 1.25 × its minimum, or one season holds ≥ 75% of its pressure balls (all tiers); the reason is printed
  in a Flag column and the flagged picks are named in the text for the limitations section. A rule rather
  than two hand-picked names, so it applies the same way to every pick. Result: Sooryavanshi (87% of pressure
  balls in 2026), Arya (446 balls, minimum 400), Russell (126 pressure balls, minimum 125; 10 pressure
  matches, minimum 10); no bowler. Rejected: raising the minimums (owner: no rule change).

## Made after the red-team read (docs/REDTEAM.md)
- D45 (18 Nov, RT fix 1; owner asked for the change, D41's per-innings cut is kept): pressure balls are
  weighted by the stakes of their innings. A pressure ball's weight omega is multiplied by
  s_i = (median LI of pressure balls in innings i) / (the larger of the two medians), so a chase pressure ball
  counts 1 and a first-innings pressure ball about 1.15 / 2.17 ≈ 0.53. The medians are computed on all scored
  balls before any tier or year filter, like the cut. Routine and dead balls, the cut itself, eligibility
  counts and plain stats are unchanged. Same rule for both lists. Fixed before any re-ranking was seen.
  Why: the per-innings cut makes a first-innings pressure ball (median LI 1.15, 77% powerplay) count the same
  as a chase pressure ball (median LI 2.17), and the like-for-like evidence that pressure changes outcomes
  (D42) is in chases; the red-team read found 3 of the top 10 batters below the median chaser. Weighting by
  measured stakes keeps first-innings play in the rating (D10's reason for the per-innings cut) without
  letting the new ball dominate. Rejected: a global cut (V3, rates chases only); weighting each ball by its
  own LI (a few last-ball chase balls at LI 10–17 would dominate); a hand-picked ratio such as 30/70.
  The previous headline is kept as sensitivity variant V13 (equal innings weight).
  Result: s_1 = 0.529. Batters: Russell out (10th to 11th), Iyer in (9th); order changes (Klaasen 3rd to
  2nd, Arya 2nd to 3rd, Allen 9th to 6th, Patidar 6th to 8th). Chase-only ranks of the ten: 1, 29, 51, 5,
  15, 26, 3, 57, 7, 21 (was 1, 51, 29, 15, 5, 57, 3, 21, 26, 67). Bowlers: same ten, Ngidi 8th to 4th.
  V13 keeps 9/10 and 10/10. Time split (outcome now also stake-weighted): rating 0.03 bat (was 0.01),
  0.19 bowl (was 0.25, interval now -0.03 to 0.39); bowl pressure level 0.24 (was 0.32); ceilings
  0.54 / 0.48 (were 0.52 / 0.53). Within noise, but the change did not improve persistence and the
  report's bowler claim is softened to "partly repeats". Core picks: 5 bat, 8 bowl (10 of 13 variants).

- D46 (18 Nov, RT fix 2): The report shows (a) the 10 eligible players outside each top 10 with the most IPL
  2025-26 balls (balls faced; legal balls bowled) and (b) every eligible player in RR's IPL 2026 squad, with
  rank, top-10 share, pressure-level rank, chase-only rank, IPL pressure balls and the component on which each
  is furthest behind the #10 pick (nominal weight x z-score gap). Written by 09 to `context_players.csv`.
  Why: a reader's first question is "where is X?"; the brief asks for rankings from data, "not reputation
  alone". IPL usage is a data stand-in for reputation, so no names are chosen by hand. Rejected: a hand-picked
  list of stars (open to cherry-picking); the top 10 by the usual death / RRR > 10 stat (overlaps our lists:
  Arya, Sooryavanshi, David, Allen and Patidar are all in its top 8). Result: closest batters Suryakumar 12th
  (33%), Prabhsimran 14th; bowlers Noor Ahmad 12th (34%), Varun 13th; Gill 38th, Buttler 32nd, Siraj 63rd,
  Arshdeep 29th. RR: 8 batters and 8 bowlers eligible; only Sooryavanshi is in a top 10; next Jaiswal and
  Archer, both 16th. No ranking changed.

## Open questions (Phase 2)
- Q3 (14 Nov, P2) [CLOSED by D41]: First-innings pressure balls are 77% powerplay, 21% middle, 1% death (spec 1.4 expected
  48/45/7 from the prototype). Cause: the first-innings model values a run almost equally through the innings,
  while a wicket costs ~13 expected runs at over 2 and ~4 at over 18, so the biggest swings come early.
  Proceeding unchanged; revisit after 06 to check first-innings death specialists are not treated unfairly
  (compare with variant V3 and their first-innings vs chase pressure ball counts). Spec 1.4 numbers to be
  corrected before the report.
- Q4 (14 Nov, P2) [CLOSED by D37]: The pressure shift and consistency components are mostly noise but keep their full weight,
  because each component is z-scored after shrinkage. Bowlers' shift has k_D = 3,811 balls (shrunk SD 0.5 per
  100 balls, vs 3.7 for pressure level); the consistency m hit the 60 cap in both lists (data implies ~78 bat,
  ~99 bowl). Ranking on pressure level alone keeps 8/10 batters and 7/10 bowlers (outputs/sensitivity_summary.csv,
  V4). Picks that depend on these components: Mendis, Iyer (bat); Mujeeb, Muzarabani, Mahedi Hasan (bowl).
- Q5 (14 Nov, P2) [CLOSED by D40; numbers below are pre-Review-1]: The time split contradicts D14 for batters (outputs/time_split.csv; 59 batters, 55 bowlers).
  Spearman with 2025–26 raw pressure Impact: batters — full rating 0.08 (90% CI −0.16 to 0.30), shrunk pressure
  level 0.00, raw pressure Impact 0.25 (0.03 to 0.44), raw shift 0.27, usual approach 0.18, usual level −0.04.
  Bowlers — rating 0.24, shrunk pressure level 0.36 (0.15 to 0.55), raw 0.27, usual level 0.35, usual approach
  0.19. So "usual level + shrunk shift" works for bowlers but not batters, where routine form does not predict
  pressure form (possibly a role effect: batters' pressure and routine balls come in different roles).
  Bootstrap: only 3 batters (Sooryavanshi, Klaasen, Arya) and no bowler are top 10 in >= 80% of resamples.

## Closed questions
- Q1 (closed 14 Nov): Rank purely on data; nobody is excluded or moved for being an RR player or a likely
  retention. The RR-fit section labels each pick's current franchise and lists ranks 11–15 as alternates.
- Q2 (closed 14 Nov): Super overs are excluded from the WP model and from ratings, and mentioned in the
  report. The 40 overs of tied matches are scored (a level finish = WP 0.5) but not used for training.
