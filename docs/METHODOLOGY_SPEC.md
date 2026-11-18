# Methodology spec — SupeRR Selector S2, Round 1

Written in Phase 1 (design), Sat 14 Nov 2026. Implemented in Phase 2 (Sun 15 – Mon 16). Report written Tue 17.
Every choice here is logged in DECISIONS.md (D6–D24). If the build forces a change, log it there first.

**The idea in four lines**
1. A win-probability (WP) model tells us, for every ball, how much the result could swing on it: its **leverage**.
2. **Pressure balls** are the top quarter of balls by leverage within each innings.
3. Each ball's outcome is valued as win probability gained, divided by what was at stake (**Impact**).
4. A player's rating combines Impact under pressure, the change from their usual level, and how often they
   come out ahead in pressure matches, after shrinking small samples.

**Numbers marked [proto]** come from a throwaway prototype run in the design session (crude version of
sections 1–3, not pipeline code). They size thresholds and set acceptance bars. The build must reproduce
them roughly, not exactly; the report quotes only numbers from `outputs/`.

Notation: `b` = balls remaining before the ball, `w` = wickets in hand (10 − wickets_before),
`r` = runs needed (chase), `score` = score_before.

---

## 1. Pressure definition

### 1.1 Rows

| Set | Rows | Used for |
|---|---|---|
| **Scored balls** | innings 1–2 of `completed` and `tie_super_over` matches, all tiers; minus innings 2 of the 4 DLS games with no revised_target (20182, 23674, 24822, 28334) | leverage and all player metrics |
| **Training balls** | scored balls with `use_for_model`, status `completed`, `is_dls != 1`, tier ≠ T20I_associate | fitting the WP model |

- No-result and abandoned matches: excluded everywhere (no outcome, mostly a few overs).
- Tied matches: scored but not trained on (the label is the super-over winner, which is not the result of the
  40 overs). A chase that ends level has terminal WP 0.5.
- Super overs (innings 3–4, 38 balls): excluded everywhere, mentioned in the report (answers Q2).
- T20I_associate is not trained on because the model sees only match state, not team strength, and those
  games are mismatches (team batting first wins 65% vs 47–50% in other tiers). They are still scored, at low weight.
- DLS games with a revised target are scored using `max_balls`, `balls_remaining` and `target` as cleaned.

### 1.2 WP model: two small logistic regressions on top of one "resources" curve

**Recommendation: logistic regression, not LightGBM.** Leverage is built from WP *differences* between
neighbouring states. Tree models give a stepped surface, so those differences are zero then jumpy; a logistic
surface is smooth and monotone by construction. With ~800 matches (rows within a match are highly correlated)
a 3–6 parameter model also overfits less. LightGBM with monotonic constraints is fitted once as a benchmark
only (CUTTABLE) to show we lose little accuracy.

**Step A — expected remaining runs `E_rem(b, w)`** ("how many more runs does an average side get from here").
Poisson regression (log link, no penalty) on first-innings training balls with `max_balls == 120`.
Target = innings total − score_before. Features, with `lb = ln(b + 1)`:
`[lb, b/120, w, w²/10, w·lb/10, w·b/1200]`. Force `E_rem = 0` when `b = 0` or `w = 0`.
E_rem is then made non-decreasing in `w` (value at `w` = highest fitted value at any `w' ≤ w`; D25).
[proto] E_rem(120,10)=181, (60,8)=102, (30,5)=48, (12,7)=26, (6,2)=8.

**Step B — par score** (era and tier): mean first-innings total of full-length completed matches in the same
`comp_tier × year`, leaving out the match itself. Cells with fewer than 10 matches use the tier mean.
[checked] IPL par rose 171 (2022) → 196 (2026); T20I_full 170 → 182, so era must be in the model.
`f = par / E_rem(120, 10)` scales the resources curve to the era. No venue adjustment (venue ids are
anonymous and only 34 of 97 venues have 8+ matches) — a stated limitation.

