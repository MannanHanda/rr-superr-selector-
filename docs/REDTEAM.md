# REDTEAM (round 4): judge read of reports/report.html

Reviewed 18 Nov 2026, about 13:25 UTC, after D52–D56 (commit dd27e3e). Read: the task brief (CLAUDE.md,
"The task") and `reports/report.html`, including its figures and a 10-page A4 print. Scored on what the report
shows. Caveat: this reviewer wrote every fix since round 1, so treat each score as perhaps half a point generous.
Earlier rounds are in git: round 1 `5caaa66`, round 2 `24c3670`, round 3 `319648b`
(`git show <commit>:docs/REDTEAM.md`).

Constraint on the fixes (owner, D51): the report ranks who performs best under pressure. No fix below adds RR
recommendations, squad fit or availability content. Owner decisions already taken are not re-opened: data-only
ranking (Q1), no IPL-ball minimum (D38), single pressure shift in the headline (D56).

## Scores

| Criterion | R1 | R2 | R3 | R4 |
|---|---|---|---|---|
| 1. Pressure definition | 7.5 | 8 | 8 | 8.5 |
| 2. Performance measurement | 7 | 7.5 | 7.5 | 7.5 |
| 3. Fair comparisons | 7.5 | 7.5 | 8 | 8 |
| 4. Evidence for the top 10 | 6.5 | 7.5 | 7.5 | 8 |
| 5. Reliability and limitations | 8 | 8.5 | 8.5 | 9 |
| 6. Clarity and reproducibility | 7 | 7.5 | 8 | 8 |
| 7. How convincing the picks are for RR | 5 | 6.5 | 6.5 | 6.5 |
| **Total** | **48.5** | **53** | **54** | **55.5 / 70** |

What moved: match importance is now handled (1); the match-after-match test, the pooled knockout check and V14
in the time split strengthen 4 and 5. What held 2 back: the new run/wicket finding opened a tension the report
does not yet close (below).

## 1. Pressure definition: 8.5

Good: a WP model with coefficients, leverage in one line, a measured first-innings weight, like-for-like
validation, and a match-importance paragraph backed by data (knockout balls average LI 1.04 against 1.00).

**Biggest weakness: first-innings "pressure" is still mostly the new ball** (98% of first-over balls qualify),
and the like-for-like evidence that pressure changes outcomes sits in chases. It is handled openly (0.53 weight,
chase-only rank, V3 and V13), but a reader cannot see at a glance which picks the choice affects most.

**Fix (10 min):** add one line to 1.3 naming the picks whose pressure balls are mostly first-innings: Allen
97%, Abhishek 82%, Sooryavanshi 81%, Arya 78% and Ngidi 79%. Point to their chase-only ranks in Tables 1–2.

## 2. Performance measurement: 7.5

Good: Impact defined one way everywhere, runs against par, raw and estimated pressure Impact side by side, and
the shift tested on runs and wickets separately, as the usual level is.

**Biggest weakness: the report found a real pressure signal for bowlers, then keeps a method that cannot see it,
with half the reason on the page.** Section 3.1 says bowlers differ in run-saving under pressure (1.22 times
chance) but not in wickets. Yet three of the top four bowlers save far fewer runs against par under pressure
than usual:

| Bowler | Runs saved against par, pressure / routine |
|---|---|
| #1 Bumrah | +17 / +35 |
| #3 Mustafizur | +4 / +24 |
| #4 Ngidi | −15 / +14 |

The stated reason for keeping one total shift is that counting run-saving "does not predict 2025–26 better
(0.21 against 0.19)". That is numerically a small improvement, so the sentence reads as wrong. The stronger
reason — the split makes the bowling list less stable — is not on the page. And Ngidi's line still says
"bowlers' pressure shifts cannot be told apart from noise", which 3.1 now contradicts.

**Fix:** the ONE change below.

## 3. Fair comparisons: 8

