# REDTEAM (round 5): judge read of reports/report.html

Reviewed 18 Nov 2026, about 13:45 UTC, after D57–D61 (commit ccc5ccd). Read: the task brief (CLAUDE.md,
"The task") and `reports/report.html`, including its figures and a true-size A4 print (16 pages). Scored on what
the report shows. Caveat: this reviewer wrote every fix since round 1, so read each score as perhaps half a point
generous. Earlier rounds are in git: round 1 `5caaa66`, round 2 `24c3670`, round 3 `319648b`, round 4 `f3e9314`
(`git show <commit>:docs/REDTEAM.md`).

Constraint on the fixes (owner, D51): the report ranks who performs best under pressure. No fix below adds RR
recommendations, squad fit or availability content. Owner decisions already taken are not re-opened: data-only
ranking (Q1), no IPL-ball minimum (D38), and one pressure shift in the headline, with the split kept as V14 (D56).

## Scores

| Criterion | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| 1. Pressure definition | 7.5 | 8 | 8 | 8.5 | 8.5 |
| 2. Performance measurement | 7 | 7.5 | 7.5 | 7.5 | 8 |
| 3. Fair comparisons | 7.5 | 7.5 | 8 | 8 | 8.5 |
| 4. Evidence for the top 10 | 6.5 | 7.5 | 7.5 | 8 | 8 |
| 5. Reliability and limitations | 8 | 8.5 | 8.5 | 9 | 9 |
| 6. Clarity and reproducibility | 7 | 7.5 | 8 | 8 | 8 |
| 7. How convincing the picks are for RR | 5 | 6.5 | 6.5 | 6.5 | 6.5 |
| **Total** | **48.5** | **53** | **54** | **55.5** | **56.5 / 70** |

What moved:
- **Criterion 2:** the V14 decision is now reasoned with pipeline numbers and a per-pick V14 rank.
- **Criterion 3:** the T20I opposition check is in.

What held 4 and 7: the report is now so transparent about the bowling picks that a quick reader sees a column of
doubts without the report's answer to them alongside. That answer exists in 5.2, but nowhere near Table 2.

## 1. Pressure definition: 8.5

Good: the WP model with coefficients, leverage, a measured first-innings weight, match importance backed by data,
and the first-innings-heavy picks named.

**Biggest weakness: the behavioural evidence is narrow.** The like-for-like test shows pressure changing play
clearly in one cell, chase middle overs (−8.1 SR), plus a borderline powerplay effect. Everywhere else, pressure
is defined by stakes, not shown to change behaviour. That is stated honestly, but finding 2 rests on a single
cell.

**Fix (30 min, only if it holds):** pool the like-for-like chase estimate across phases, with precision weights,
as F3 already does within cells. If its interval clears zero, lead finding 2 with that one number; if it does
not, leave finding 2 as it is.

## 2. Performance measurement: 8

Good: Impact defined one way everywhere, runs against par, and the shift tested on runs and wickets, with V14's
stability cost shown.

**Biggest weakness: two "consistency" measures sit side by side without explanation.**
- **The rating's component** is WPA-based. Its eligible averages are 51% (batters) and 44% (bowlers).
- **The 5.1 test** uses positive-Impact matches. Its averages are 55% and 44%.

The brief's key word is "consistently", and a reader cannot tell why there are two measures. Nor can they tell
why the one in the rating uses raw WPA, which 5.3 calls "dominated by a handful of last-over balls".

**Fix (10 min):** add one sentence to 5.1. The component counts matches in which the player added win
probability, an outcome view; the 5.1 share counts matches with positive Impact, the situation-adjusted view used
everywhere else. Showing both lets a reader check that the picks hold up either way.

## 3. Fair comparisons: 8.5

Good: shrinkage, the funnel, offsets with their direction, flags, IPL-only rank and runs against par, and an
opposition check that names the weakest full members from the data.

**Biggest weakness: the opposition check finds a problem and stops there.** Rashid Khan has 42% of his
full-member T20I pressure balls against Ireland and Zimbabwe, against an 11% pool average. A reader cannot tell
whether removing those matches would change anything. It is the same "found it, didn't act" pattern that V14
closed for run-saving.

**Fix (30–40 min, no ranking change):** add variant V15, which re-rates without full-member T20Is against the two
weakest sides. Report its top-10 overlap and Rashid's (and Mustafizur's) V15 rank in 3.3. This needs the
batting/bowling team ids in `lib_rating.BALL_COLS` and one filter in `build_pms`.

## 4. Evidence for the top 10: 8

Good: every pick has a rank interval, runs against par, IPL-only runs against par, raw pressure Impact with its
chance range, an IPL-only rank, a V14 rank, a match-after-match row and a "why" line.

**Biggest weakness: Table 2 reads as a list of doubts about the bowling picks.**
- Bumrah: raw pressure Impact −0.0; V14 rank 9th.
- Mustafizur: −30 on IPL pressure balls.
- Ngidi: −15 runs against par on pressure balls; V14 rank 35th.
- Rashid: 42% of his T20I pressure balls against the weakest sides.
- Hazlewood: −10 on IPL pressure balls.
- Nawaz: no IPL balls.

Table 2's own note tells the reader that "the pressure-specific evidence is in the raw pressure Impact, the runs
saved against par and the plain stats". That invites the reader to judge the picks on exactly those columns. The
report's answer is in 5.2, four pages later: a bowler's usual level predicts his next two seasons under pressure
(0.33) better than his past pressure record does (raw pressure Impact 0.14).

**Fix:** the ONE change below.

