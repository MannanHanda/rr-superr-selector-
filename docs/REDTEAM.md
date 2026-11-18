# REDTEAM (round 3): judge read of reports/report.html

Reviewed 18 Nov 2026, about 11:20 UTC, after D50–D51 (commit 24c3670). Read: the task brief (CLAUDE.md,
"The task") and `reports/report.html`, including all 8 figures and an 11-page A4 print. Scored on what the
report shows. Caveat: this reviewer wrote the round-1 and round-2 fixes, so read every score as perhaps half a
point generous. Earlier rounds: `git show 5caaa66:docs/REDTEAM.md` (round 1) and
`git show 24c3670:docs/REDTEAM.md` (round 2).

Constraint on the fixes (owner, D51): the report ranks who performs best under pressure. No fix below adds RR
recommendations, squad fit or availability content.

## Scores

| Criterion | Round 1 | Round 2 | Round 3 |
|---|---|---|---|
| 1. Pressure definition | 7.5 | 8 | 8 |
| 2. Performance measurement | 7 | 7.5 | 7.5 |
| 3. Fair comparisons | 7.5 | 7.5 | 8 |
| 4. Evidence for the top 10 | 6.5 | 7.5 | 7.5 |
| 5. Reliability and limitations | 8 | 8.5 | 8.5 |
| 6. Clarity and reproducibility | 7 | 7.5 | 8 |
| 7. How convincing the picks are for RR | 5 | 6.5 | 6.5 |
| **Total** | **48.5** | **53** | **54 / 70** |

Criterion 7 is now judged on whether the picks convince as IPL pressure performers, since the report
deliberately gives no squad advice.

## 1. Pressure definition: 8

Good: a WP model with formulas and coefficients on the page, leverage in one line, a first-innings weight
(0.53) measured from the data, like-for-like validation, and 1.4 now agrees with finding 3.

**Biggest weakness: match importance is missing.** Knockouts, finals and World Cup games are never mentioned.
Pressure is entirely in-match leverage, so a league game and a final with the same scoreboard carry the same
pressure. "Which situations?" is the first thing a cricket judge checks, and "what about knockouts?" is the
obvious follow-up. The first-innings issue ("pressure" is mostly the new ball) is still there, but the report
now handles it openly with the 0.53 weight, the chase-only rank and variants V3 and V13.

**Fix (30–45 min):** a short paragraph in 1.3 saying why tournament stakes are not part of LI: LI measures how
much one ball can swing this match, and a knockout raises the cost of losing, not the swing of a ball. Give the
number of knockout matches in the data. If the numbers allow, add a small descriptive table of the top 10's
pressure Impact in knockout matches, labelled as too small to rank on. It needs a small script, since every
number must come from `outputs/`.

## 2. Performance measurement: 7.5

Good: Impact (WPA ÷ stake, centred on the situation), runs against par, the raw and estimated pressure figures
side by side, and "never the drop alone".

**Biggest weakness: the finding that shapes the whole bowling list rests on a test that mixes runs and
wickets.** Section 3.1 shrinks the usual level's run and wicket parts separately "because wickets take far
longer to settle" (bowlers: k = 255 balls for runs, 980 for wickets), but the pressure shift is shrunk on total
Impact. The wicket part's noise could hide a real difference in run-saving under pressure. If so, "bowlers show
no measurable difference" (finding 3, and the reason the bowling list ranks on level) is an artefact of how the
test was set up. A statistician on the panel can see this from 3.1 alone.