Good: shrinkage with k on the page, the funnel, measured offsets with their direction in words, flags for thin
IPL evidence, an IPL-only rank for every pick.

**Biggest weakness (unchanged from round 3): all full-member T20Is form one tier with one offset.** Matches
against the weakest full members count the same as India v Australia. Only 6 of 10 bowlers stay top 10 on IPL
balls alone, and the four who don't lean on T20I evidence whose opposition mix is never shown: Rashid (39th),
Ellis (18th), Hazlewood (14th) and Nawaz (no IPL balls).

**Fix (45–60 min, descriptive):** for the T20I-heavy picks, show the share of their T20I pressure balls against
the stronger full members, defined from the data (for example, the top 8 by T20I win rate in the period).
Alternatively, add a sensitivity row that re-rates without T20Is against the weakest four full members.

## 4. Evidence for the top 10: 8

Good: every pick has a rank interval, runs against par, raw pressure Impact with a chance range, an IPL-only
rank, a "why" line, and now a match-after-match row.

**Biggest weakness: the weak end of the batting list is counted, never named.** Page 1 says "6 of the 10 batters
stay in the top 10 without their best pressure match", but not who doesn't. The four who drop out are Tim David
(13th), Patidar (11th, also 57th chasing), Iyer (15th) and Inglis (15th). They sit in the 5–10 range, and three
of them are already marginal. A judge has to cross-read two tables to find this.

**Fix (10 min):** name them in page 1's "Less sure" line. Add "drops to Nth without his best pressure match" to
those four "why" lines, generated from `outputs/match_consistency.csv`.

## 5. Reliability and limitations: 9

Good: match bootstrap with bands, a time split with a noise ceiling and five variants, 14 sensitivity variants,
match-after-match, a pooled knockout check and frank limitations.

**Biggest weakness: the batting list "is not a forecast", but the report never says which batting picks rest on
the most evidence.** The checks exist; they are just spread out. Three batters pass all of them: Sooryavanshi,
Abhishek Sharma and Kohli are each secure or probable, top 10 when chasing, and still top 10 without their best
match.

**Fix (10 min):** one sentence in "What we stand behind": "Three batters pass every check (secure or probable,
top 10 when chasing, still top 10 without their best match): Sooryavanshi, Abhishek Sharma and Kohli." Generate
the names from `outputs/` so they cannot drift.

## 6. Clarity and reproducibility: 8

Good: a glossary, formulas, 10 pages, numbered evidence tables, a public repo.

**Biggest weakness: page 1 and 3.1 have become harder to read.**
- **Finding 3 fuses two claims.** "Players differ in how their run-scoring and run-saving respond…", then
  "Batters do differ…" repeats it, and "does not improve (0.21 against 0.19)" reads as an error.
- **Page 1 repeats itself.** "Places 8–12 cannot be told apart" appears twice.
- **One block in 3.1 is too long.** The bowling paragraph is about 250 words in a single block.
- **Stale notes.** The "Cap" note still says bowlers' shifts show "almost no real spread"; that is true for the
  total and wicket parts, not the run part. Appendix D stops at D53 and says "four variants".
- **Mixed number format.** "0.03 to +0.43" mixes signed and unsigned numbers.

**Fix (20–30 min):**
- Rewrite finding 3 as one claim: players differ in run-scoring and run-saving under pressure, not in wickets,
  but those differences barely carry over, so level is the best guide.
- Keep one "places 8–12" line on page 1.
- Split 3.1's bowling paragraph into two short paragraphs ("taken as a whole" / "split into runs and wickets").
- Correct the Cap note.
- Extend Appendix D to D56.
- Use one number format.

## 7. How convincing the picks are for RR: 6.5

Judged on the picks as IPL pressure performers; the report deliberately gives no squad advice.

**Biggest weakness: the bowling list has no IPL-specific pressure evidence per pick.** Only 6 of 10 bowlers are
also top 10 on IPL balls alone. Rashid is 39th on IPL balls, Nawaz has none, and Ngidi has 71 IPL pressure
balls. The tables show IPL ball counts and an IPL-only rank, but not how each bowler actually performed on IPL
pressure balls.