**Step C — first innings** (no target yet, so compare the projected total with par):
`z = (score + f·E_rem(b,w) − par_adj) / 30`, `prog = 1 − b/max_balls`,
features `[z, z·prog, z·prog²]`, logistic regression (C = 10), label `batting_team_won`.
`par_adj = par × E_rem(max_balls,10)/E_rem(120,10)` for shortened innings. At ball one z = 0, so WP ≈ 50%.
One sentence for the report: *"Is the batting side heading for more or fewer than a par score, and how far
through the innings are we?"*

**Step D — chase**: `m = f·E_rem(b,w) − r` (runs ahead of an average side), `u = m / sqrt(b + 1)`,
features `[u, u·ln(b+1), m/30, w/10, b/120, min(6r/b, 36)/10]`, logistic regression (C = 10).
Terminal states are set by rule, not by the model: `r ≤ 0` → 1; `b = 0` or `w = 0` with `r > 1` → 0; `r = 1` → 0.5.
The first innings never hands over to the chase model: the WP after the last ball of innings 1 comes from
the Step C model at `b = 0`, so no player is charged for a jump between the two models.

**Split and fit.** Hold out 20% of *matches* (GroupShuffleSplit on match_id, seed 42); all balls of a match
stay on one side, and par is leave-one-out, so there is no leakage. Report test metrics from this split,
then refit on all training matches for scoring (9 parameters, so in-sample bias is negligible).

The calibration bars below (ECE and bin gaps) are judged on out-of-fold predictions from 5-fold CV grouped
by match; Brier and the benchmark use the 20% split (D26).

**Calibration: "good enough" means all of**
- test Brier ≤ 0.225 (innings 1) and ≤ 0.135 (innings 2). [proto] 0.213 and 0.125; a coin-flip scores 0.250.
- 10-bin expected calibration error ≤ 0.03 in each innings [proto 0.024, 0.023]; no bin with ≥ 500 balls
  off by more than 0.07; and ECE ≤ 0.05 on chase balls with `b ≤ 12`.
- Sanity grid: WP falls as `r` rises and rises with `w` on ≥ 99% of a grid of chase states;
  6 needed off 6 with 5 wickets in hand > 0.80; 30 off 6 < 0.03; 1 off 6 > 0.95.
If the chase model misses these, add `u²` and a `w × u` term before considering anything else.

### 1.3 Leverage per ball

For the state before each scored ball, take eight possible outcomes: dot, 1, 2, 3, 4, 6, wicket (0 runs),
extra (1 run, ball not used). Their probabilities `p_o` are league frequencies in the same
`innings × phase` (6 cells; 5 → 4, 7 → 6). Then

```
li_raw = sqrt( Σ_o p_o · (WP(state after o) − Σ_o p_o·WP(state after o))² )     # SD of WP after the ball
LI     = li_raw / mean(li_raw over all scored balls)                             # average ball = 1.00
```

One sentence: *"Leverage is the typical size of the win-probability swing on this ball; 2.0 means twice as
much is at stake as on an average ball."* This is the Leverage Index used in baseball analytics.
[proto] mean li_raw = 0.0225; LI percentiles 50/75/90/95/99 = 0.87 / 1.17 / 1.85 / 2.38 / 4.04.

### 1.4 From leverage to pressure balls

- **Pressure ball**: LI at or above the **75th percentile of its own innings** [proto cut: 0.96 in innings 1,
  1.73 in innings 2]. Everything else that is not dead is a **routine ball**.
- **Crunch ball**: top 5% of LI over all balls. Descriptive only (tables, example chart), not in the rating.
- **Dead ball**: `li_raw < 0.002` (the ball can move WP by under 0.2 points; [proto] 6% of balls).
  Dead balls are dropped from all value metrics, so garbage-time runs and wickets count for nothing.

