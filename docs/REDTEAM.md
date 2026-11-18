# REDTEAM: cold-read judge review of reports/report.html

Reviewed 15 Nov 2026 as a first-time judge. Read only the task brief (CLAUDE.md, "The task") and
`reports/report.html` (text plus the 8 embedded figures). I read the HTML, not the printed PDF, so page
breaks and page count are not judged. Nothing was re-run; every number below is quoted from the report.

## Scores

| Criterion | Score /10 |
|---|---|
| 1. Pressure definition | 7.5 |
| 2. Performance measurement | 7 |
| 3. Fair comparisons | 7.5 |
| 4. Evidence for the top 10 | 6.5 |
| 5. Reliability and limitations | 8 |
| 6. Clarity and reproducibility | 7 |
| 7. How convincing the picks are for RR | 5 |
| **Total** | **48.5 / 70** |

## 1. Pressure definition: 7.5

Good: leverage from a calibrated WP model, out-of-fold calibration shown, last-over play-out, and a direct
comparison with "death overs or RRR > 10" (misses 54% of pressure balls). Most entrants will not get near this.

**Biggest weakness: half of all "pressure balls" are not pressure.** The cut is the top 25% within each
innings, so the first-innings cut is LI 1.04, which is an average ball. Pressure balls there have a median
LI of 1.15, 77% are in the powerplay, and 98% of first-over balls qualify. A cricket analyst will not accept
that the first over of a match is pressure in the same sense as a tight chase (median LI 2.17). The report's
own validation agrees: the only clear effect is in chases (strike rate 8.1 lower in the middle overs), while
in the first-innings middle overs batters score *faster* on pressure balls (+10.6).

The consequence shows in the batting list. Chase-only ranks of the top 10 batters are
1, 51, 29, 15, 5, 57, 3, 21, 26, 67 (of 105). Only 3 are top 10 when chasing, and 2 (Patidar, Russell)
are below the median eligible batter, with Arya (51st) just above it. Six of the ten are powerplay batters.

**Fix (under an hour, no method change):** put the chase-only rank on the front-page lists, add one line
("x of 10 batters and 6 of 10 bowlers are also top 10 on chase pressure alone"), and say plainly in 1.3 that
first-innings pressure is a weaker kind. The proper fix is the ONE change at the end.

## 2. Performance measurement: 7

Good: WPA divided by stake, centred on situation, run and wicket parts separated, "never the drop alone".

**Biggest weakness: Impact has no cricket-readable unit, and the plain stats beside it sometimes say the
opposite.** Nobody can tell what "+19.3 per 100 balls" is worth. And the rows contradict their own text:
- Kohli: "Lifts under pressure (shift +3.1)", but SR 140 / 146 and balls per dismissal 30 / 33 are both worse.
- Bumrah, #1: economy 7.45 / 7.25 and balls per wicket 30 / 18 are both worse under pressure, and his total
  pressure WPA is +0.22 wins (−0.15 without his best match).

The explanation is that the plain stats are not situation-adjusted and Impact is, but the reader is left to
work that out.

