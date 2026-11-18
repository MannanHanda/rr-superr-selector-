# Review 1: analysis before write-up (14 Nov 2026)

Reviewer checks were run in scratch scripts on `data/processed/`. Numbers marked (check) are not yet in `outputs/`: each fix below must write its own diagnostic there before the report quotes it. Apply 1 to 4 in order, rerun 03 to 08 once, then do the rest. Log each method change in DECISIONS.md.

## MUST FIX

1. **DONE (D35):** last six chase balls blend in exact backward induction (outcome mix by runs-per-ball band), E_rem empirical for b ≤ 3; 6 off 1 = 0.13, 4 off 1 = 0.24, 12 off 3 = 0.11; last-ball ΔWP +1.94 (SE 1.06), bar widened to 2 SE there.
   **The chase WP model is wrong in the last three balls.** With 5 wickets in hand it gives 4 needed off 1 ball a WP of 0.78, 6 off 1 0.55, 3 off 1 0.86 and 8 off 3 0.70 (check). Actual results: 5 off 1 was won 1 time in 10 (model 0.41), 6 off 1 1 in 7 (0.29), 7 to 8 off 3 27% of 22 (0.46). Mean batting-side ΔWP on the last ball of a chase is −2.45 points over 291 balls, where a calibrated model gives 0. The model is fine from 6 balls out (12 to 15 off 6: 0.37 vs 0.39 actual). Cause: the `min(6r/b, 36)/10` term in `lib_wp.chase_features` has coefficient +0.59 (`wp_model_eval.md`) and explodes as b reaches 1; `E_rem` at 1 ball left is 3.1 runs against 2.0 actual. The b ≤ 12 calibration bar cannot see it (118 to 300 balls per bin). Visible damage: all 15 rows of the top-leverage table in `leverage_summary.md` are "1 ball left, 3 to 4 needed" with WP 0.54 to 0.79, and F2 shows them. **Fix:** for chases with b ≤ 6, compute WP by exact backward induction over the 8 outcomes (frequencies from chase balls with b ≤ 6, existing terminal rules) and blend with the logistic by λ = (7 − b)/6. Replace `E_rem` for b ≤ 3 with the empirical mean. Add acceptance bars to `wp_model_eval.md`: 6 off 1 in 0.05 to 0.15; 4 off 1 below 0.30; 12 off 3 below 0.15; mean ΔWP per ball within ±0.5 points for balls-remaining buckets 1, 2–3, 4–6, 7–12 in each innings.

2. **DONE (D36):** Impact centred on discipline × innings × over group × flag (`impact_centering.csv`); mean raw shift −2.91 → −0.13 (bat), +3.23 → +0.11 (bowl); role-mix correlation 0.42 → 0.29; F6 retitled.
   **Impact is not centred within situation, so the league-wide "shift" is model misfit and F6's headline is an artifact.** Mean batter Impact per 100 balls should be 0 in any set of states. It is +4.65 routine and −2.65 pressure in the first-innings powerplay, −8.63 in first-innings overs 1–2 pressure (9,262 balls, about 8 SE), −6.55 in chase overs 16–18 pressure and +4.91 in overs 19–20 (check). `eb_params.csv` prior shift is −0.034 for batters and +0.026 for bowlers, which is what F6's title "Batters lose ground under pressure and bowlers gain" reports. These biases are the size of the player-talent SD (about 6 per 100). The shift expected from role mix alone correlates 0.44 with batters' raw shift: openers get −3 to −5 (Kohli −4.2, Abhishek −4.5), new-ball bowlers +3.3 to +4.0 (Bumrah, Bhuvneshwar, Muzarabani). **Fix:** in 05, subtract the league mean credited Impact of the same innings × over group (1–2, 3–6, 7–10, 11–15, 16–18, 19–20) × pressure flag, per discipline, as D30d already does for runs above expected. Write the cell means to `outputs/impact_centering.csv`. Retitle F6 to what survives.