Why a within-innings cut: [proto] with one global top-20% cut, **99.4% of pressure balls are chase balls**,
because first-innings leverage is flat (mean LI 0.81, nearly all between 0.5 and 1.3) while chase leverage is
either near zero or very high. A global cut would rate nobody on setting a total. Pressure is therefore
defined relative to the job (setting or chasing), we say so openly, and we show the split.
Why 75%: it is a convention, justified three ways: (a) the validation chart shows outcomes change across bands,
(b) it leaves the median eligible player ~250 pressure balls, (c) the top 10 are re-run at 80%, 70% and a
global cut (section 4.4).
Built (corrected after Review 1, D41; `outputs/leverage_summary.md`): first-innings pressure is mostly the
new ball: 77.3% powerplay, 21.3% middle, 1.4% death (the prototype's 48 / 45 / 7 did not survive the build);
98% of first-innings over-1 balls and 84% of over-2 balls are pressure balls, and first-innings powerplay balls
are 40.4% of all pressure balls. First-innings pressure balls are only mildly high-leverage (median LI 1.15,
cut 1.04) against chases (median 2.17, cut 1.71). Chase pressure: 26% powerplay, 50% middle, 25% death, in
close games. The report says this plainly: first-innings "pressure" here mostly means batting or bowling with
the new ball when early wickets swing the projected total most. The owner kept the per-innings cut (a single
league-wide cut makes ~97% of pressure balls chase balls, i.e. "chases only"); T3/T4 add each pick's
chase-only pressure rank and first-innings share so readers can see who also holds up in a chase.

### 1.5 Validation: are pressure balls really different?

Named outputs: `outputs/pressure_validation.csv`, figure **F3**, figure **F4**.
- **F3 / validation table**: strike rate, dot %, boundary % and wicket % on legal balls by leverage band
  (bottom half, 50–75%, pressure 75–95%, crunch 95%+) *within each phase*, with match-bootstrap 90%
  intervals for pressure minus routine. [proto] in the middle overs SR falls 138 → 122 from the lowest to
  the highest band and in the powerplay 151 → 130 with dot % 44 → 47; at the death the pattern is mixed.
  Report whatever the final numbers show; a modest effect is still a finding.
  (Changed after Review 1, D42: the crude band gaps are mostly over number and wickets down. F3 now shows
  pressure minus routine inside the same over × wickets-down cell, by innings × phase, precision-weighted, with
  match-bootstrap intervals. What holds: chases slow by about 8 SR points on middle-overs pressure balls (and
  about 5 in the powerplay, interval touching 0); chase death overs show no SR gap and a wicket gap whose
  interval includes 0; first-innings powerplay shows no SR effect, and first-innings middle overs go the
  other way (+11 SR, −1.0 wicket %).)
- **Phase alone is not enough**: mean |WP change| per ball by phase next to mean |WP change| by leverage band.
- **F4 / the usual definition misses**: take the common definition (overs 16–20, or chase required rate
  above 10). Report what share of those balls are dead or below-median leverage, and what share of our
  pressure balls it fails to catch.

---

## 2. Performance measurement

### 2.1 Value of one ball: Impact

For each scored, non-dead ball, from the batting side's point of view:

```
wp0 = WP(state before)      wp1 = WP(actual state after)
wp_nw = WP(state after with the same runs and ball count but no wicket)
x_run = (wp_nw − wp0) / li_raw        x_wkt = (wp1 − wp_nw) / li_raw        each clipped to [−6, +6]
WPA   = wp1 − wp0   (raw win probability added)
```

One sentence: *"Impact is how much the ball helped the team's win chances, measured against how much was at
stake on that ball."* An average ball scores 0 [proto: mean 0.005, SD 1.00, same spread on pressure and routine
balls]. Dividing by leverage is what makes pressure and routine balls comparable; raw WPA is larger on
pressure balls by construction, so it cannot be used for a pressure-vs-usual comparison.

Credit rules
- **Batter** (rows with `is_ball_faced`): `x_run` on every ball faced; `x_wkt` only if `striker_out`.
  Wides are not the striker's. A run-out of the non-striker is charged to no one.
- **Bowler** (every delivery bowled, including wides and no-balls): `−x_run`, and `−x_wkt` only if
  `is_bowler_wicket` (so run-outs give the bowler no credit, consistent with D3).
- Known simplification: byes and leg-byes sit inside `x_run` for both. State it under limitations.

Tier adjustment: `x` is first corrected by a tier offset (section 3.3), then weighted by ball weight `ω`.
All "per 100 balls" figures are `100 × ω-weighted mean`.

### 2.2 Metrics reported for every player (pressure and routine columns side by side)

