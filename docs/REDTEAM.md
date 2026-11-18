# REDTEAM (round 2): judge read of reports/report.html

Reviewed 18 Nov 2026, 07:40 UTC, after fixes D45-D49. Read: the task brief (CLAUDE.md, "The task") and
`reports/report.html` (text and all 8 figures). Scored on what the report shows, not on what the repo contains.
Caveat: this reviewer also made the round-1 fixes, so it is not a truly cold read; treat the scores as
optimistic by perhaps half a point each. The round-1 review is in git history (`git show 5caaa66:docs/REDTEAM.md`).

## Scores

| Criterion | Round 1 | Round 2 |
|---|---|---|
| 1. Pressure definition | 7.5 | 8 |
| 2. Performance measurement | 7 | 7.5 |
| 3. Fair comparisons | 7.5 | 7.5 |
| 4. Evidence for the top 10 | 6.5 | 7.5 |
| 5. Reliability and limitations | 8 | 8.5 |
| 6. Clarity and reproducibility | 7 | 7.5 |
| 7. How convincing the picks are for RR | 5 | 6.5 |
| **Total** | **48.5 / 70** | **53 / 70** |

## 1. Pressure definition: 8

Good: a calibrated WP model with the formulas and coefficients on the page, leverage explained in one line,
like-for-like validation, the comparison with "death overs or RRR > 10", and a first-innings weight (0.53)
that is measured from the data, not chosen.

**Biggest weakness: section 1.4 ends by contradicting the rest of the report.** Its last sentence says
"players differ in how they respond, which is what the rating measures". Front-page finding 3 says bowlers
show no measurable difference in how they respond, and the rating is 77-87% level. The same section also
shows that first-innings "pressure" does not behave like pressure: batters score *faster* on first-innings
middle-overs pressure balls (+10.6), and the powerplay gap is not clear of zero. A careful judge sees the
definition's evidence and the rating's premise pulling apart.

**Fix (15 min):** rewrite the last two sentences of 1.4. Say the clear like-for-like effect is in chases;
first-innings pressure balls are defined by stakes (an early wicket moves the projected total most), not by a
change in behaviour, which is why they count 0.53. Replace "which is what the rating measures" with what the
rating does reward: performance on high-stakes balls, which mostly tracks a player's level.

## 2. Performance measurement: 7.5

Good: Impact (WPA ÷ stake, centred on the situation), run and wicket parts, "never the drop alone", and now
runs against par, so plain stats and Impact no longer contradict each other.

