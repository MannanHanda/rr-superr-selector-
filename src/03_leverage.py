"""
03_leverage.py — Phase 2, step 2: leverage, pressure balls and the value of every ball.
Spec: docs/METHODOLOGY_SPEC.md sections 1.3, 1.4, 2.1 and 7.

Run from the repo root:
    python src/03_leverage.py

Inputs  (data/processed/): balls.parquet, wp_models.pkl, par.parquet
Outputs (data/processed/): ball_values.parquet  one row per scored ball:
            keys (match_id, innings, innings_ball_num), outcome (league outcome code),
            wp0 / wp1 / wp_nw (batting side WP before, after, after-without-the-wicket),
            li_raw, LI, is_pressure, is_crunch, is_dead, is_routine,
            WPA (= wp1 - wp0), x_run, x_wkt (Impact parts; NaN on dead balls)
        (outputs/):        leverage_summary.md

Leverage (1.3): SD of the WP after the ball over 8 outcomes (dot, 1, 2, 3, 4, 6, wicket, extra), weighted
by league outcome frequencies in the same innings x phase; LI = li_raw / mean li_raw (average ball = 1.00).
Pressure (1.4): LI at or above the 75th percentile of its own innings. Crunch: top 5% of LI overall.
Dead: li_raw < 0.002 (dropped from value metrics). Routine: neither pressure nor dead.
Impact (2.1): x_run = (wp_nw - wp0) / li_raw, x_wkt = (wp1 - wp_nw) / li_raw, each clipped to [-6, 6].
Exits with code 1 if any acceptance check fails.
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_wp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

PRESSURE_Q = 0.75
CRUNCH_Q = 0.95
DEAD_LI_RAW = 0.002
X_CLIP = 6.0
OUTCOMES = lib_wp.OUTCOMES  # outcome code -> (runs added, wickets lost, legal ball used)
outcome_code = lib_wp.outcome_code

COLS = [
    "match_id", "innings", "innings_ball_num", "overid", "comp_tier", "year", "status", "is_dls", "phase", "max_balls",
    "balls_remaining", "wickets_before", "score_before", "runs_needed", "total_runs", "is_legal", "is_wicket",
    "batting_team_won",
]


def main() -> None:
    with open(PROC / "wp_models.pkl", "rb") as fh:
        models = pickle.load(fh)
    raw = pd.read_parquet(PROC / "balls.parquet", columns=COLS)
    b = raw[lib_wp.scored_mask(raw)].copy()
    b = b.merge(pd.read_parquet(PROC / "par.parquet", columns=["match_id", "par"]), on="match_id", how="left")
    b = b.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

    inn = b["innings"].to_numpy()
    S, B = b["score_before"].to_numpy(float), b["balls_remaining"].to_numpy(float)
    W = (10 - b["wickets_before"]).to_numpy(float)
    R = b["runs_needed"].fillna(0).to_numpy(float)
    MB, PAR = b["max_balls"].to_numpy(float), b["par"].to_numpy(float)

    def wp(dr, db, dw):
        return lib_wp.wp(models, inn, S + dr, B - db, W - dw, R - dr, MB, PAR)

    # --- WP before, after, after-without-wicket
    runs, legal, wkt = (b[c].to_numpy(float) for c in ("total_runs", "is_legal", "is_wicket"))
    b["wp0"] = wp(0, 0, 0)
    b["wp1"] = wp(runs, legal, wkt)
    b["wp_nw"] = wp(runs, legal, 0)
    b["WPA"] = b["wp1"] - b["wp0"]

    # --- leverage
    b["outcome"] = outcome_code(b)
    freq = b.groupby(["innings", "phase"])["outcome"].value_counts(normalize=True).unstack(fill_value=0.0)
    freq = freq.reindex(columns=list(OUTCOMES), fill_value=0.0)
    key = pd.MultiIndex.from_arrays([b["innings"], b["phase"]])
    ev, ev2 = np.zeros(len(b)), np.zeros(len(b))
    for o, (dr, dw, db) in OUTCOMES.items():
        p = freq[o].reindex(key).to_numpy()
        v = wp(dr, db, dw)
        ev += p * v
        ev2 += p * v * v
    b["li_raw"] = np.sqrt(np.maximum(ev2 - ev ** 2, 0.0))
    b["LI"] = b["li_raw"] / b["li_raw"].mean()

    # --- pressure / crunch / dead / routine
    cut = b.groupby("innings")["LI"].quantile(PRESSURE_Q)
    b["is_pressure"] = b["LI"] >= b["innings"].map(cut)
    b["is_crunch"] = b["LI"] >= b["LI"].quantile(CRUNCH_Q)
    b["is_dead"] = b["li_raw"] < DEAD_LI_RAW
    b["is_routine"] = ~b["is_pressure"] & ~b["is_dead"]

    # --- Impact (uncredited); NaN on dead balls so they cannot leak into value metrics
    live = ~b["is_dead"]
    b["x_run"] = ((b["wp_nw"] - b["wp0"]) / b["li_raw"]).where(live).clip(-X_CLIP, X_CLIP)
    b["x_wkt"] = ((b["wp1"] - b["wp_nw"]) / b["li_raw"]).where(live).clip(-X_CLIP, X_CLIP)

    out_cols = ["match_id", "innings", "innings_ball_num", "outcome", "wp0", "wp1", "wp_nw", "WPA", "li_raw", "LI",
                "is_pressure", "is_crunch", "is_dead", "is_routine", "x_run", "x_wkt"]
    b[out_cols].to_parquet(PROC / "ball_values.parquet", index=False)

    # --- acceptance checks
    wp_cols = ["wp0", "wp1", "wp_nw"]
    nan_core = int(b[wp_cols + ["li_raw", "LI"]].isna().sum().sum())
    nan_x = int(b.loc[live, ["x_run", "x_wkt"]].isna().sum().sum())
    wp_ok = bool(((b[wp_cols] >= 0) & (b[wp_cols] <= 1)).all().all())
    share = b.groupby("innings")["is_pressure"].mean()

    # telescoping: over a whole chase the WPA sums to (final result - WP at the first ball)
    rng = np.random.default_rng(lib_wp.SEED)
    chases = b[(b["innings"] == 2) & (b["status"] == "completed") & (b["is_dls"] != 1)]
    sample = rng.choice(chases["match_id"].unique(), 20, replace=False)
    g = chases[chases["match_id"].isin(sample)].groupby("match_id").agg(
        wpa=("WPA", "sum"), start=("wp0", "first"), won=("batting_team_won", "first"))
    tele_err = float((g["wpa"] - (g["won"] - g["start"])).abs().max())
    # and ball to ball: WP after a ball equals WP before the next ball (all innings)
    nxt = b.groupby(["match_id", "innings"])["wp0"].shift(-1)
    chain_err = float((b["wp1"] - nxt).abs().max())

    bad_dls = int(((b["innings"] == 2) & b["match_id"].isin(lib_wp.DLS_NO_TARGET)).sum())
    bad_so = int((~b["innings"].isin([1, 2])).sum())
    bad_nr = int((~b["status"].isin(["completed", "tie_super_over"])).sum())

    checks = [
        ("Mean LI = 1.00 +/- 0.001", f"{b['LI'].mean():.4f}", abs(b["LI"].mean() - 1) <= 0.001),
        ("Pressure share innings 1 = 25% +/- 0.5", f"{100 * share[1]:.2f}%", abs(share[1] - 0.25) <= 0.005),
        ("Pressure share innings 2 = 25% +/- 0.5", f"{100 * share[2]:.2f}%", abs(share[2] - 0.25) <= 0.005),
        ("No NaN on scored balls (WP, leverage; x on live)", f"{nan_core + nan_x} NaN", nan_core + nan_x == 0),
        ("All WP in [0, 1]", str(wp_ok), wp_ok),
        ("Mean batting WPA per ball within +/-0.001", f"{b['WPA'].mean():+.5f}", abs(b["WPA"].mean()) <= 0.001),
        ("Chase WPA sums to result - start WP (20 matches)", f"max err {tele_err:.1e}", tele_err <= 1e-6),
        ("Bad-DLS chases absent", f"{bad_dls} rows", bad_dls == 0),
        ("Super overs absent", f"{bad_so} rows", bad_so == 0),
        ("No-result / abandoned absent", f"{bad_nr} rows", bad_nr == 0),
    ]
    check_df = pd.DataFrame(checks, columns=["check", "value", "pass"])

    # --- summary report
    pct = b["LI"].quantile([0.5, 0.75, 0.9, 0.95, 0.99]).rename("LI")
    mix = (b[b["is_pressure"]].groupby("innings")["phase"].value_counts(normalize=True).unstack()
           .reindex(columns=["powerplay", "middle", "death"]).mul(100))
    by_cell = b.pivot_table(index="innings", columns="phase", values="is_pressure", aggfunc="mean")
    by_cell = by_cell.reindex(columns=["powerplay", "middle", "death"]).mul(100)
    wk = (b[b["innings"] == 1].groupby(pd.cut(b["wickets_before"], [-1, 1, 3, 5, 9],
                                                 labels=["0-1", "2-3", "4-5", "6-9"]), observed=True)
          ["is_pressure"].mean().mul(100).rename("innings-1 pressure % by wickets down"))
    chp = b[b["is_pressure"] & (b["innings"] == 2)]
    tier = b.groupby("comp_tier")[["is_pressure", "is_crunch", "is_dead"]].mean().mul(100)
    flags = pd.Series({"pressure": b["is_pressure"].mean(), "crunch": b["is_crunch"].mean(),
                       "dead": b["is_dead"].mean(), "routine": b["is_routine"].mean()}).mul(100)
    xs = b.loc[live].assign(x=lambda d: d["x_run"] + d["x_wkt"]).groupby("is_pressure")["x"].agg(["mean", "std"])
    # REVIEW_1 item 7: what first-innings "pressure" is (mostly the new ball), in numbers the report can quote
    pb = b[b["is_pressure"]]
    inn_tab = pd.DataFrame({
        "pressure balls": pb.groupby("innings").size(),
        "share of all pressure balls %": 100 * pb.groupby("innings").size() / len(pb),
        "share in powerplay %": 100 * pb.groupby("innings")["phase"].apply(lambda s: (s == "powerplay").mean()),
        "median LI of pressure balls": pb.groupby("innings")["LI"].median(),
        "LI cut": cut, "LI p95 within innings": b.groupby("innings")["LI"].quantile(0.95),
    })
    inn1_pp_share = 100 * ((pb["innings"] == 1) & (pb["phase"] == "powerplay")).mean()
    over_flag = (b[(b["innings"] == 1) & (b["overid"] <= 6)].groupby("overid")["is_pressure"].mean().mul(100)
                 .rename("innings-1 share of balls flagged pressure %"))

    lines = [
        "# Leverage summary (generated by src/03_leverage.py)", "",
        "Spec: docs/METHODOLOGY_SPEC.md sections 1.3, 1.4, 2.1.", "",
        "## Acceptance checks", "", check_df.to_markdown(index=False), "",
        f"Scored balls: {len(b):,} in {b['match_id'].nunique()} matches. "
        f"Mean li_raw = {b['li_raw'].mean():.4f}. Ball-to-ball WP chain max error: {chain_err:.1e}.", "",
        "## LI percentiles", "", pct.to_frame().to_markdown(floatfmt=".2f"), "",
        "## Pressure cut (LI at the 75th percentile of each innings)", "",
        cut.rename("LI cut").to_frame().to_markdown(floatfmt=".3f"), "",
        "## Share of balls by flag (%)", "", flags.to_frame("% of scored balls").to_markdown(floatfmt=".1f"), "",
        "## Phase mix of pressure balls (% of each innings' pressure balls)", "", mix.to_markdown(floatfmt=".1f"), "",
        "## First-innings pressure is mostly the new ball (REVIEW_1 item 7)", "",
        inn_tab.to_markdown(floatfmt=".2f"), "",
        f"First-innings powerplay balls are {inn1_pp_share:.1f}% of all pressure balls.", "",
        over_flag.to_frame().to_markdown(floatfmt=".1f"), "",
        "## Share of balls that are pressure balls, by innings and phase (%)", "", by_cell.to_markdown(floatfmt=".1f"),
        "", wk.to_frame().to_markdown(floatfmt=".1f"), "",
        f"Chase pressure balls: mean WP {chp['wp0'].mean():.2f}; share with WP between 0.2 and 0.8: "
        f"{100 * chp['wp0'].between(0.2, 0.8).mean():.0f}%.", "",
        "## By competition tier (%)", "", tier.to_markdown(floatfmt=".1f"), "",
        "## Impact per ball (x_run + x_wkt, batting side, live balls)", "",
        xs.rename(index={False: "routine", True: "pressure"}).to_markdown(floatfmt=".3f"), "",
        "## League outcome frequencies used for leverage (innings x phase)", "",
        freq.to_markdown(floatfmt=".3f"), "",
    ]
    (OUTPUTS / "leverage_summary.md").write_text("\n".join(lines), encoding="utf-8")

    # --- console summary
    print(f"Scored balls: {len(b):,}; LI p50/p75/p90/p95/p99 = "
          + " / ".join(f"{v:.2f}" for v in pct) + f"; pressure cuts {cut.round(2).to_dict()}")
    print(f"Pressure phase mix (%): " + "; ".join(
        f"inn {i}: " + ", ".join(f"{c} {v:.0f}" for c, v in r.items()) for i, r in mix.iterrows()))
    print(f"Dead {flags['dead']:.1f}%, crunch {flags['crunch']:.1f}%; ball-to-ball WP chain max error {chain_err:.1e}")
    print()
    print(check_df.assign(**{"pass": check_df["pass"].map({True: "PASS", False: "FAIL"})}).to_string(index=False))
    print(f"\nWrote {PROC / 'ball_values.parquet'}, {OUTPUTS / 'leverage_summary.md'}")
    if not check_df["pass"].all():
        sys.exit(1)


if __name__ == "__main__":
    main()