| Metric | Batting | Bowling |
|---|---|---|
| Impact per 100 balls | 100 × mean(x_run + x_wkt), credited as above | same, sign flipped |
| WPA (wins added) | Σ credited WPA on pressure balls; also per 100 pressure balls | same, sign flipped |
| Runs above expected per 100 | 100 × mean(batter_runs − league mean batter_runs in the same innings × phase × pressure flag × tier) | 100 × mean(expected − bowler_runs), same cells |
| Rate | strike rate = 100 × batter runs / balls faced | economy = 6 × bowler runs / legal balls |
| Dot % | dots / balls faced | dots / legal balls |
| Boundary % | (4s + 6s) / balls faced | (4s + 6s conceded) / legal balls |
| Dismissal rate | balls faced per dismissal | legal balls per bowler wicket |

Only Impact (and the sign of match WPA) enter the rating. The rest are evidence a cricket reader can check.

### 2.3 Baseline ("usual performance")

The player's own Impact on their **routine balls** (non-pressure, non-dead), same tiers, same weights.
Routine balls, not all balls, so the two sides of the comparison do not overlap.

### 2.4 The three components

All estimates are shrunk (section 3.1). `n` is the effective number of balls.

1. **Usual level** `U = Û_run + Û_wkt`: routine-ball means of the run part and the wicket part, each
   shrunk to the league mean with its own strength.
2. **Pressure shift** `D̂ = d̄ + n_P/(n_P + k_D) × (D_raw − d̄)`, where `D_raw` = raw pressure Impact − raw
   routine Impact and `d̄` is the pool mean shift. This is the "drop from baseline" (negative = drop).
3. **Pressure level** `P̂ = U + D̂`: our best estimate of the player's true Impact per ball under pressure.
4. **Consistency** `Ĉ`: among the player's matches with ≥ 3 pressure balls, the weighted share in which their
   credited pressure WPA summed to more than zero, shrunk to the pool rate by adding `m` pseudo-matches.
   One sentence: *"In what share of the games where he was under pressure did he leave his team better off?"*

Why the pressure level is built as usual level + shift: a player's routine balls are three times as many as
their pressure balls, so the routine sample is the steadier base, and the pressure sample then moves the
estimate as far as its size justifies. (Changed after Review 1, D40: the earlier claim that this "predicts
later pressure Impact better" came from the prototype and does not hold in the build. In the time split
(`outputs/time_split.csv`) the shrunk pressure level predicts 2025–26 pressure Impact for bowlers (0.32) but
not for batters (0.01), where raw pressure Impact (0.19) and the usual approach (0.23) do slightly better.
We report this as it is and do not retune on ~60 players.)

### 2.5 Reliability rating

```
Rating = 0.60 · z(P̂) + 0.15 · z(D̂) + 0.25 · z(Ĉ)        z = standard score across the eligible pool
Reported as 50 + 10 × Rating.  Ties broken by P̂.  Batters and bowlers are rated separately.
```

Weights, fixed before seeing any ranking (to avoid tuning towards names we like):
- **60% pressure level**: it is what wins matches and the best-measured of the three.
- **25% consistency**: a robust check that the level is not two or three huge games; it is the brief's
  "most consistently".
- **15% pressure shift**: the brief asks for pressure against usual level, but the shift is the noisiest
  quantity (time split, raw shift: 0.22 batters, −0.08 bowlers), so it gets the smallest weight. It also
  already moves `P̂`. Since D37 each z-score is scaled by the SD of the raw values, so the effective weights
  are set by how much survives shrinkage (`outputs/rating_scale_change.md`).

Why not rank on the drop alone: the drop is a difference of two noisy numbers, so its extremes are mostly
luck, and a player who is poor everywhere has no drop at all. A batter at Impact −5 in both situations would
outrank one who goes from +10 to +6. The level must lead; the shift only adjusts.

---

## 3. Fair comparisons

### 3.1 Empirical Bayes shrinkage

Shrunk estimate = `prior + n/(n + k) × (raw − prior)`, with `n = (Σω)² / Σω²` (effective balls) and
`k = σ² / τ²`, where `σ²` is the ball-level variance and `τ²` = variance of player means across the pool
minus the average sampling variance (method of moments). The prior is the pool's ball-weighted mean. Pool
for estimating priors and `k`: players with ≥ 200 scored balls and ≥ 60 pressure balls, per discipline.
`k` reads as *"the number of balls at which we trust the player's own record as much as the league average"*.

