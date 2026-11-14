MODEL: Fable. Paste everything below the line into Claude Code.
---

You are the lead analyst on this project. Your job in this session is DESIGN ONLY. You write the methodology
spec that another model (Opus) will implement over the next two days. Do not write pipeline code in this session.

## Read first (in this order, nothing else yet)
1. CLAUDE.md: the brief, our strategy, the data dictionary and the known data issues
2. DECISIONS.md: decisions already made, plus open questions Q1 and Q2
3. outputs/data_quality.md: coverage and data issues

Do NOT open the raw CSVs. If you need numbers to make a design choice (for example, how many players would pass a
given eligibility threshold), you may run short Python queries against data/processed/*.parquet. Keep each
query's printed output under about 30 lines. Run at most about 8 such queries in total; this session should be
spent on thinking, not exploring.

## Context you must design for
- Deadline Wed 18 Nov 18:29 GMT. Implementation happens Sun 15 to Mon 16, and the report is written Tue 17.
  One student builds it, with Claude Code. Design something that can be built and checked in about 1.5 days.
- More than 10,000 entrants and 16 places. Most entrants will define pressure as death overs plus a high
  required rate, then sort by strike rate and economy. We win on rigour, evidence and clarity, not complexity.
- The judges are cricket analysts. Every metric must be explainable in one sentence to a cricket person.
- The method must handle both innings, and both batting and bowling.

## Write docs/METHODOLOGY_SPEC.md with exactly these sections

### 1. Pressure definition
- Win-probability (WP) model. Specify:
  - features (balls remaining, wickets in hand, runs needed / required rate in a chase, a first-innings
    equivalent such as projected total vs a par score, competition tier, era/year)
  - model type, with a clear recommendation, for example logistic regression with splines versus LightGBM
    with monotonic constraints
  - training rows (use_for_model == True), and how to split train/test by match so there is no leakage
  - calibration checks and what "good enough" means
  - how the first innings is handled, since there is no target yet
- Leverage per ball: the exact formula. For example, the spread of WP change across the possible outcomes of a
  ball, weighted by league outcome frequencies in that state, normalised so the average ball = 1.0.
- How continuous leverage becomes "pressure balls": a threshold or tiers, and how to justify the cut.
- The validation test: what evidence shows that high-pressure balls really are different across the league
  (for example dot %, dismissal rate and run rate by leverage band, compared with phase alone). Name the exact
  chart or table.
- How the 4 DLS games without a revised_target, ties and super overs are handled.

### 2. Performance measurement
- Batting metrics and bowling metrics, each with a formula. Include context-adjusted ones (WPA per ball,
  runs above expected, where expected comes from league rates in the same state) and plain ones (strike rate,
  economy, dot %, boundary %, dismissal rate).
- Player baseline: what "usual performance" means, so we can compare pressure with non-pressure balls.
- The final reliability rating: the exact formula combining pressure performance, the drop from baseline,
  and match-to-match consistency, with weights and the reasoning for them. Explain why ranking on the drop alone
  is wrong.

### 3. Fair comparisons
- Empirical Bayes shrinkage: which quantities get shrunk, toward what prior, and how the prior is estimated.
- Eligibility thresholds for batters and bowlers, set from the actual data (show the numbers you checked).
  Target a pool of roughly 60–120 eligible players per list.
- Competition-tier weights (IPL / T20I_full / T20I_associate / Emerging), and how they are justified.
  Is there a data-driven option, such as comparing the same players' rates across tiers?
- Recency weighting for an IPL 2027 auction: the decay form and parameter.
- Opposition strength: adjust for it or not? Decide, and say why.

### 4. Reliability checks
- Bootstrap (resampling matches) to get a rank interval for every top-20 player. Give the number of resamples.
- Time-split test: does pressure performance in 2022–24 predict 2025–26? What do we report if the correlation
  is weak? (Be honest. It is a finding either way.)
- Match-level consistency: the share of a player's pressure matches with positive WPA, or similar.
- Sensitivity check: do the top 10 survive reasonable changes to the threshold and weights? Which variants?

### 5. RR fit (short section)
- How we describe each pick's role (phase, batting position, pace or spin, batting hand) and match it to RR's
  IPL 2026 pressure weaknesses from the data.
- Answer open questions Q1 and Q2 from DECISIONS.md.

### 6. Report plan
- Outline of a 10–12 page PDF that maps one-to-one to the five sections the brief requires.
- The list of figures and tables, each with a one-line purpose. Aim for about 8 figures. The best ones prove a
  point; they don't just display data.

### 7. Implementation plan for Opus
- Numbered scripts, src/02_... onwards. For each: inputs, outputs (file names), what it computes, and
  acceptance checks Opus must pass before moving on (for example "WP model test Brier score < X",
  "leverage mean = 1.00", "top-10 tables have no player below the eligibility threshold").
- Order of work, and which steps can be cut if time runs short (mark them CUTTABLE).

## Also
- Append each decision you make to DECISIONS.md in its format (D6 onwards). Close Q1 and Q2.
- If one design choice is truly a coin-flip, pick the simpler option and say so in the spec.
- Before you finish, re-read the brief requirements in CLAUDE.md and confirm that every required report item
  is covered by a spec section. List any gaps.

When finished, give me a summary of at most 10 lines: the pressure definition in one sentence, the rating
formula in one sentence, the eligibility thresholds, and the three biggest risks you see.