**Biggest weakness: for bowlers, "pressure level" is in practice the usual level relabelled.** The bowlers'
shift hits the 5,000-ball shrinkage cap, its effective weight is 2%, and every bowler in Figure 6 sits on
the diagonal. So Table 4 shows Ngidi (#4) with a pressure level of +7.5 while the same row shows him
conceding 15 runs per 100 pressure balls *more* than par; Hazlewood (#7) is −2 and Mustafizur (#3) +4.
A cricket judge reads that as "a pressure ranking built from non-pressure balls". The report does say this
(finding 3, the Ngidi line), but the column label says otherwise.

**Fix (30 min):** in the bowlers' components table, add raw pressure Impact (unshrunk) beside the shrunk
pressure level, and label the shrunk one "Pressure level (estimate)". Add one sentence under the bowling list
on page 1: "For bowlers the data cannot separate pressure form from usual form, so this list ranks the best
bowlers on high-stakes balls largely through their overall level." No ranking changes.

## 3. Fair comparisons: 7.5

Good: empirical-Bayes shrinkage with k on the page, the eligibility funnel, measured tier offsets kept apart
from judgment weights, recency weights, par by competition and season.

**Biggest weakness: the high-variance flag misses the picks that rest least on IPL cricket.** One constant
offset (+4.6 batters, +1.5 bowlers) covers every full-member T20I. The picks most exposed to it are Nawaz
(0 IPL pressure balls), Allen (38) and Ngidi (71). None carries the ⚑, yet the text calls Ngidi "the least
supported bowling pick". The flag rule and the prose disagree.

**Fix (30 min):** add "fewer than 75 IPL pressure balls" to the ⚑ rule (75 is already the time split's
per-period minimum). It flags exactly those three. Add an "IPL-only rank" column (variant V9, already
computed) next to "Chase-only rank". Presentation only; no ranking change.

## 4. Evidence for the top 10: 7.5

Good: a rank interval and top-10 share for every pick, runs against par, a "why" line for every pick, and
section 4.3 answering "where is X?" without hand-picking the names.

**Biggest weakness: the order invites "why him and not him?" questions the tables don't answer.** Four pairs
show the same rating with different ranks (Allen and Kohli 56.0, Iyer and Inglis 55.1, Ngidi and Bhuvneshwar
55.0, Nawaz and Ellis 54.0). The #11 batter, Russell, is top 10 in 40% of resamples, more than #9 Iyer (39%).
The report says places 9-10 are coin-flips, but only in section 5.1.

**Fix (15 min):** show ratings to two decimals on page 1 and in Tables 3-4. Add one line under the lists:
"Places 8-12 in each list cannot be told apart statistically; the order is the point estimate. Next in line:
Russell (retired from the IPL) and Abrar Ahmed (Pakistan)."

## 5. Reliability and limitations: 8.5

The strongest section: match bootstrap, a time split with a noise ceiling and now four variants, 13
sensitivity variants, and a frank limitations list.

**Biggest weakness: the report's own baselines beat the rating, and the only answer given is "we did not
retune".** For bowlers, plain usual level predicts the next period at 0.33 against the rating's 0.19; for
batters, raw pressure Impact (0.18) and the usual death-overs SR (0.20) beat the rating (0.03). A judge will
ask why the rating is better than the simpler measures it is tested against.

**Fix (20 min):** add three sentences to 5.2 making the case outright. The brief asks for a ranking of who
delivered under pressure, a description, which the time split does not test. Choosing whichever of 11
predictors scores best on about 60 players would be picking noise, since the intervals overlap. And state
how many of the top 10 the best baseline would also pick, if that number is in `outputs/`.

## 6. Clarity and reproducibility: 7.5

Good: a page 1 a judge can absorb in a minute, formulas with coefficients, a run order, a public repo link,
and a decision log.

**Biggest weakness: too long and dense for a judge working through a large pile, with no glossary.** After
page 1 come eight blocks (sections 1-6, with section 4 split in two, plus the appendix), each starting a new
page. Tables are 7-8pt and the top-10 tables pack a
4-line stats cell. The report coins several terms (Impact, LI, WPA, shift, k, pseudo-matches). "Impact" is
easily confused with the IPL's Impact Player rule, which the report also mentions. Tables are numbered
inconsistently (Table 1 in Appendix C, no Table 2, Tables 3-4, the rest unnumbered).

**Fix (30 min):** a 10-row glossary box at the start of section 2 (or the foot of page 1), with "Impact (not
the IPL Impact Player rule)". Number every table in order. Print to PDF and check the page count and that
Tables 3-4 are readable at A4.

## 7. How convincing the picks are for RR: 6.5

Good: RR's needs from its own pressure balls, where RR's players rank, routes to RR with availability notes,
and an honest statement that the lists are not a shopping list.

**Biggest weakness: section 6 never says what RR should do.** It ends with tables, and its own logic points to
answers it doesn't state:
- Retain Sooryavanshi (#1, top 10 in 99% of resamples, already at RR).
- Middle-overs top-order batting need: Kohli, Inglis, Allen and Prabhsimran fit, all only if released.
- Middle-overs pace need: only Ellis (CSK) fits in the top 15. Need fit is not assessed beyond rank 15, so
  open-market names (Daryl Mitchell, Mahedi Hasan) cannot be matched to a need at all.
- Bowling #9 Nawaz cannot be signed: a visible oddity in a list framed for an IPL auction.

**Fix:** the ONE change below.

## Other things a judge will catch (minutes each)

- The repo link reads "…/rr-superr-selector-." The trailing hyphen plus full stop looks like a typo. Drop the
  full stop, or rename the repo and the link.
- Section 6.1: "0 of them are death-overs cells" should read "none of them are".
- Section 5.2: "+0.00 to +0.43" should read "0.00 to +0.43".
- Page 1 shows Nawaz's team as "–"; show "Pakistan", as Table 4 does.
- Section 5.3 names the #1 bowler's raw pressure WPA as −0.15 without his best match. Keep it (it's honest),
  but add in the same sentence that his runs saved against par under pressure (+17) are positive.
- Hazlewood's line says "dot % rises under pressure" while his runs saved against par are −2. Add the same
  kind of explanation as Ngidi's: his place rests on wickets and level.

## Would this make the top 16 out of 10,000?

Possibly; it is now a contender rather than a long shot. On rigour and honesty it is very likely in the top
1%. Few entries will have a calibrated WP model with published coefficients, measured stakes, shrinkage,
match bootstrap, a time split with a noise ceiling and 13 variants. The fixes removed the round-1 blockers:
the batting list is now mostly chase-tested, the famous names are accounted for, and the RR section has
auction logic. What still separates it from a safe top-16 pick: a judge has to work hard to get to "so what
should RR do?", and the bowling list's "pressure" label is softer than it looks. My estimate is 25-35% (round
1: 10-20%). This is a guess; I have not seen the field or the marking scheme, and I am biased as the author of
the fixes.

## The ONE change

**Put a five-line "What this means for RR's 2027 auction" box on page 1, and back it by assessing need fit
for every eligible player, not just ranks 1-15.**

Suggested lines, every name and number taken from `outputs/`:
1. **Retain** Sooryavanshi: #1 batter, top 10 in 99% of resamples.
2. **Middle-overs top-order batting** (RR 8th of 10): Kohli, Inglis and Allen fit, if released; the best
   open-market option comes from the whole-pool need fit.
3. **Middle-overs pace** (RR 8th of 10): Ellis fits, if released; the best open-market pace option comes from
   the whole-pool fit.
4. **Pay for level, not "clutch" reputation:** for bowlers, usual level predicts later pressure form best
   (0.33); for batters, no measure does.
5. **Data-only lists:** bowling #9 Nawaz cannot play in the IPL; the next eligible bowlers are named.

This turns the lowest-scoring criterion (7) into a clear answer that a judge reads in the first minute. The
data work is extending `08_rr_fit.py`'s role cards from ranks 1-15 to the eligible pool (phase shares and
batting position already exist per ball), then writing a 5-row "best target per need, by route" table to
`outputs/`. About an hour, with no ranking change.

## Top 5 fixes, in priority order

1. **The ONE change:** a page-1 "what RR should do" box, backed by need fit across the whole eligible pool.
2. **Bowlers' pressure level** (criterion 2): add raw pressure Impact beside the shrunk level, relabel the
   column, and add one sentence on page 1.
3. **Section 1.4 contradiction** (criterion 1): rewrite its last two sentences; first-innings pressure is
   defined by stakes, not behaviour.
4. **Order and flags** (criteria 3 and 4): two-decimal ratings, a "places 8-12 are indistinguishable" line,
   and the ⚑ rule extended to fewer than 75 IPL pressure balls (Nawaz, Allen, Ngidi).
5. **Readability** (criteria 5 and 6): a glossary box, consistent table numbers, the three-sentence case in
   5.2 for the rating over simpler baselines, and a PDF check at A4.