| Shrunk quantity | Prior | [proto] k, batters | [proto] k, bowlers |
|---|---|---|---|
| Routine run part `U_run` | league mean | ~150 | ~370 |
| Routine wicket part `U_wkt` | league mean | ~370 | ~4,300 |
| Pressure shift `D` | pool mean shift | ~1,000 | ~1,350 |
| Consistency share `C` | pool share, `m` pseudo-matches (beta-binomial moments) | m ≈ 35 | m ≈ 35 |

Runs and wickets are shrunk separately because the data says they deserve different trust: scoring and
conceding rates settle within a few hundred balls, wicket outcomes take thousands. Without the split a
couple of soft dismissals or lucky wickets drive the ranking.
Guards: if `τ² ≤ 0` or `k > 5000`, set `k = 5000` and say so in the report; `m` is limited to 10–60.
Save every prior and `k` to `outputs/eb_params.csv`.

### 3.2 Eligibility (counted on scored, non-dead balls in IPL + T20I_full only)

| | Batters | Bowlers |
|---|---|---|
| Career volume | ≥ 400 balls faced | ≥ 400 legal balls bowled |
| Pressure volume | ≥ 125 pressure balls faced | ≥ 125 pressure balls bowled |
| Pressure matches (≥ 3 pressure balls) | ≥ 10 | ≥ 10 |
| Recent, for a 2027 auction | ≥ 60 balls in 2025–26 | ≥ 60 balls in 2025–26 |
| [proto] pool size | **96** | **103** |

Numbers checked [proto, pressure cut at 75%, recent rule applied]; cells are batters / bowlers:

| total ≥ \ pressure ≥ | 75 | 100 | 125 | 150 | 200 |
|---|---|---|---|---|---|
| 300 | 130 / 141 | 112 / 121 | 100 / 106 | 88 / 94 | 69 / 62 |
| 400 | 120 / 126 | 106 / 114 | **96 / 103** | 87 / 93 | 69 / 62 |
| 500 | 102 / 107 | 96 / 101 | 91 / 97 | 84 / 90 | 69 / 62 |

At (400, 100) the median eligible player has ~256 (batters) / ~210 (bowlers) pressure balls over ~25
pressure matches, about two thirds are in an IPL 2026 squad, and almost all have 30+ first-innings pressure
balls. Associate and Emerging balls still count in a player's metrics (at low weight) but cannot make a
player eligible. The build recounts with the final model; if a pool falls outside 60–120, move the
pressure-ball minimum in steps of 25 and log it.

### 3.3 Competition tiers

Two separate things:
- **Difficulty offset (data-driven).** For each non-IPL tier and each discipline, take players with ≥ 150
  balls in that tier and ≥ 150 in the IPL, compute (their Impact per ball in the tier − in the IPL), and
  average it weighted by the smaller of the two ball counts. Subtract that offset from every ball's `x` in
  that tier. If fewer than 15 players qualify, the offset is 0. Output `outputs/tier_offsets.csv`
  (table T6). One sentence: *"The same batters score this much more easily in tier X than in the IPL, so we
  take that much off."* CUTTABLE (fallback: weights only).
- **Relevance weight (judgment, fixed in advance)**: IPL 1.0, T20I_full 0.8, Emerging 0.5, T20I_associate
  0.3. The target is IPL 2027, so IPL evidence counts most. The offsets table is the supporting evidence;
  the weights are tested in section 4.4 (IPL only; all tiers equal).

### 3.4 Recency

`w_rec = 0.5 ^ ((2026 − year) / 2)`: a two-year half-life, giving 2026 = 1.00, 2025 = 0.71, 2024 = 0.50,
2023 = 0.35, 2022 = 0.25. Ball weight `ω = w_tier × w_rec`, times `s_inn` on pressure balls (D45: s = median
pressure LI of the innings ÷ the larger median, so chase 1.00 and first innings 0.53). A match's weight (for
consistency) is the same product. Two years because form and roles change but one IPL season is only ~14 matches; variants with
no decay and a one-year half-life are in section 4.4.

### 3.5 Opposition strength: no explicit adjustment