3. **DONE (D37):** z-scores use the SD of raw values, m uncapped (69 / 74); effective weights 74/13/13 (bat), 83/2/16 (bowl); Mendis, Iyer, Mujeeb, Muzarabani leave the top 10 (`rating_scale_change.md`).
   **The rating re-inflates noise by z-scoring each shrunk component by its own SD (open question Q4).** Bowlers: sd(D̂) 0.48 vs sd(P̂) 3.70 (k_D 3,811 in `eb_params.csv`), so a point of shift counts about 3 times a point of level, and consistency m sits on the 60 cap while the data implies about 78 and 99. Result (`ratings_bowlers.csv`): Mujeeb is 30th on pressure level and 5th overall (z_D 2.11, z_C 2.74); Muzarabani 18th to 9th; Mahedi Hasan 16th to 10th; Bumrah 1st on level and 8th. Batters: Mendis is 28th on level (P̂ −0.1, usual −5.0, routine SR 125) and 10th overall, the "poor in every situation" case CLAUDE.md rules out. The time split gives bowler shift a Spearman of −0.09. **Fix:** standardise each component by the SD of its raw (unshrunk) values across eligible players, so shrinkage decides how much of each component survives; remove the m cap. Report the effective weights and a before/after top 10 in `outputs/rating_scale_change.md`.

4. **DONE (D38):** eligibility counts all tiers (pool 105 / 109, top 10s unchanged); `ipl_pressure_balls` added to ratings and T3/T4 (Nawaz 0, Allen 38, Ngidi 71).
   **Three top-10 bowlers and one batter have almost no IPL evidence, in a list framed as IPL auction advice.** IPL pressure balls: Mujeeb 0, Mahedi Hasan 0 (59 of his are against associates, offset 0 in `tier_offsets.csv`), Muzarabani 9, Mendis 10. The T20I_full bowler offset is only +1.5 per 100, estimated from 66 players who play both and applied to players who play none. V9 (IPL only) keeps 6 of 10 bowlers; #11 Nawaz also has 0. **Fix (owner decided 14 Nov):** no IPL-ball minimum. Count every pressure ball a player has faced or bowled, in all four tiers, towards eligibility: `lib_rating.eligibility` now counts only IPL + T20I_full (`CORE_TIERS`), so Emerging and associate balls never help a player qualify. Keep the minimum values (400 / 125 / 10 / 60) and the tier weights and offsets, which adjust for opposition and do not drop balls. Rerun the funnel and log the change in DECISIONS.md. Add an "IPL pressure balls" column to T3 and T4 so readers can see where each pick's evidence comes from.