**Fix (15 min to test; adopting it is the owner's call):** estimate the between-bowler spread (τ²) of the
run-part shift alone, as is already done for the total.
- If it is at or below zero, add one clause to 3.1: "tested on runs and wickets separately; neither shows a
  spread beyond chance". The headline finding gets stronger.
- If it is clearly above zero, splitting the shift the way the usual level is split is a method change that
  re-ranks both lists. Adopt it only with at least 2 hours left to re-check the lists, the "why" lines and the
  dropdowns. Otherwise state it in 5.4 as an open question.

## 3. Fair comparisons: 8

Good: shrinkage with k on the page, the eligibility funnel, measured offsets kept apart from judgment weights,
flags that now catch thin IPL evidence, and an IPL-only rank for every pick.

**Biggest weakness: all full-member T20Is form one tier with one constant offset**, so matches against the
weakest full members count the same as India v Australia. This matters most for the bowling list: on IPL balls
alone (V9) only 6 of the 10 bowlers stay top 10. The four who drop out lean on T20I evidence whose opposition
mix is never shown: Rashid (39th on IPL balls alone), Ellis (18th), Hazlewood (14th) and Nawaz (no IPL balls).

**Fix (45–60 min, descriptive, no ranking change):** for the T20I-heavy picks, show the share of their T20I
pressure balls against the stronger full members, with "stronger" defined from the data (for example, the top 8
full members by T20I win rate in this period). Alternatively, add a sensitivity row that re-rates without T20Is
against the weakest four full members.

## 4. Evidence for the top 10: 7.5

Good: a rank interval, top-10 share, runs against par, raw pressure Impact and a "why" line for every pick, and
section 4.3 answering "where is X?" without hand-picked names.

**Biggest weakness: for bowlers, every rank column measures level.** Pressure level, chase-only rank and
IPL-only rank are all built on the shrunk estimate, which for bowlers sits close to usual level (3.1). The only
pressure-specific evidence in Table 2 is raw pressure Impact, runs against par and the plain stats. For #1
Bumrah those are mixed:
- raw pressure Impact −0.0 ± 5.3, against +11.8 usual
- 30 balls per wicket under pressure, against 18 on routine balls
- 74th of 109 on consistency
- but +17 runs saved per 100 pressure balls against par

A cricket judge reading Table 2 will ask why he is #1 under pressure. The answer is in 3.1, two sections
earlier, not in his row.

**Fix (15 min):** put the answer in his row: "first on level; on pressure balls he concedes little (+17 runs
saved against par) but takes fewer wickets (30 balls per wicket against 18), a gap of the size chance produces
about 3 times among 109 bowlers". Add to the Table 2 caption: "for bowlers, chase-only and IPL-only ranks also
rest mainly on usual level".

## 5. Reliability and limitations: 8.5

Good: match bootstrap with confidence bands, a time split with a noise ceiling and four variants, 13
sensitivity variants, the case for the rating over simpler measures, and a frank limitations list.

**Biggest weakness: the brief's key word, "consistently", is the least-evidenced idea per pick.** "Consistency
across matches" is a named brief item, and the brief asks for the players who "deliver most consistently when
it matters". Per pick, the report offers only the rank interval and a pointer to
`outputs/top10_match_detail.csv`. The consistency component is built on raw WPA, which 5.3 itself calls
"dominated by a handful of last-over balls". Its effective weight is 11–13%, and the bowling picks sit at
42–48% against a 44% average (Bumrah 74th, Ngidi 98th). A judge looking for "who delivers match after match"
cannot find a per-pick answer in the report.

**Fix:** the ONE change below.

## 6. Clarity and reproducibility: 8

Good: a glossary, formulas with coefficients, numbered evidence tables, a public repo, a run order, 11 pages.

**Biggest weakness: two definitions on the page are wrong or inconsistent.**
- **Impact.** The glossary says "WPA ÷ LI", where LI is the normalised leverage (average ball = 1). But 2.1
  divides by "leverage of the ball", which 1.2 defines as the spread of possible WP changes, in WP points. The
  two differ by a constant factor, so a reader cannot tell which one produced "+20 per 100 balls" and the ±6
  cap. The cap only makes sense for the spread, so the glossary is the one to fix.
- **Consistency.** Page 1 calls it the "share of pressure matches won for the team", and Iyer's line says "won
  for his side". It is the share of pressure matches in which the player's WPA on pressure balls was positive,
  not matches won.

**Fix (15 min):** define Impact once, the same way everywhere: "WPA ÷ the ball's leverage (the spread of
possible WP changes, in WP points)". Replace "won for the team/his side" with "in which he added win
probability". While there, remove the forced page breaks that leave pages 4, 8 and 10 half empty, which takes
the report to about 9 pages.

## 7. How convincing the picks are for RR: 6.5

Judged on the picks as IPL pressure performers. Good: names you might expect, IPL pressure balls per pick, ⚑
flags and IPL-only ranks.

**Biggest weakness: the bowling list is the weaker half for an IPL reader.**
- Only 6 of the 10 bowlers are also top 10 on IPL balls alone.
- #4 Ngidi is called "the least supported bowling pick" in his own row (15 runs per 100 above par under
  pressure, 71 IPL pressure balls).
- #9 Nawaz has no IPL balls.

The batting list holds up better (8 of 10 are also top 10 on IPL balls alone), but three of its picks are
mainly new-ball, first-innings batters with weak chase records: Arya (51st chasing), Patidar (57th) and Allen
(97% first-innings, 38 IPL pressure balls).

**Fix (10 min, evidence only):** add one sentence on page 1: "8 of the 10 batters and 6 of the 10 bowlers are
also top 10 on IPL balls alone; the other picks lean on T20I evidence (flags and IPL-only ranks in Tables
1–2)". Name the IPL-only rank in the Rashid, Ellis and Hazlewood lines. The deeper cost is a data-only list that
includes a bowler with no IPL balls. That follows from decisions the report already states (data-only ranking,
Q1; no IPL-ball minimum, D38) and is not re-opened here.