Decided against. A proper adjustment needs bowler and batter quality estimated together, which is circular,
thin at the matchup level, and not buildable and checkable in the time. What we do instead: outcomes are
judged against league rates in the same match state, the tier offset removes the largest opposition gap, and
IPL sides are balanced by the auction. It goes in the limitations section.

---

## 4. Reliability checks

### 4.1 Bootstrap rank intervals
Resample **matches** with replacement, 1,000 times (seed 42). Hold fixed the WP model, leverage, pressure
cuts, tier offsets, priors, `k` values and the eligible pool; recompute raw means, shrunk estimates, ratings
and ranks. For each top-20 player report median rank, 5th–95th percentile rank and the share of resamples in
the top 10. Work from player × match sufficient statistics so it runs in seconds. State that the interval
does not include WP-model uncertainty.

### 4.2 Time-split test
Early = 2022–24, late = 2025–26. Players with ≥ 75 pressure balls in each period ([proto] ~50 per
discipline). Run the rating pipeline on early data only (recency anchored at 2024) and correlate (Spearman,
with a bootstrap 90% interval over players) with **late raw pressure Impact**. Compare five predictors:
(1) the full rating, (2) `P̂`, (3) raw pressure Impact, (4) the shift `D_raw` alone, (5) the usual approach:
strike rate (batters) or economy (bowlers) in overs 16–20 or at required rate above 10.
Expect [proto]: about 0.15 for batters and 0.3 for bowlers for (2); near zero for (3) in batters and for (4)
in both. With ~50 players a correlation needs to be about 0.25 to be clear of zero.
**If it is weak, we say so**: "pressure performance over two seasons is only weakly repeatable at these
sample sizes; the rating describes who has delivered and is the best available estimate, not a guarantee."
That finding is the reason for the shrinkage, the 15% weight on the shift and the rank intervals. If the
usual approach (5) predicts as well as ours, report that too, alongside what it gets wrong (F4).

### 4.3 Match-level consistency
`Ĉ` from section 2.4, plus for each top-10 player: number of pressure matches, raw share positive, and their
three best and three worst pressure matches by WPA (appendix table).

### 4.4 Sensitivity
Re-run the ranking for each variant and record the top 10. Output `outputs/sensitivity.csv`: per variant, the
overlap with the headline top 10 and the Spearman correlation across the pool; per player, the number of
variants in which they stay top 10.

| # | Variant |
|---|---|
| V1, V2 | pressure cut at the 80th / 70th percentile within innings |
| V3 | one global cut at the top 20% (chase-dominated) |
| V4, V5, V6 | weights 100/0/0, 40/20/40, 34/33/33 (level / shift / consistency) |
| V7, V8 | no recency decay; one-year half-life |
| V9, V10 | IPL balls only; all tiers weight 1 with no offsets |
| V11 | no run/wicket split (one shrinkage on total Impact) |
| V12 | level measured as raw WPA per 100 pressure balls instead of Impact |
| V13 | both innings' pressure balls weighted equally (no stake weight; the headline before D45) |
| V14 | pressure shift's run and wicket parts shrunk separately, as the usual level is (D56) |

Report the players who stay top 10 in at least 10 of 14 variants as "core picks" and name the ones who do not.

---

## 5. RR fit (short)

- **Role card per pick**: main phase (largest share of balls), usual batting position, batting hand, pace or
  spin and bowling type, share of pressure balls in innings 1 vs 2, `ipl_2026_team`.
- (Changed in build, D33: IPL 2025–26 pressure balls, and only cells where all ten teams have >= 30 balls.)
- **RR's pressure weaknesses**: on IPL 2026 pressure balls, total credited Impact per 100 balls for each team
  in each cell — batting: phase × position group (1–3, 4–7); bowling: phase × pace/spin. Rank RR among the ten
  teams in every cell; the cells where RR rank 8th–10th are the needs. Output `outputs/rr_needs.csv` (T7).
  One season is a small sample, so this section is framed as indicative.
- **Match**: a pick "fits" if their role card sits in a need cell. One line per pick.
- **Q1 (closed)**: the ranking is data-only. No one is excluded or moved for being an RR player or a likely
  retention. The RR-fit section labels each pick "already at RR" or "at another franchise", and lists ranks
  11–15 as alternates. We do not guess retention lists; the data does not contain them.
