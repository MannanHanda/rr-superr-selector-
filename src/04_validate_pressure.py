"""
04_validate_pressure.py — Phase 2, step 3: show that pressure balls really are different.
Spec: docs/METHODOLOGY_SPEC.md sections 1.5 and 7.

Run from the repo root:
    python src/04_validate_pressure.py

Inputs  (data/processed/): balls.parquet, ball_values.parquet, matches.parquet
Outputs (outputs/): pressure_validation.csv   outcomes by leverage band within phase, pressure minus routine
                                              with match-bootstrap 90% intervals, mean |WP change| by phase/band
                    naive_vs_leverage.csv     the usual definition (overs 16-20 or chase RRR > 10) vs ours
                    leverage_summary.md       appends the 15 highest-leverage states (for a human eyeball)
                    figures/f2_example_chase.png, f3_outcomes_by_band.png, f4_usual_vs_leverage.png

Leverage bands (spec 1.5): low = below the innings median LI; medium = median to the pressure cut;
pressure = pressure ball but not crunch; crunch = top 5% of LI overall. Band rates use legal balls.
Exits with code 1 if any acceptance check fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_wp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
FIGS = OUTPUTS / "figures"

N_BOOT = 1000
MIN_CELL = 500
BANDS = ["low", "medium", "pressure", "crunch"]
BAND_LABELS = {"low": "Low\n(bottom 50%)", "medium": "Medium\n(50-75%)", "pressure": "Pressure\n(top 25%)",
               "crunch": "Crunch\n(top 5%)"}
PHASES = ["powerplay", "middle", "death"]
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#a3a29c", "#e4e3df"
SERIES = {"powerplay": "#2a78d6", "middle": "#eb6834", "death": "#1baf7a"}
METRICS = {"SR": "Strike rate", "dot_pct": "Dot balls (%)", "boundary_pct": "Boundary balls (%)",
           "wicket_pct": "Wicket balls (%)"}
SUMMARY_MARK = "## 15 highest-leverage states"

BALL_COLS = ["match_id", "innings", "innings_ball_num", "overid", "over_ball_num", "phase", "comp_tier", "year",
             "status", "is_dls", "batting_team_id", "bowling_team_id", "is_legal", "batter_runs", "is_dot_faced",
             "is_four", "is_six", "is_wicket", "score_before", "wickets_before", "balls_remaining", "max_balls",
             "runs_needed", "req_run_rate", "target", "batting_team_won"]


def load() -> pd.DataFrame:
    v = pd.read_parquet(PROC / "ball_values.parquet")
    b = pd.read_parquet(PROC / "balls.parquet", columns=BALL_COLS)
    d = v.merge(b, on=["match_id", "innings", "innings_ball_num"], how="left", validate="1:1")
    pct = d.groupby("innings")["LI"].rank(pct=True)
    d["band"] = np.select([d["is_crunch"], d["is_pressure"], pct >= 0.5], ["crunch", "pressure", "medium"], "low")
    return d


def rates(s: pd.DataFrame) -> pd.DataFrame:
    """Rates from summed counts (columns legal, runs, dots, bnd, wkts)."""
    return pd.DataFrame({
        "SR": 100 * s["runs"] / s["legal"], "dot_pct": 100 * s["dots"] / s["legal"],
        "boundary_pct": 100 * s["bnd"] / s["legal"], "wicket_pct": 100 * s["wkts"] / s["legal"],
    })


def counts(d: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    leg = d[d["is_legal"] == 1]
    return leg.groupby(by, observed=True).agg(
        legal=("is_legal", "size"), runs=("batter_runs", "sum"), dots=("is_dot_faced", "sum"),
        bnd=("is_boundary", "sum"), wkts=("is_wicket", "sum"))


def bootstrap_diff(d: pd.DataFrame) -> pd.DataFrame:
    """Pressure minus routine, per phase and metric, with a 90% match-bootstrap interval."""
    leg = d[(d["is_legal"] == 1) & (d["is_pressure"] | d["is_routine"])]
    c = counts(leg, ["match_id", "phase", "is_pressure"])
    mids = c.index.get_level_values("match_id").unique()
    rng = np.random.default_rng(lib_wp.SEED)
    w = np.stack([np.bincount(rng.integers(0, len(mids), len(mids)), minlength=len(mids)) for _ in range(N_BOOT)])
    w = pd.DataFrame(w.T, index=mids)  # matches x resamples
    rows = []
    for ph in PHASES:
        res = {}
        for flag in (True, False):
            sub = c.xs((ph, flag), level=("phase", "is_pressure"))
            ww = w.reindex(sub.index).to_numpy()
            point = rates(sub.sum().to_frame().T).iloc[0]
            boot = rates(pd.DataFrame(ww.T @ sub.to_numpy(), columns=sub.columns))
            res[flag] = (point, boot)
        for m in METRICS:
            diff = res[True][1][m] - res[False][1][m]
            rows.append({"table": "pressure_minus_routine", "innings": "both", "phase": ph, "band": "pressure-routine",
                         "metric": m, "value": res[True][0][m] - res[False][0][m],
                         "lo90": diff.quantile(0.05), "hi90": diff.quantile(0.95), "n_balls": np.nan})
    return pd.DataFrame(rows)


def band_table(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    for inn_label, sub in (("both", d), ("1", d[d["innings"] == 1]), ("2", d[d["innings"] == 2])):
        c = counts(sub, ["phase", "band"])
        r = rates(c).join(c["legal"].rename("n_balls"))
        r = r.reset_index().melt(id_vars=["phase", "band", "n_balls"], var_name="metric")
        r["innings"] = inn_label
        out.append(r)
    t = pd.concat(out)
    t["table"] = "rates_by_band"
    return t


def abs_wpa_table(d: pd.DataFrame) -> pd.DataFrame:
    a = d.assign(abs_wpa=d["WPA"].abs())
    ph = a.groupby("phase")["abs_wpa"].agg(["mean", "size"]).reset_index().rename(columns={"phase": "group"})
    ph["by"] = "phase"
    bd = a.groupby("band")["abs_wpa"].agg(["mean", "size"]).reset_index().rename(columns={"band": "group"})
    bd["by"] = "leverage band"
    t = pd.concat([ph, bd]).rename(columns={"mean": "value", "size": "n_balls"})
    return pd.DataFrame({"table": "mean_abs_wp_change", "innings": "both", "phase": np.where(
        t["by"] == "phase", t["group"], "all"), "band": np.where(t["by"] == "phase", "all", t["group"]),
        "metric": "mean_abs_wp_change", "value": t["value"].to_numpy(), "n_balls": t["n_balls"].to_numpy()})


def naive_table(d: pd.DataFrame) -> pd.DataFrame:
    usual = (d["overid"] >= 16) | ((d["innings"] == 2) & (d["req_run_rate"] > 10))
    below_med = d.groupby("innings")["LI"].rank(pct=True) < 0.5
    d = d.assign(usual=usual, below_med=below_med)
    rows = []
    for lab, s in (("both", d), ("1", d[d["innings"] == 1]), ("2", d[d["innings"] == 2])):
        u, p = s[s["usual"]], s[s["is_pressure"]]
        rows.append({
            "innings": lab, "usual_balls": len(u), "pressure_balls": len(p),
            "usual_share_dead_pct": 100 * u["is_dead"].mean(),
            "usual_share_below_median_pct": 100 * u["below_med"].mean(),
            "usual_share_dead_or_below_median_pct": 100 * (u["is_dead"] | u["below_med"]).mean(),
            "usual_share_that_is_pressure_pct": 100 * u["is_pressure"].mean(),
            "pressure_missed_by_usual_pct": 100 * (~p["usual"]).mean(),
            "crunch_missed_by_usual_pct": 100 * (~s.loc[s["is_crunch"], "usual"]).mean(),
        })
    return pd.DataFrame(rows)


def top_states(d: pd.DataFrame) -> pd.DataFrame:
    t = d.sort_values("LI", ascending=False).drop_duplicates(
        ["innings", "balls_remaining", "wickets_before", "score_before", "runs_needed"]).head(15)
    return pd.DataFrame({
        "innings": t["innings"], "tier": t["comp_tier"], "year": t["year"],
        "over": t["overid"].astype(str) + "." + t["over_ball_num"].astype(str),
        "score": t["score_before"].astype(int).astype(str) + "/" + t["wickets_before"].astype(int).astype(str),
        "balls left": t["balls_remaining"].astype(int), "runs needed": t["runs_needed"],
        "WP batting side": t["wp0"].round(2), "LI": t["LI"].round(2),
    }).reset_index(drop=True)


# ---------------------------------------------------------------- figures

def style(ax) -> None:
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8, colors=INK2)


def fig_bands(t: pd.DataFrame) -> Path:
    t = t[t["innings"] == "both"]
    fig, axes = plt.subplots(1, 4, figsize=(7.5, 3.4))
    x = np.arange(len(BANDS))
    for ax, (m, label) in zip(axes, METRICS.items()):
        for ph in PHASES:
            s = t[(t["metric"] == m) & (t["phase"] == ph)].set_index("band").reindex(BANDS)
            ax.plot(x, s["value"], color=SERIES[ph], lw=2, marker="o", ms=5, markeredgecolor="white",
                    markeredgewidth=1.2, label=ph.capitalize())
        ax.set_title(label, fontsize=9, color=INK, loc="left")
        ax.set_xticks(x, ["Low", "Medium", "Pressure", "Crunch"], fontsize=7, rotation=35, ha="right",
                      rotation_mode="anchor")
        style(ax)
    fig.supxlabel("Leverage band", fontsize=8, color=INK2, y=0.1)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=8, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("In every phase, batters score more slowly on pressure balls",
                 fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    path = FIGS / "f3_outcomes_by_band.png"
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


def fig_naive(n: pd.DataFrame) -> Path:
    # chase only (D29): in innings 1 the comparison is partly circular, since our first-innings pressure
    # balls sit early and the usual definition there is overs 16-20
    r = n.set_index("innings").loc["2"]
    vals = [r["usual_share_dead_or_below_median_pct"], r["pressure_missed_by_usual_pct"],
            r["crunch_missed_by_usual_pct"]]
    labels = ["Share of 'usual pressure' chase balls\nthat are dead or below-median leverage",
              "Share of our chase pressure balls\nthe usual definition misses",
              "Share of crunch balls (top 5%)\nthe usual definition misses"]
    fig, ax = plt.subplots(figsize=(7.5, 2.6))
    y = np.arange(len(vals))[::-1]
    ax.barh(y, vals, color="#2a78d6", height=0.55)
    for yy, v in zip(y, vals):
        ax.text(v + 1, yy, f"{v:.0f}%", va="center", fontsize=9, color=INK)
    ax.set_yticks(y, labels, fontsize=8)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of balls", fontsize=8, color=INK2)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8, colors=INK2)
    fig.suptitle("In chases, 'death overs or required rate above 10' measures the wrong balls", fontsize=11,
                 color=INK, x=0.01, ha="left")
    fig.tight_layout()
    path = FIGS / "f4_usual_vs_leverage.png"
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


def fig_example(d: pd.DataFrame, teams: dict) -> tuple[Path, int]:
    m = pd.read_parquet(PROC / "matches.parquet", columns=["match_id", "is_dls", "status"])
    ok = m[(m["status"] == "completed") & (m["is_dls"] != 1)]["match_id"]
    ch = d[(d["innings"] == 2) & (d["comp_tier"] == "IPL") & (d["year"] == 2026) & d["match_id"].isin(ok)
           & (d["max_balls"] == 120)]
    mid = int(ch.groupby("match_id")["LI"].mean().idxmax())
    s = ch[ch["match_id"] == mid].sort_values("innings_ball_num")
    bat, bowl = teams.get(s["batting_team_id"].iloc[0], "Chasing side"), teams.get(s["bowling_team_id"].iloc[0], "")
    won = s["batting_team_won"].iloc[0] == 1
    x = np.arange(1, len(s) + 1)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.5, 4.4), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    a1.plot(np.r_[0, x], np.r_[s["wp0"].iloc[0], s["wp1"].to_numpy()], color="#2a78d6", lw=2)
    a1.axhline(0.5, color=MUTED, lw=0.8, ls="--")
    a1.set_ylim(0, 1)
    a1.set_ylabel("Chasing side\nwin probability", fontsize=8, color=INK2)
    style(a1)
    colors = np.where(s["is_pressure"], "#eb6834", MUTED)
    a2.bar(x, s["LI"], color=colors, width=0.8)
    a2.axhline(s["LI"][s["is_pressure"]].min() if s["is_pressure"].any() else 1.7, color=INK2, lw=0.8, ls=":")
    a2.set_ylabel("Leverage\n(average ball = 1)", fontsize=8, color=INK2)
    a2.set_xlabel("Ball of the chase (including extras)", fontsize=8, color=INK2)
    style(a2)
    a2.text(0.01, 0.92, "orange = pressure ball", transform=a2.transAxes, fontsize=8, color=INK2, va="top")
    target = int(s["target"].iloc[0])
    result = "won" if won else "lost"
    fig.suptitle(f"Leverage climbs as a close chase tightens\n{bat} chasing {target} v {bowl}, "
                 f"IPL 2026 ({result})", fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    path = FIGS / "f2_example_chase.png"
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path, mid


def main() -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    d = load()
    d["is_boundary"] = d["is_four"] + d["is_six"]

    bands = band_table(d)
    diff = bootstrap_diff(d)
    absw = abs_wpa_table(d)
    val = pd.concat([bands, diff, absw], ignore_index=True)[
        ["table", "innings", "phase", "band", "metric", "value", "lo90", "hi90", "n_balls"]]
    val.to_csv(OUTPUTS / "pressure_validation.csv", index=False)
    naive = naive_table(d)
    naive.to_csv(OUTPUTS / "naive_vs_leverage.csv", index=False)

    m = pd.read_parquet(PROC / "matches.parquet", columns=["home_team_id", "home_team", "away_team_id", "away_team"])
    teams = {**dict(zip(m["home_team_id"], m["home_team"])), **dict(zip(m["away_team_id"], m["away_team"]))}
    f2, example_mid = fig_example(d, teams)
    f3, f4 = fig_bands(bands), fig_naive(naive)

    top = top_states(d)
    summary = (OUTPUTS / "leverage_summary.md").read_text(encoding="utf-8")
    summary = summary.split(SUMMARY_MARK)[0].rstrip() + "\n\n"
    summary += (f"{SUMMARY_MARK} (added by src/04_validate_pressure.py; one row per distinct state)\n\n"
                + top.to_markdown(index=False) + "\n")
    (OUTPUTS / "leverage_summary.md").write_text(summary, encoding="utf-8")

    # --- acceptance checks
    both = bands[(bands["innings"] == "both") & (bands["metric"] == "SR")]
    share = both.groupby("phase")["n_balls"].transform(lambda s: s / s.sum())
    share_sum = both.assign(s=share).groupby("phase")["s"].sum()
    small = both[both["n_balls"] < MIN_CELL][["phase", "band", "n_balls"]]
    small_by_inn = bands[(bands["innings"] != "both") & (bands["metric"] == "SR") & (bands["n_balls"] < MIN_CELL)]
    checks = [
        ("Band shares sum to 100% in every phase", ", ".join(f"{v:.3f}" for v in share_sum),
         bool(np.allclose(share_sum, 1))),
        (f"Every phase x band cell has >= {MIN_CELL} balls or is flagged",
         f"{len(small)} small (flagged below)" if len(small) else "all >= 500", True),
        ("Top-15 leverage states table written to leverage_summary.md", f"{len(top)} rows", len(top) == 15),
        ("Bootstrap diff has 3 phases x 4 metrics", f"{len(diff)} rows", len(diff) == 12),
    ]
    check_df = pd.DataFrame(checks, columns=["check", "value", "pass"])

    # --- console summary
    piv = bands[(bands["innings"] == "both")].pivot_table(index=["phase", "band"], columns="metric", values="value")
    piv = piv.reindex(pd.MultiIndex.from_product([PHASES, BANDS]))[list(METRICS)]
    print(piv.round(1).to_string())
    print("\nPressure minus routine (90% interval):")
    print(diff.assign(ci=lambda x: x["lo90"].round(1).astype(str) + " to " + x["hi90"].round(1).astype(str))
          .pivot(index="phase", columns="metric", values="ci").reindex(PHASES)[list(METRICS)].to_string())
    print("\nMean |WP change| per ball: by phase",
          absw[absw["band"] == "all"].set_index("phase")["value"].round(4).to_dict(),
          "| by band", absw[absw["phase"] == "all"].set_index("band")["value"].reindex(BANDS).round(4).to_dict())
    r = naive.set_index("innings").loc["2"]
    print(f"Usual definition, chases: {r['usual_share_dead_or_below_median_pct']:.0f}% of its balls are dead or "
          f"below-median; "
          f"it misses {r['pressure_missed_by_usual_pct']:.0f}% of our pressure balls and "
          f"{r['crunch_missed_by_usual_pct']:.0f}% of crunch balls")
    if len(small) or len(small_by_inn):
        print("Flagged small cells (<500 legal balls):",
              "; ".join(f"{x.innings} {x.phase}/{x.band} n={int(x.n_balls)}" for x in
                        pd.concat([small.assign(innings="both"), small_by_inn]).itertuples()))
    print(f"F2 example chase: match {example_mid}")
    print()
    print(check_df.assign(**{"pass": check_df["pass"].map({True: "PASS", False: "FAIL"})}).to_string(index=False))
    print(f"\nWrote pressure_validation.csv, naive_vs_leverage.csv, leverage_summary.md (top states), {f2.name}, "
          f"{f3.name}, {f4.name}")
    if not check_df["pass"].all():
        sys.exit(1)


if __name__ == "__main__":
    main()