**Fix:** (a) one sentence converting Impact to runs ("+10 Impact per 100 balls is about N runs per 100 balls
in an average situation"); (b) replace or supplement the pressure / routine columns with a par-adjusted
figure using the centring cells you already have ("SR +14 v par on pressure balls", "economy −0.9 v par").

Second issue, same section: for bowlers the rating is 82% level and 2% shift, and Figure 6 shows every bowler
on the diagonal. The bowling list is "best bowlers overall". That is a legitimate finding (the data shows no
real spread in bowlers' shifts), but it is buried in a table footnote. State it as a finding.

## 3. Fair comparisons: 7.5

Good: empirical-Bayes shrinkage with k values shown, an eligibility funnel, measured tier offsets kept
separate from judgment weights, recency weights, Impact Player era handled through par.

**Biggest weakness: no floor on IPL evidence for an IPL auction list.** Mohammad Nawaz is the #9 bowler
with 0 IPL pressure balls and Finn Allen the #9 batter with 38. Their ratings rest on one constant T20I
offset (+4.6 batters, +1.5 bowlers) that treats every full-member T20I alike. The IPL-only variant (V9)
changes 3 batters and 4 bowlers, one of the three largest changes among the 12 variants.

**Fix:** add an "IPL-only rank" column next to "Chase-only rank" (V9 is already computed) and a
"low IPL evidence" flag on the front page. Decide separately whether to add a minimum such as 60 IPL
pressure balls; it is currently a rejected alternative (D38), so it needs a decision-log entry either way.
Also state the direction of the offset in words ("T20I batting is worth 4.6 less than the same Impact in the
IPL"); "taken off every ball" leaves the sign unclear.

## 4. Evidence for the top 10: 6.5

Good: every pick has rank interval, sample, plain stats, a reason, and a component breakdown.

**Biggest weakness: the tables never answer the judge's first question, "where is X?"** There is no
Suryakumar (18th), Travis Head (17th), Jaiswal, Buttler, Pooran, Arshdeep, Chahal, Varun (12th) or
Kuldeep (16th), and no explanation. The brief says "not reputation alone"; the strongest way to show that is
to name the reputations the data overruled, and why.

**Fix:** a "Ten names you might expect" table: rank, pressure level, shift, top-10 share, and a one-line
reason. All of it is in `outputs/ratings_*.csv` and the bootstrap files.

Also in this section: some rows argue against their own pick. Lungi Ngidi (#8) has pressure WPA of −0.64
wins, is 102nd of 109 on consistency, concedes 8.97 on pressure balls and has 71 IPL pressure balls. The
brief asks for players who deliver "most consistently". Harry Brook (#11) is top 10 in 34% of resamples,
more than Russell at #10 (31%). Neither is explained beyond "marginal".

## 5. Reliability and limitations: 8

The best section. Match bootstrap with rank intervals, a time split reported with a noise ceiling, twelve
variants, and a limitations list that hides nothing.

**Biggest weakness: the time split says more than the text admits.** For batters the rating predicts the
next period at +0.01, and the "usual approach" the report dismisses on page 1 does better (0.23). For
bowlers the usual approach (0.31) also edges the rating (0.25). Raw shift (0.22) beats shrunk pressure
level (0.00) for batters, which is the opposite of the 60/15 weighting. All of this is within noise at
n = 60, but a judge reading Figure 8 sees the headline rating as the worst bar in the batting panel, and
the brief is about an auction, which is a forecast.

**Fix:** run the same time split on variants already built (V3 chase-only cut, V4 level only, V12 raw WPA)
and add them to Figure 8. If chase-weighted pressure persists better for batters, that is the evidence for
the ONE change below. If nothing persists, say so once in 5.2 and add the sentence that follows from it:
"for batters, buy the level, not the clutch reputation".

## 6. Clarity and reproducibility: 7

Good: a front page a judge can absorb in a minute, one message per chart, a run order, a decision log.

**Biggest weakness: the repository link is an unfilled placeholder.** Appendix A reads
"Code and decision log: {{REPO_URL}}". The reproducibility claim points nowhere, and it looks unfinished.
Without the code, the WP model cannot be rebuilt from the text: the two regressions are described in
words, with no formula or coefficients, and "expected-runs curve" is never defined.

**Fix:** fill the link (or attach the code) and add a three-line formula box in 1.1 with the fitted
coefficients. Also: body text is 9pt and the top-10 tables 7.2pt, which is hard going on a laptop.

## 7. How convincing the picks are for RR: 5

**Biggest weakness: section 6 is a lookup table, not an auction view.**
- No availability. Bumrah, Kohli, Klaasen and Narine are unlikely to reach an auction. Nawaz and alternate
  Abrar Ahmed are Pakistan players, who have not played in the IPL since 2008. Russell has, I believe,
  retired from the IPL (verify). Brook, the first alternate, should be back in the 2027 pool after his ban
  (verify). None of this is mentioned.
- RR's own players are not ranked, though Parag (16th) and Archer (18th) appear in Figure 7.
- 9 of 10 bowlers show "–" against RR need. There is no death-overs cell at all.
- Sooryavanshi "fills" a need that RR has with him already in the side. Nathan Ellis is called a death
  bowler and a fit for "middle-overs pace" in the same sentence (31% of his balls are in the middle).

**Fix:** replace the two long tables with a half-page box: (a) where every current RR player ranks;
(b) three or four realistic targets from the top 20, by need, each with an availability note;
(c) one sentence that the lists are data-only and include players RR cannot sign. Remove the "fills" tag
for the player already at RR.

## Other things a judge will catch (minutes each)

- Top-10 bowlers all have consistency below 50% (40 to 49). Without the pool rate beside it, "43%" for the
  best bowler looks like a failure. Show it as a difference from the pool rate, and say why bowlers sit
  below 50.
- Consistency (25% nominal weight) is the sign of raw pressure WPA, which section 5.3 says is "dominated by
  a handful of last-over balls". The report undermines one of its own components.
- "Secure" is attached to two batters who also carry the high-variance flag (Sooryavanshi on one season,
  Arya with a 1–29 interval). Say in the legend that "secure" means stable under resampling, not deep evidence.
- Table numbering: Tables 3 and 4 in the body, Table 1 in the appendix, no Table 2, others unnumbered.
- "Chase-only rank" in the bowler table means "defending a target". Rename the column.
- Front-page finding 3 tells a skimming judge "the batting list is not a forecast". Keep the honesty in
  section 5; lead the front page with what the method does establish.

## Would this make the top 16 of 10,000?

Not as it stands; it is borderline. On rigour it is very likely in the top 1 to 2%: few entrants will have a
calibrated WP model, leverage, shrinkage, bootstrap intervals and a time split. But 16 of 10,000 is the top
0.16%, and at that level reports are separated by whether a cricket analyst believes the lists and whether
the RR section reads like advice. My estimate is a 10 to 20% chance now and perhaps 25 to 35% with the fixes
below. This is a guess: I have not seen the field or the marking scheme.

What holds it back, in order:
1. A batting list that is mostly first-innings powerplay hitters, three of whom are below-median chasers.
2. A batting rating that, by its own test, does not predict and is matched by the baseline it criticises.
3. A handful of picks a cricket judge will query on sight (Ngidi, Nawaz, Russell, Arya at #2 on 184 balls).
4. An RR section with no auction logic.

## The ONE change

**Make chase pressure carry more of the batting rating than new-ball first-innings "pressure".**

Today a first-innings ball at LI 1.1 counts the same as a chase ball at LI 2.2. Weight the two innings by
their stakes when forming the pressure level (for example by median pressure LI, about 35 : 65), shrink each
separately, keep the current version as a sensitivity variant, and log the decision before looking at who
moves. Then re-run the time split. This fixes the definition (criterion 1), probably moves Arya, Patidar,
Allen and Russell down and proven chasers up (criterion 4 and face validity), and may give the batting
rating some persistence (criterion 5). It is more than an hour once the report is rebuilt; the one-hour
version is the front-page chase-only rank described under criterion 1.

## Top 5 fixes, in priority order

1. Chase-weight the batting pressure level (the ONE change), or at minimum show chase-only rank on page 1.
2. Add the "names you might expect" table and RR's own players' ranks.
3. Rewrite section 6 as an auction box with availability notes (retained stars, Nawaz, Russell, Brook).
4. Run the time split on existing variants, add to Figure 8, and reword front-page finding 3.
5. Hygiene: fill `{{REPO_URL}}`, add the WP formula box, explain bowler consistency below 50%, fix the
   Kohli and Bumrah rows with a par-adjusted plain metric, and explain or flag Ngidi.