- **Q2 (closed)**: super overs are excluded from the model and from ratings; the 40 overs of tied matches
  are scored but not trained on.

---

## 6. Report plan (10–12 pages, `reports/report.html` → PDF)

| Page | Section (brief item) | Content |
|---|---|---|
| 1 | Summary | the two top-10 lists, the method in four lines, three headline findings |
| 2–3 | **1. Pressure definition** | WP model in plain words, leverage, the pressure cut, F1, F2 |
| 4 | (same) | proof that pressure balls differ and that phase alone misses it: F3, F4 |
| 5–6 | **2. Performance measurement** | Impact, credit rules, plain metrics, baseline, the rating formula and weights |
| 7 | **3. Fair comparisons** | shrinkage (F5), eligibility funnel (T2), tiers (T6), recency, opposition |
| 8–9 | **4. Evidence for the top 10** | T3, T4, F6 |
| 10 | **5. Reliability and limitations** | F7, F8, T5, list of limitations |
| 11 | RR fit (optional extra) | T7, one line per pick |
| 12 | Appendix | T1, parameters, reproduction steps (script order) |

Figures (each proves one point)
- **F1** WP calibration, both innings: predicted vs actual win rate — the model can be trusted.
- **F2** One close IPL 2026 chase: WP line with leverage bars — what pressure looks like ball by ball.
- **F3** SR, dot % and wicket % by leverage band within each phase — pressure changes outcomes inside a phase.
- **F4** Usual definition vs ours: share of "death + high required rate" balls that are dead or low-leverage,
  and share of our pressure balls it misses — the common approach measures the wrong balls.
- **F5** Raw vs shrunk pressure Impact against pressure balls (funnel) — small samples cannot top the list.
- **F6** Pressure level vs usual level, one panel per discipline, top 10 labelled, 45° line — who holds or
  lifts their level.
- **F7** Bootstrap rank intervals for the top 20, both lists — how sure we are of each place.
- **F8** Time-split: correlation of each predictor with later pressure Impact (bars with intervals) — what
  is and is not repeatable.

Tables
- **T1** Data coverage and exclusions. **T2** Eligibility funnel (players left after each rule).
- **T3 / T4** Top-10 batters / bowlers: rating, rank interval, P̂, usual level, shift, consistency, pressure
  balls and matches, WPA, SR or economy, dot %, boundary %, dismissal rate (pressure vs routine).
- **T5** Sensitivity: rank of each top-10 player under V1–V14. **T6** Tier offsets and weights.
- **T7** RR needs and which pick fills each.

---

## 7. Implementation plan

Shared code lives in `src/lib_rating.py` (weights, shrinkage, rating as functions with parameters for the
pressure cut, component weights, half-life and tier weights) so 06 and 07 call the same logic.
Seed 42 everywhere. Print summaries only.

**src/02_wp_model.py** — in: `balls.parquet`. Out: `data/processed/wp_models.pkl`,
`data/processed/par.parquet`, `outputs/wp_model_eval.md`, `outputs/figures/f1_wp_calibration.png`.
Does: sections 1.1–1.2. *Checks:* every bar in 1.2 "good enough"; training rows contain no tie, DLS,
associate or super-over ball; train and test share no match_id; benchmark LightGBM Brier within 0.01
(CUTTABLE).

**src/03_leverage.py** — in: balls, models. Out: `data/processed/ball_values.parquet` (keys + wp0, wp1,
wp_nw, li_raw, LI, is_pressure, is_crunch, is_dead, x_run, x_wkt, WPA), `outputs/leverage_summary.md`.
Does: 1.3, 1.4, 2.1 (uncredited values). *Checks:* mean LI = 1.00 ± 0.001; pressure share = 25.0% ± 0.5 in each
innings; no NaN on scored balls; all WP in [0, 1]; mean batting WPA per ball within ±0.001; summed WPA over a
completed chase equals final result minus starting WP (to 1e-6) on 20 random matches; the 4 bad DLS chases,
super overs and no-result matches are absent.