5. **DONE (D39):** new `09_top10_tables.py` writes T3/T4 with 90% rank interval, top-10 share and band (bat 3/3/4, bowl 2/4/4 secure/probable/marginal) and the 9–12 coin-flip note.
   **The order inside the top 10 is mostly not supported, and the report must say so.** `bootstrap_ranks_*.csv`, share of resamples in the top 10 by submitted rank: batters 92, 80, 92, 58, 59, 52, 46, 38, 42, 31 (#12 Brook 30); bowlers 79, 70, 68, 70, 62, 59, 56, 63, 42, 36 (#11 Nawaz 36). 90% rank intervals for batters 4 to 10 reach 33 to 50. The intervals hold the WP model, priors and k fixed, so they understate. **Fix:** present tiers (secure ≥ 80%, probable 50–80%, marginal < 50%) and state that order within a tier is the point estimate only and that places 9–10 are coin-flips against 11–12. Add the 90% rank interval and top-10 share to `top10_*.md` (spec T3/T4; absent now).

6. **DONE (D40):** time split rerun after 1–4 and reported as is (rating 0.01 bat, 0.25 bowl); early consistency added (0.12 / 0.00); noise ceiling 0.52 / 0.53 (`time_split_ceiling.csv`, on F8); "predicts better" claim deleted from spec 2.4 and D14.
   **The time split contradicts the stated reason for the rating design, for batters.** `time_split.csv`, 2022–24 predicting 2025–26: batters (n 59) full rating 0.08 (−0.16, 0.30), shrunk pressure level 0.00, raw pressure Impact 0.25, raw shift 0.27; bowlers (n 55) rating 0.24, shrunk level 0.36, usual level alone 0.35. So batter ratings show no measurable persistence, and for bowlers pressure level predicts no better than usual level. **Fix:** report these numbers as they are; delete the "usual level + shrunk shift predicts better" claim (spec 2.4, D14, proto 0.16/0.31); add early-period consistency as a predictor (25% of the rating, never tested); add a noise ceiling (split-half reliability of the 2025–26 outcome). Rerun after fixes 1–3. Do not retune weights on n = 59.

## SHOULD FIX

7. **DONE (D41):** new-ball facts written to `leverage_summary.md` (overs 1–2: 98% / 84% flagged, 40.4% of pressure balls); T3/T4 gain chase-only pressure rank and first-innings share; spec 1.4 corrected to 77.3 / 21.3 / 1.4.
   **First-innings "pressure" is the new ball.** 98% of first-innings over-1 balls and 84% of over-2 balls are flagged; 40.5% of all pressure balls are first-innings powerplay (check). First-innings pressure balls have median LI 1.15 (cut 1.04, p95 1.32) against 2.17 in chases. Sooryavanshi, Arya and Abhishek have 78–82% of their pressure balls in innings 1 (`rr_fit.md`). V3 (global cut) keeps 5 of 10 batters, Spearman 0.61. **Fix:** say this plainly in the report, add each pick's chase-only pressure rank to T3/T4, and correct spec 1.4 (it says 48/45/7; built is 77.5/21.2/1.3). Owner decided 14 Nov: keep the per-innings cut. (A single league-wide cut (80th percentile, LI 1.32) makes 97.4% of pressure balls chase balls, so it amounts to "chases only".)

8. **DONE (D42):** F3 redrawn as within over × wickets-down gaps by innings; chase middle SR −8.1 (−11.7 to −4.6) is the one clear effect; title says so and 04 checks it; death-wicket gap interval includes 0, first-innings middle overs go the other way (+10.6).
   **F3's title "In every phase, batters score more slowly on pressure balls" is false.** Chase death overs: SR 156.7 pressure vs 156.9 routine (check); what moves there is wickets, 9.2% vs 8.0%. Within over × wickets down, the pressure-minus-routine SR gap is −8.5 in chase middle overs, −5.9 in the chase powerplay, −2.3 at the chase death, and +3.5 in the first-innings powerplay (crude −25.8; the gap is over number and wickets down). **Fix:** redraw F3 by innings with the within-cell comparison and title it with what holds: chase middle overs and powerplay slow down, death overs cost wickets, first innings shows no effect. F4 (59% / 54% / 36%) is sound.

9. **DONE (D43):** `top10_match_detail.csv` (3 best + 3 worst pressure matches per pick, with opponent, tier, WPA and best-match share); flags Allen and Russell (bat) and Bumrah, Mustafizur, Ngidi (bowl, raw WPA ≤ 0 without their best game).
   **The match-level table required by spec 4.3 is missing.** Write `outputs/top10_match_detail.csv`: the three best and three worst pressure matches per pick, with date, opponent, tier, balls and WPA. Without it nobody can check for a single freak game.

10. **DONE (D44):** T3/T4 Flag column by rule (count within 25% of a minimum, or ≥ 75% of pressure balls in one season): Sooryavanshi (87% in 2026), Arya (446 balls), plus Russell (126 pressure balls); named in the text for limitations.
   **Two batting picks rest on thin, one-season samples.** Sooryavanshi #1: 174 eligible pressure balls, 15 pressure matches, nearly all in 2026, routine SR 230. Arya #2: 402 eligible balls against a threshold of 400, raw shift +24.5, bootstrap p95 rank 34. **Fix:** no rule change; flag both in T3 as high-variance and name them in the limitations.

## NOTE

11. The LightGBM chase benchmark (Brier 0.152 vs logistic 0.116, `wp_model_eval.md`) is misconfigured, so the "within 0.01 of the benchmark" check is empty. Fix the benchmark or drop the claim.
12. The first-innings model is weak (AUC 0.70, Brier 0.220 against 0.250 for a coin) and overconfident at the top (bin 0.8–0.9: predicted 0.843, actual 0.785). First-innings leverage inherits this; state it as a limitation.
13. `rr_fit.md`: both NEED cells rest on 84 and 103 balls. The top-order middle-overs "fit" is Sooryavanshi, who is already at RR and bats 67% in the powerplay; no top-10 bowler fits the middle-overs pace need. Keep the section short and indicative.
14. Sanity states that pass: 20 off 6 with 2 wickets left 0.03; 180/2 after 15 overs 0.84 (180/6: 0.73); chase of 197 at ball one 0.55. No feature leakage found (state-before features, leave-one-out par, splits by match).
15. Dropdown names (e.g. "Namboori Tilak Varma") still need checking against Unstop.

## After the fixes: still to check (added 15 Nov)

Things the fixes surfaced or decided that need the owner's eye before the write-up. Each points at its evidence.

**Findings to decide how to present**
- [ ] **Raw match WPA disagrees with three bowling picks** (`outputs/top10_match_detail.csv`, D43). Bumrah's total
  pressure WPA is 0.22 wins over 44 matches (−0.15 without his best match), Mustafizur's is −0.17 without his best,
  and Ngidi's total is −0.64. The rating scales every ball by its leverage and centres it on the situation, so
  a few last-over balls can't dominate it; raw WPA is dominated by exactly those balls. Judges may ask about
  this, so the report needs a sentence on it (V12 "level = raw WPA" keeps only 4 of 10).
- [ ] **The batter rating doesn't hold up over time** (`outputs/time_split.csv`, `time_split_ceiling.csv`, F8, D40).
  Rated on 2022–24, it predicts 2025–26 pressure Impact at 0.01 for batters, against 0.25 for bowlers. The noise
  ceiling is about 0.52. For batters, raw pressure Impact (0.19) and the usual approach (0.23) do slightly better,
  but their intervals overlap zero. Weights were not retuned. The limitations section must say this plainly.
- [ ] **Some role effect survives the centring** (`outputs/impact_centering_check.csv`, D36). The correlation between
  a batter's role mix and his raw shift fell from 0.42 to 0.29, not to 0. State it as a limitation.
- [ ] **Thin IPL evidence among the picks** (`final_top10_*.csv`, D38): Nawaz 0 IPL pressure balls, Allen 38,
  Ngidi 71. They are eligible by the owner's all-tiers rule; the report should show the tier mix next to them.
- [ ] **High-variance and marginal picks** (`top10_*.md`, D39, D44): Sooryavanshi (87% of pressure balls in
  2026), Arya (446 balls, minimum 400) and Russell (126 pressure balls, minimum 125) are flagged. Four picks per
  list are marginal (< 50% of resamples in the top 10). #10 Russell (31%) is behind #11 Brook (34%) on that
  share. Name them in the limitations.
- [ ] **Chase-only ranks** (`top10_*.md`, D41): Arya 51st, Patidar 57th and Russell 67th of 105 batters when
  chasing; Allen has 7 chase pressure balls. Decide how much to say in the RR-fit section.

**Places where the fixes departed from this review's wording (sign-off needed)**
- [ ] Item 1: the last-ball chase ΔWP bar is "±0.5 points or 2 SE, whichever is wider". ±0.5 is below the noise of
  253 balls. Outcome frequencies are split by runs needed per ball. Result +1.94 (SE 1.06) (`wp_model_eval.md`, D35).
- [ ] Item 8: the F3 title claims only the chase middle-overs slowdown (strike rate −8). The suggested "death overs
  cost wickets, first innings shows no effect" does not hold: the death wicket gap's interval includes 0, and
  first-innings middle overs go the other way (+10.6 SR) (`pressure_validation.csv`, D42).
- [ ] Item 3: the 06 guard "|corr(rating, pressure balls)| < 0.3" now also passes when the rating's correlation is
  within 0.05 of raw usual level's. Bowlers come out at 0.309 against a raw 0.320 (D37).

**Still open from the NOTE list:** 11 (the LightGBM benchmark claim is empty), 12 (first-innings model weakness as
a limitation), 13 (keep RR fit short), 15 (check dropdown names on Unstop). Item 14 needs no action.

## Brief coverage

- Pressure definition: **covered, weak.** The first-innings rationale (7) and the last-ball WP (1) undercut it.
- Performance measurement: **covered, weak** until Impact is centred (2) and the rating scale fixed (3).
- Fair comparisons: **weak** for T20I-only players and zero associate/Emerging offsets (4).
- Evidence for the top 10: **weak.** Rank intervals (5) and match detail (9) are missing from the tables.
- Reliability and limitations: **covered** in the outputs (F7, F8, 12 variants); the wording in 5 and 6 is what makes it honest.