## Other things a judge will catch (minutes each)

- Page 1 says "Places 8–12 in each list cannot be told apart". The "How sure we are" line and 5.1 say "places
  9–10 are close to coin-flips against 11–12". Pick one.
- Section 3.3 never states the offset's direction in words, for example: "the same batters score 4.6 Impact per
  100 balls more in full-member T20Is than in the IPL, so 4.6 is taken off".
- Appendix D stops at D45. It doesn't summarise D46–D51: the names table, the time-split variants, the raw-Impact
  display, and the removal of the RR section.
- About a third of page 1 is empty. That is room for one small figure (F6 or F7) if wanted, since judges skim
  page 1 first.
- Accuracy note, not visible to a judge: 3.1 says "over a typical 251 pressure balls … ±6.7". 251 is the raw
  median count, but ±6.7 was computed on the median weighted (effective) sample, which is smaller. Say "over a
  typical bowler's weighted sample", or quote the effective count.

## Would this make the top 16 out of 10,000?

Possibly; my estimate stays at 25–35%. On rigour and transparency it is very likely in the top 1%. Few entries
will publish a calibrated WP model with coefficients, measured stakes, shrinkage, a match bootstrap, a time
split with a noise ceiling and 13 variants.

What still caps it:
1. **The bowling list ranks level.** By the report's own finding, its pressure-specific evidence is thin, and
   the #1 bowler's pressure-ball record is average in Impact terms.
2. **"Consistently" is under-evidenced.** It is the brief's key word, and the least-evidenced idea per pick.
3. **Three batting picks are new-ball, first-innings batters** who rank low when chasing.
4. **The narrative undercuts itself without saying what it stands behind.** It is full of honest caveats: "the
   least supported bowling pick", "not a forecast", "cannot be told apart", "no measurable difference". That
   rigour is a strength, but page 1 should also say once, plainly, what the report *is* confident about. For
   example: four picks are top 10 in over 90% of resamples; 5 batters and 8 bowlers are top 10 under at least
   10 of 13 versions of the method; and Sooryavanshi, Abhishek Sharma, Kohli and Iyer are top 10 when chasing as
   well.

## The ONE change

**Show, per pick, that he delivers match after match.** Add one compact table (or dot chart) in 5.1 and one
sentence on page 1. For every top-10 pick, plus #11–12, show:
1. **His rank with his single best pressure match removed**, all other players unchanged and priors and k held
   fixed, as in the bootstrap.
2. **The share of his pressure matches with positive Impact**, against the pool average. This gives an
   Impact-based view of consistency alongside the WPA-based component.
3. **His best match's share of his total pressure Impact.**

The page-1 sentence would read: "N of the 10 batters and M of the 10 bowlers stay in the top 10 without their
best pressure match."

Why this change: it answers the brief's key phrase directly, per pick, with a test any cricket judge
understands ("not a one-match wonder"), and it changes no ranking. It takes about an hour, because the bootstrap
in `07_reliability.py` already holds per-player, per-match sums, so removing one match is a small change to
those sums.

Gate: if some picks drop out of the top 10 without their best match, say so plainly. That is still the honest
answer to "most consistently".

## Top 5 fixes, in priority order

1. **The ONE change:** per-pick match-after-match evidence (rank without the best match, Impact-based match
   share, best-match share) and a page-1 sentence. About 1 hour; no ranking change.
2. **Accuracy (criterion 6):** Impact defined the same way in the glossary, 1.2 and 2.1; "won for the team/his
   side" replaced; the offset direction stated in words; "8–12" and "9–10" aligned. About 15 minutes.
3. **Bowler evidence in the rows, plus page 1 (criteria 4 and 7):**
   - Bumrah's line explains his pressure-ball record.
   - The Table 2 caption says bowlers' chase-only and IPL-only ranks rest on level.
   - The Rashid, Ellis and Hazlewood lines give their IPL-only rank.
   - Page 1 gets the IPL-only overlap sentence and a positive "what we stand behind" line.

   About 30 minutes.
4. **Match importance (criterion 1):** a paragraph on why knockouts are not part of LI, with the count of
   knockout matches, plus a descriptive knockout table for the top 10 if the numbers allow. About 30–45 minutes.
5. **Shift test and layout (criterion 2):** test the run and wicket parts of the shift separately (15 minutes).
   It either strengthens finding 3 in one clause or raises a method question for the owner. Also remove the
   forced page breaks (10 minutes).