## 5. Reliability and limitations: 9

Good: bootstrap bands, a time split with a ceiling and five variants, 14 sensitivity variants, match-after-match
for both the headline and V14, a pooled knockout check, and frank limitations.

**Biggest weakness: a few sentences have not caught up with the new evidence.**
- **5.3** lists the "biggest changes" as V3, V12, V7 and V9. For bowlers, V14 changes the ranking more than V9
  (rank correlation 0.80 against 0.85).
- **The limitations** still say opposition is "only handled through competition tiers"; 3.3 now checks it.
- **3.4's opposition bullet** says the same.
- **Appendix D** stops at D57.

**Fix (10 min):** add V14 to the bowlers' "biggest changes"; point the opposition bullet and the limitation to the
3.3 check; extend Appendix D to D61.

## 6. Clarity and reproducibility: 8

Good: a glossary, formulas, numbered evidence tables, a true-size print where every table fits A4, a public repo.

**Biggest weakness: the reading load before the evidence.**
- **"How to read the tables" is one block of about 200 words** with nine definitions (rank interval, ⚑, IPL-only
  rank, V14 rank, raw pressure Impact ± chance, runs v par, IPL only…). A judge must parse all of it before
  Table 1.
- **Page 8 is about 85% empty,** because section 4 is forced onto a new page after a short 3.4.

**Fix (20 min):**
- Turn "How to read the tables" into a two-column key (term | meaning), one line each.
- Drop the forced page break before section 4. Table rows already avoid splitting, so this saves a page.

## 7. How convincing the picks are for RR: 6.5

Judged on the picks as IPL pressure performers; the report deliberately gives no squad advice.

**Biggest weakness: the bowling picks' IPL pressure record is mixed, and Rashid's row sends two signals at
once.**
- Four bowling picks are below par on IPL pressure balls: Mustafizur −30, Hazlewood −10, Ellis −8 and Ngidi −5.
  Nawaz has no IPL balls.
- Rashid's line says he is "39th on IPL balls alone, so his place leans on T20I evidence". Yet his IPL-only runs
  against par are +21 on pressure balls against −1 on routine balls. An IPL reader sees a strong IPL pressure
  record and a weak IPL-only rank, with no explanation.

**Fix (10 min, evidence only):** in Rashid's line, say why the two differ. On IPL balls alone, his routine overs
are below par, which pulls his IPL-only rating down. On IPL pressure balls, he saves 21 runs per 100 against par.
The rest of this criterion is covered by the ONE change: the reason the ranking leans on level, placed where the
bowling doubts appear.

## Would this make the top 16 out of 10,000?

Possibly; my estimate stays at about 30–35%. The report is now unusually complete and self-critical. Every brief
item has evidence, per pick, from several angles, and every number is traceable.

Report polish is now at diminishing returns. What separates it from a safe top-16 pick is mostly outside the
report's control: how the panel weighs a level-led bowling list and a batting list that "records who has
delivered" against lists that read more like "clutch" picks. After this round, the best use of time is:
1. the fixes below, especially the ONE change
2. then stop, print, enter the dropdowns and submit with margin before 18:29

This is a guess; I have not seen the field or the marking scheme, and I am biased as the author of the fixes.

## The ONE change

**Put the report's answer next to the bowling doubts.** Replace the note under the "Table 2" heading with
something like:

> How to read the bowlers' table. A bowler's pressure-ball record is short (a median of 251 pressure balls) and
> noisy: by chance alone, raw pressure Impact moves about ±6.7 per 100 balls and runs against par about ±18 per
> 100 balls over 100 balls. Rated on 2022–24, a bowler's usual level predicts his 2025–26 pressure form better
> (0.33) than his own past pressure record does (raw pressure Impact 0.14). So the ranking leans on level, and the
> pressure-specific columns (raw pressure Impact, runs saved against par, IPL only, V14 rank) show where a pick's
> pressure record is weak. Read them with their chance ranges.

Generate every number from `outputs/` (`ts.bowl_ulevel`, `ts.bowl_raw`, `eb.bowl_P_se_median`,
`ipl.bowl_rae_se100`, `pool.bowl_median_pressure_balls`). Add one clause to the page-1 legend: "…ranks largely on
level, which predicts a bowler's next two seasons under pressure better than his past pressure record does (5.2)".

Why this one: it turns six visible doubts into an argued design choice, at the point where a judge forms an
opinion of the bowling list. It changes no number and no rank. About 15–20 minutes.

## Top 5 fixes, in priority order

1. **The ONE change:** the bowlers' reading note under Table 2, and the page-1 legend clause. About 15–20 minutes.
2. **Rashid's line (criterion 7):** explain the weak IPL-only rank against his strong IPL pressure runs. About 10
   minutes.
3. **Layout and stale lines (criteria 5 and 6):**
   - Turn "How to read the tables" into a key.
   - Drop the forced page break before section 4.
   - Add V14 to the bowlers' biggest changes in 5.3.
   - Point the opposition limitation and the 3.4 bullet to 3.3.
   - Extend Appendix D to D61.

   About 30 minutes.
4. **Close the opposition loop (criterion 3):** V15, re-rating without full-member T20Is against the two weakest
   sides, with its overlap and Rashid's V15 rank. About 30–40 minutes.
5. **Two consistency measures (criterion 2):** one sentence in 5.1 on why both appear. Optionally, a pooled
   like-for-like chase estimate for finding 2 (criterion 1), used only if its interval clears zero. About 10–40
   minutes.

After these: stop, print at true size (16 pages, or 15 once the page break goes), enter the dropdowns, submit.
