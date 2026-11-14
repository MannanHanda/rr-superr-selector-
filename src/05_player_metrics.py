"""
05_player_metrics.py — Phase 2, step 4: credit every ball to batters and bowlers, weight it, and build
per-player metrics and eligibility.
Spec: docs/METHODOLOGY_SPEC.md sections 2.1-2.3, 3.2-3.4 and 7.

Run from the repo root:
    python src/05_player_metrics.py

Inputs  (data/processed/): balls.parquet, ball_values.parquet, players.parquet
Outputs (data/processed/): player_match_stats.parquet  sufficient statistics per
            discipline x player x match x flag (pressure / routine / dead); used by 06 and the 07 bootstrap
        (outputs/): tier_offsets.csv, metrics_batters.csv, metrics_bowlers.csv, eligibility_funnel.csv

The crediting, weighting, tier offsets and eligibility rules live in lib_rating.py (shared with 06 and 07):
Credit (2.1): batter = balls faced; run part always, wicket part only if the striker is out.
              bowler = every delivery; minus the run part, minus the wicket part only for bowler wickets.
Tier offset (3.3): mean (tier - IPL) Impact per ball of players with >= 150 balls in both, weighted by the
              smaller count; subtracted from every ball in that tier (run and wicket parts separately, D30).
Weights (3.4): ball weight = tier weight x 0.5 ** ((2026 - year) / 2).
Eligibility (3.2): IPL + T20I_full, non-dead balls.
Exits with code 1 if any acceptance check fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rating as lr  # noqa: E402
import lib_wp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

POOL_RANGE = (60, 120)


def plain_stats(s: pd.DataFrame, disc: str, prefix: str) -> pd.DataFrame:
    g = s.groupby("player_id")[["rows", "n_balls", "runs", "dots", "bnd", "outs"]].sum()
    if disc == "bat":
        out = pd.DataFrame({"balls": g["n_balls"], "SR": 100 * g["runs"] / g["n_balls"],
                            "dot_pct": 100 * g["dots"] / g["n_balls"], "boundary_pct": 100 * g["bnd"] / g["n_balls"],
                            "balls_per_dismissal": g["n_balls"] / g["outs"].replace(0, np.nan)})
    else:
        out = pd.DataFrame({"balls": g["n_balls"], "economy": 6 * g["runs"] / g["n_balls"],
                            "dot_pct": 100 * g["dots"] / g["n_balls"], "boundary_pct": 100 * g["bnd"] / g["n_balls"],
                            "balls_per_wicket": g["n_balls"] / g["outs"].replace(0, np.nan)})
    return out.add_prefix(prefix)


def value_stats(s: pd.DataFrame, prefix: str) -> pd.DataFrame:
    g = s.groupby("player_id")[["rows", "w", "w2", "w_x_run", "w_x_wkt", "w_x_tot", "w_rae", "wpa"]].sum()
    return pd.DataFrame({
        "rows": g["rows"], "n_eff": g["w"] ** 2 / g["w2"],
        "impact_per100": 100 * g["w_x_tot"] / g["w"], "impact_run_per100": 100 * g["w_x_run"] / g["w"],
        "impact_wkt_per100": 100 * g["w_x_wkt"] / g["w"], "rae_per100": 100 * g["w_rae"] / g["w"],
        "wpa_sum": g["wpa"], "wpa_per100": 100 * g["wpa"] / g["rows"],
    }).add_prefix(prefix)


def build_metrics(pms: pd.DataFrame, disc: str, players: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    s = pms[pms["discipline"] == disc]
    core = s[s["comp_tier"].isin(lr.CORE_TIERS)]
    e, funnel = lr.eligibility(pms, disc)

    live = s[s["flag"] != "dead"]
    pr = live[live["flag"] == "pressure"]
    pm_all = pr.groupby(["player_id", "match_id"])["n_balls"].sum()
    m = pd.concat([
        e,
        value_stats(pr, "pressure_"), value_stats(live[live["flag"] == "routine"], "routine_"),
        plain_stats(core[core["flag"] == "pressure"], disc, "pressure_"),
        plain_stats(core[core["flag"] == "routine"], disc, "routine_"),
        plain_stats(core, disc, "all_"),
        pd.DataFrame({
            "matches": s.groupby("player_id")["match_id"].nunique(),
            "pressure_matches_all_tiers": (pm_all >= lr.PRESSURE_MATCH_MIN_BALLS).groupby("player_id").sum(),
            "pressure_share_inn1": pr[pr["innings"] == 1].groupby("player_id")["n_balls"].sum()
            / pr.groupby("player_id")["n_balls"].sum(),
            "ipl_share_of_balls": s[s["comp_tier"] == "IPL"].groupby("player_id")["n_balls"].sum()
            / s.groupby("player_id")["n_balls"].sum(),
        }),
    ], axis=1)
    m = m[m.index.isin(live["player_id"])]
    m["eligible"] = m["eligible"].fillna(False).astype(bool)
    m = players.set_index("player_id")[["player_name", "ipl_2026_team"]].join(m, how="right")
    m.index.name = "player_id"
    return m.sort_values(["eligible", "pressure_impact_per100"], ascending=[False, False]), funnel


def hand_check(players: pd.DataFrame, metrics: dict) -> pd.DataFrame:
    """Independent plain-stat calculation straight from balls.parquet for the 3 highest-volume batters
    and bowlers in IPL + T20I_full."""
    raw = pd.read_parquet(PROC / "balls.parquet", columns=["match_id", "innings", "status", "comp_tier", "striker_id",
                                                           "bowler_id", "batter_runs", "bowler_runs",
                                                           "is_wide", "is_noball"])
    raw = raw[lib_wp.scored_mask(raw) & raw["comp_tier"].isin(lr.CORE_TIERS)]
    names = players.set_index("player_id")["player_name"]
    rows = []
    faced = raw[raw["is_wide"] != 1]
    for pid in faced["striker_id"].value_counts().index[:3]:
        f = faced[faced["striker_id"] == pid]
        rows.append({"player": names[pid], "stat": "SR", "hand": 100 * f["batter_runs"].sum() / len(f),
                     "pipeline": metrics["bat"].loc[pid, "all_SR"]})
    legal = raw[(raw["is_wide"] != 1) & (raw["is_noball"] != 1)]
    for pid in legal["bowler_id"].value_counts().index[:3]:
        hand = 6 * raw.loc[raw["bowler_id"] == pid, "bowler_runs"].sum() / (legal["bowler_id"] == pid).sum()
        rows.append({"player": names[pid], "stat": "economy", "hand": hand,
                     "pipeline": metrics["bowl"].loc[pid, "all_economy"]})
    return pd.DataFrame(rows)


def main() -> None:
    pms, offs = lr.build_pms(lr.load_balls(), lr.Params())
    offs.to_csv(OUTPUTS / "tier_offsets.csv", index=False)
    pms.to_parquet(PROC / "player_match_stats.parquet", index=False)

    players = pd.read_parquet(PROC / "players.parquet")
    metrics, funnels = {}, []
    for disc in ("bat", "bowl"):
        metrics[disc], f = build_metrics(pms, disc, players)
        funnels.append(f)
    metrics["bat"].to_csv(OUTPUTS / "metrics_batters.csv", float_format="%.4f")
    metrics["bowl"].to_csv(OUTPUTS / "metrics_bowlers.csv", float_format="%.4f")
    funnel = pd.concat(funnels, ignore_index=True)
    funnel.to_csv(OUTPUTS / "eligibility_funnel.csv", index=False)

    # --- acceptance checks
    raw = pd.read_parquet(PROC / "balls.parquet", columns=["match_id", "innings", "status", "is_ball_faced",
                                                           "batter_runs", "is_bowler_wicket"])
    raw = raw[lib_wp.scored_mask(raw)]
    direct_runs = int(raw.loc[raw["is_ball_faced"] == 1, "batter_runs"].sum())
    direct_wkts = int(raw["is_bowler_wicket"].sum())
    cred_runs = int(pms.loc[pms["discipline"] == "bat", "runs"].sum())
    cred_wkts = int(pms.loc[pms["discipline"] == "bowl", "outs"].sum())
    n_bat, n_bowl = int(metrics["bat"]["eligible"].sum()), int(metrics["bowl"]["eligible"].sum())
    hc = hand_check(players, metrics)
    hc_err = float((hc["hand"] - hc["pipeline"]).abs().max())
    w_tab = {y: round(float(lr.recency_weight(y)), 2) for y in range(2022, 2027)}
    expected_w = {2022: 0.25, 2023: 0.35, 2024: 0.50, 2025: 0.71, 2026: 1.00}
    impact_cols = ["pressure_impact_per100", "routine_impact_per100"]
    no_nan = all(metrics[d].loc[metrics[d]["eligible"], impact_cols].notna().all().all() for d in ("bat", "bowl"))
    checks = [
        ("Credited batter runs = direct count", f"{cred_runs:,} vs {direct_runs:,}", cred_runs == direct_runs),
        ("Credited bowler wickets = direct count", f"{cred_wkts:,} vs {direct_wkts:,}", cred_wkts == direct_wkts),
        (f"Eligible batters in {POOL_RANGE}", str(n_bat), POOL_RANGE[0] <= n_bat <= POOL_RANGE[1]),
        (f"Eligible bowlers in {POOL_RANGE}", str(n_bowl), POOL_RANGE[0] <= n_bowl <= POOL_RANGE[1]),
        ("Plain stats match hand calc (3 bat, 3 bowl)", f"max diff {hc_err:.1e}", hc_err < 1e-9),
        ("Recency weights match spec 3.4", str(w_tab), w_tab == expected_w),
        ("No NaN Impact for eligible players", "", no_nan),
    ]
    check_df = pd.DataFrame(checks, columns=["check", "value", "pass"])

    # --- console summary
    print(funnel.pivot(index="step", columns="discipline", values="players").reindex(
        funnel["step"].drop_duplicates()).to_string())
    print("\nTier offsets (Impact per 100 balls, run + wicket, applied):")
    t = offs.groupby(["discipline", "tier"]).agg(off=("applied_offset_per_ball", "sum"),
                                                 raw=("raw_offset_per_ball", "sum"), n=("n_players", "first"))
    print((t.assign(off=100 * t["off"], raw=100 * t["raw"])).round(2).to_string())
    print("\nHand check:")
    print(hc.round(3).to_string(index=False))
    for disc, label in (("bat", "batters"), ("bowl", "bowlers")):
        e = metrics[disc][metrics[disc]["eligible"]]
        print(f"\nEligible {label}: Impact/100 pressure mean {e['pressure_impact_per100'].mean():+.2f} "
              f"(sd {e['pressure_impact_per100'].std():.2f}); routine mean {e['routine_impact_per100'].mean():+.2f} "
              f"(sd {e['routine_impact_per100'].std():.2f}); median pressure balls {e['elig_pressure_balls'].median():.0f}"
              f"; median inn-1 share of pressure balls {e['pressure_share_inn1'].median():.2f}")
    print()
    print(check_df.assign(**{"pass": check_df["pass"].map({True: "PASS", False: "FAIL"})}).to_string(index=False))
    print("\nWrote player_match_stats.parquet, tier_offsets.csv, metrics_batters.csv, metrics_bowlers.csv, "
          "eligibility_funnel.csv")
    if not check_df["pass"].all():
        sys.exit(1)


if __name__ == "__main__":
    main()