**src/04_validate_pressure.py** — in: ball_values. Out: `outputs/pressure_validation.csv`,
`outputs/naive_vs_leverage.csv`, figures f2, f3, f4. Does: 1.5. *Checks:* band shares sum to 100% per phase;
every cell has ≥ 500 balls or is flagged; the table of the 15 highest-leverage states reads as real
cricket (close chases late on) — paste it into `leverage_summary.md` for the human to eyeball.

**src/05_player_metrics.py** — in: ball_values, players. Out: `outputs/tier_offsets.csv`,
`data/processed/player_match_stats.parquet` (sufficient statistics per player × match × discipline ×
pressure flag), `outputs/metrics_batters.csv`, `outputs/metrics_bowlers.csv`, `outputs/eligibility_funnel.csv`.
Does: credit rules, 2.2, 3.2–3.4. *Checks:* league-wide credited batter runs and bowler wickets equal direct
counts from balls.parquet; pool sizes are 60–120; plain stats for three well-known players match a hand
calculation; weights reproduce the 3.4 table.

**src/06_ratings.py** — in: 05 outputs. Out: `outputs/eb_params.csv`, `outputs/ratings_batters.csv`,
`outputs/ratings_bowlers.csv` (whole pool, ranked), `outputs/top10_batters.md`, `outputs/top10_bowlers.md`
(top 20 shown, top 10 marked), figures f5, f6. Does: 2.4, 2.5, 3.1. *Checks:* nobody in the tables is below
any eligibility rule; no duplicate players; z-scores have mean 0 and SD 1; every shrunk value lies between
raw and prior; correlation of rating with pressure-ball count is below 0.3 in absolute value (volume is not
buying rank); all `k` values and guards are printed.

**src/07_reliability.py** — in: 05–06 outputs, lib. Out: `outputs/bootstrap_ranks_batters.csv`,
`..._bowlers.csv`, `outputs/time_split.csv`, `outputs/sensitivity.csv`, figures f7, f8. Does: section 4.
*Checks:* the un-resampled run reproduces 06 exactly; 1,000 resamples; every top-20 player has an interval;
all 12 variants present; time-split table includes n and intervals.

**src/08_rr_fit.py** — in: ratings, ball_values, players. Out: `outputs/rr_needs.csv`, `outputs/rr_fit.md`.
Does: section 5. *Checks:* ten IPL 2026 teams in every cell; every top-10 pick has a role card. CUTTABLE.

**Order.** Sun: 02 → 03 → 04 (stop and have the human read the calibration and the top-leverage table).
Mon: 05 → 06 → 07 → 08. As soon as 06 produces a top 20, the human checks those names against the Unstop
dropdowns.

**Cut list, first to go first:** LightGBM benchmark → 08 RR fit (replace with role cards only) → F2 →
tier offsets (weights only) → variants V10–V12 → F4. Never cut: calibration checks, shrinkage, bootstrap,
time-split, V1–V9.

---

## Coverage check against the brief

| Brief requirement | Covered in |
|---|---|
| Pressure definition: situations, indicators, why | 1.2–1.5 |
| Performance measurement: metrics, baselines, rating logic | 2.1–2.5 |
| Fair comparisons: samples, eligibility, context, IPL + T20I | 3.1–3.5 |
| Evidence for the top 10 | 6 (T3, T4, F6), 4.3 |
| Reliability and limitations | 4.1–4.4, limitations below |
| Reproducible; data, not reputation | 7 (scripts, checks), weights fixed in advance |
| Optional RR fit | 5 |

Gaps and limitations to state in the report
1. No venue or pitch adjustment, and no opponent-quality adjustment beyond tier.
2. First-innings pressure is a weaker distinction than chase pressure (flat leverage); the within-innings
   cut is a choice, tested by V3.
3. Byes and leg-byes sit in the ball value; non-striker run-outs are charged to no one; fielding is not measured.
4. Bootstrap intervals exclude WP-model uncertainty. The Impact Player rule (IPL 2023+) changes batting depth
   and is only partly absorbed by the yearly par.
5. One prior per discipline: lower-order batters are shrunk towards the same mean as top-order batters.
6. Not controlled by us: whether every top-10 name exists in the Unstop dropdowns. Check on Monday.