**Fix (30 min, evidence only):** add each bowler's runs saved against par on IPL pressure balls only, as one line
in his "why" text or a column in the components table, from a small addition to the 09 tables. An RR reader can
then see the IPL pressure record directly. The deeper cost, a data-only list that includes a bowler with no IPL
balls, follows from decisions already taken and is not re-opened here.

## Would this make the top 16 out of 10,000?

Possibly; my estimate rises slightly, to about 30–35%. On rigour and transparency it is very likely in the top
1%. It is now unusually complete on the brief's own items:
- pressure, with stakes and match importance
- performance, against par and usual level
- fair comparisons
- per-pick evidence, including match after match
- reliability, from five angles

What still caps it:
1. **The bowling list's story has a visible seam.** The report finds bowlers do differ in run-saving under
   pressure, while three of its top four bowlers save fewer runs under pressure than usual.
2. **IPL evidence for bowlers is thin.** The bowling list is the weaker half on IPL-only evidence.
3. **Hedging.** Some caveats repeat, and finding 3 is hard to parse on first read.

This is a guess; I have not seen the field or the marking scheme, and I am biased as the author of the fixes.

## The ONE change

**Close the loop on the bowlers' run-saving finding, with no ranking change.**
1. **Measure the stability cost.** Run the bootstrap and the match-after-match test for the V14 lists as well
   (07 and 09 with `split_shift=True`). The report can then state the stability cost with pipeline numbers
   instead of only the forecast test. From the trial run in D56: under V14 the bowling list would be 2 secure /
   3 probable / 5 marginal (headline 2 / 5 / 3), only 4 of 10 would survive losing their best match (headline 9),
   and only 4 of 10 would be top 10 on IPL balls alone (headline 6).
2. **Show the V14 rank per pick.** Add a "Rank if run-saving shift counted (V14)" column to both components
   tables, from `outputs/sensitivity.csv`, so a reader sees exactly which picks depend on the choice.
3. **Rewrite the reasoning in 3.1 and finding 3.** "Bowlers' run-saving does change under pressure, but the
   change is small next to chance. Counting it reorders the list without predicting the next two seasons better
   (0.21 against 0.19, well within noise) and makes the list less stable (numbers above), so the headline keeps
   one shift, fixed before any ranking was seen."
4. **Fix Ngidi's line** to say "bowlers' overall pressure shifts".

Why this one: it removes the one place where the report's findings and its picks visibly disagree. It turns the
owner's D56 decision into a reasoned, evidenced choice. It also touches the brief's core phrase, "compared with
their usual level". About an hour. No ranking change.

## Top 5 fixes, in priority order

1. **The ONE change:** V14 stability numbers from the pipeline, a per-pick V14 rank column, the reasoning
   rewritten in 3.1 and finding 3, and Ngidi's line corrected. About 1 hour.
2. **Wording pass (criterion 6):** finding 3 as one claim, with "does not improve" changed to "barely changes,
   within noise"; one "places 8–12" on page 1; 3.1 split into two paragraphs; the Cap note corrected; Appendix D
   to D56; one number format. About 20–30 minutes.
3. **Name the evidence on page 1 (criteria 4 and 5):** the "Less sure" line names the batting picks who drop out
   without their best match (David, Patidar, Iyer, Inglis). Add a line naming the three batters who pass every
   check (Sooryavanshi, Abhishek Sharma, Kohli). Both are generated from `outputs/`. About 15 minutes.
4. **IPL pressure record for bowlers (criterion 7):** runs saved against par on IPL pressure balls, per bowling
   pick. About 30 minutes.
5. **T20I opposition check (criterion 3)** and the 1.3 line naming first-innings-heavy picks (criterion 1).
   About 1 hour and 10 minutes.
