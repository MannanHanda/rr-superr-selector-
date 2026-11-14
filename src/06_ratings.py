"""
06_ratings.py — Phase 2, step 5: shrink, combine and rank.
Spec: docs/METHODOLOGY_SPEC.md sections 2.4, 2.5, 3.1 and 7.

Run from the repo root:
    python src/06_ratings.py

Inputs  (data/processed/): player_match_stats.parquet;  (outputs/): metrics_batters.csv, metrics_bowlers.csv
Outputs (outputs/): eb_params.csv, ratings_batters.csv, ratings_bowlers.csv (whole eligible pool, ranked),
                    top10_batters.md, top10_bowlers.md (top 20 shown, top 10 marked),
                    figures/f5_shrinkage.png, figures/f6_pressure_vs_usual.png

Components (all in Impact per 100 balls, shrinkage in lib_rating.py):
  U  usual level      routine-ball run part + wicket part, each shrunk to the league mean
  D  pressure shift   pressure minus routine Impact, shrunk to the pool mean shift
  P  pressure level   U + D
  C  consistency      share of pressure matches (>= 3 pressure balls) with positive credited WPA, shrunk
Rating = 0.60 z(P) + 0.15 z(D) + 0.25 z(C), reported as 50 + 10 x rating.
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
import lib_rating as lr  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
FIGS = OUTPUTS / "figures"

INK, INK2, MUTED, GRID, BLUE, ORANGE = "#0b0b0b", "#52514e", "#a3a29c", "#e4e3df", "#2a78d6", "#eb6834"
LABEL = {"bat": "Batters", "bowl": "Bowlers"}
FILE = {"bat": "batters", "bowl": "bowlers"}
PER100 = ["P_hat", "U", "U_run", "U_wkt", "D_hat", "P_raw", "R_raw", "D_raw", "R_run_raw", "R_wkt_raw"]


def to_report_units(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    for c in PER100:
        if c in t:
            t[c] = 100 * t[c]
    for c in ("C_hat", "C_raw"):
        t[c] = 100 * t[c]
    return t


def top_table(r: pd.DataFrame, disc: str, n: int = 20) -> str:
    t = r.head(n)

    def pr(a, b, fmt="{:.0f}"):
        return [f"{fmt.format(x)} / {fmt.format(y)}" if pd.notna(x) and pd.notna(y) else "-"
                for x, y in zip(t[a], t[b])]

    out = pd.DataFrame({
        "Rank": [f"**{k}**" if k <= 10 else str(k) for k in t["rank"]],
        "Player": t["player_name"], "IPL 2026 team": t["ipl_2026_team"].fillna("-"),
        "Rating": t["rating"].round(1),
        "Pressure level": t["P_hat"].round(1), "Usual level": t["U"].round(1), "Shift": t["D_hat"].round(1),
        "Consistency %": t["C_hat"].round(0).astype(int),
        "Pressure balls": t["elig_pressure_balls"].astype(int), "Pressure matches": t["c_matches"].astype(int),
        "Pressure WPA (wins)": t["P_wpa_sum"].round(2),
    })
    if disc == "bat":
        out["SR P / R"] = pr("pressure_SR", "routine_SR")
        out["Dot % P / R"] = pr("pressure_dot_pct", "routine_dot_pct")
        out["Bdry % P / R"] = pr("pressure_boundary_pct", "routine_boundary_pct")
        out["Balls/out P / R"] = pr("pressure_balls_per_dismissal", "routine_balls_per_dismissal")
    else:
        out["Econ P / R"] = pr("pressure_economy", "routine_economy", "{:.2f}")
        out["Dot % P / R"] = pr("pressure_dot_pct", "routine_dot_pct")
        out["Bdry % P / R"] = pr("pressure_boundary_pct", "routine_boundary_pct")
        out["Balls/wkt P / R"] = pr("pressure_balls_per_wicket", "routine_balls_per_wicket")
    return out.to_markdown(index=False)


def style(ax) -> None:
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8, colors=INK2)


def fig_shrinkage(pool_tabs: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3.6), sharey=True)
    for ax, disc in zip(axes, ("bat", "bowl")):
        t = pool_tabs[disc]
        ax.scatter(t["n_P"], t["P_raw"], s=12, facecolors="none", edgecolors=MUTED, lw=0.8,
                   label="Raw pressure Impact")
        ax.scatter(t["n_P"], t["P_hat"], s=12, color=BLUE, label="After shrinkage (pressure level)")
        ax.axhline(0, color=INK2, lw=0.6)
        ax.set_xscale("log")
        ticks = [50, 100, 200, 400, 800]
        ax.set_xticks(ticks, [str(x) for x in ticks])
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.set_title(LABEL[disc], fontsize=10, color=INK, loc="left")
        ax.set_xlabel("Pressure balls (effective, weighted; log scale)", fontsize=8, color=INK2)
        style(ax)
    axes[0].set_ylabel("Impact per 100 pressure balls", fontsize=8, color=INK2)
    axes[0].legend(fontsize=7, frameon=False, loc="lower right")
    fig.suptitle("Shrinkage pulls small samples towards the average before anyone is ranked",
                 fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    path = FIGS / "f5_shrinkage.png"
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


def fig_pressure_vs_usual(rated: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 4.0))
    for ax, disc in zip(axes, ("bat", "bowl")):
        t = rated[disc]
        top = t["rank"] <= 10
        lo = min(t["U"].min(), t["P_hat"].min()) - 1
        hi = max(t["U"].max(), t["P_hat"].max()) + 1
        ax.plot([lo, hi], [lo, hi], ls="--", lw=0.8, color=INK2)
        ax.scatter(t.loc[~top, "U"], t.loc[~top, "P_hat"], s=12, color=MUTED, label="Eligible player")
        ax.scatter(t.loc[top, "U"], t.loc[top, "P_hat"], s=22, color=ORANGE, edgecolors="white", lw=0.8,
                   label="Top 10", zorder=3)
        # names in a column down the left, in order of pressure level, with leader lines (no collisions)
        lab = t[top].sort_values("P_hat", ascending=False)
        ys = np.linspace(hi - 0.08 * (hi - lo), hi - 0.55 * (hi - lo), len(lab))
        for yy, (_, r) in zip(ys, lab.iterrows()):
            ax.annotate(f"{int(r['rank'])}. {r['player_name']}", (r["U"], r["P_hat"]),
                        xytext=(lo + 0.03 * (hi - lo), yy), fontsize=6, color=INK, va="center",
                        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.5})
        ax.set_xlim(lo, hi), ax.set_ylim(lo, hi)
        ax.set_title(LABEL[disc], fontsize=10, color=INK, loc="left")
        ax.set_xlabel("Usual level (Impact per 100 routine balls)", fontsize=8, color=INK2)
        style(ax)
    axes[0].set_ylabel("Pressure level (Impact per 100 pressure balls)", fontsize=8, color=INK2)
    axes[1].legend(fontsize=7, frameon=False, loc="lower right")
    fig.suptitle("Batters lose ground under pressure and bowlers gain\n"
                 "(dashed line = same level under pressure as usual)", fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    path = FIGS / "f6_pressure_vs_usual.png"
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


def between(shrunk, raw, prior) -> bool:
    a, b = shrunk - prior, raw - prior
    ok = (a * b >= -1e-15) & (a.abs() <= b.abs() + 1e-12)
    return bool(ok[raw.notna()].all())


def main() -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    pms = pd.read_parquet(PROC / "player_match_stats.parquet")
    p = lr.Params()
    rated, pool_tabs, eb_rows, checks = {}, {}, [], []
    for disc in ("bat", "bowl"):
        metrics = pd.read_csv(OUTPUTS / f"metrics_{FILE[disc]}.csv", index_col="player_id")
        elig_ids = metrics.index[metrics["eligible"]]
        pool = lr.eb_pool(pms, disc)
        t, eb = lr.rate(pms, disc, elig_ids, pool, p)
        for q, e in eb.items():
            eb_rows.append({"discipline": disc, "quantity": q, **e})

        # shrinkage-between-raw-and-prior check, on the rated players
        between_ok = all([
            between(t["U_run"], t["R_run_raw"], eb["U_x_run"]["prior"]),
            between(t["U_wkt"], t["R_wkt_raw"], eb["U_x_wkt"]["prior"]),
            between(t["D_hat"], t["D_raw"], eb["D"]["prior"]),
            between(t["C_hat"], t["C_raw"], eb["C"]["prior"]),
        ])
        r = to_report_units(t).join(metrics, how="left")
        rated[disc] = r
        cols = ["rank", "player_name", "ipl_2026_team", "rating", "rating_z", "P_hat", "U", "U_run", "U_wkt", "D_hat",
                "C_hat", "P_raw", "R_raw", "D_raw", "C_raw", "n_P", "n_R", "c_matches", "P_wpa_sum",
                "z_P_hat", "z_D_hat", "z_C_hat", "elig_balls", "elig_pressure_balls", "elig_pressure_matches",
                "elig_recent_balls", "pressure_share_inn1", "ipl_share_of_balls"]
        plain = [c for c in metrics.columns if c.startswith(("pressure_", "routine_", "all_"))
                 and c not in cols and not c.endswith(("impact_per100", "_n_eff", "_rows"))]
        r[cols + plain].to_csv(OUTPUTS / f"ratings_{FILE[disc]}.csv", float_format="%.4f")
        (OUTPUTS / f"top10_{FILE[disc]}.md").write_text(
            f"# Top 20 {FILE[disc]} by reliability rating (generated by src/06_ratings.py)\n\n"
            "Ranks 1-10 in bold are the submission. Levels and shift are Impact per 100 balls (0 = average ball "
            "outcome for the situation; positive = helps the team's win chances). Consistency = shrunk share of "
            "pressure matches with positive win probability added. P / R = pressure / routine balls "
            "(plain stats on IPL + full-member T20Is). Rank intervals come from src/07_reliability.py.\n\n"
            + top_table(r, disc) + "\n", encoding="utf-8")

        # pool for the shrinkage figure: everyone in the EB pool, priors and k held at the main estimates
        pt, _ = lr.rate(pms, disc, pool.union(elig_ids), pool, p, eb=eb)
        pool_tabs[disc] = to_report_units(pt)

        el = metrics.loc[r.index]
        below = int((~((el["elig_balls"] >= lr.ELIG["total"]) & (el["elig_pressure_balls"] >= lr.ELIG["pressure"])
                       & (el["elig_pressure_matches"] >= lr.ELIG["pressure_matches"])
                       & (el["elig_recent_balls"] >= lr.ELIG["recent"]))).sum())
        z = r[["z_P_hat", "z_D_hat", "z_C_hat"]]
        corr = float(np.corrcoef(r["rating"], r["elig_pressure_balls"])[0, 1])
        tag = LABEL[disc]
        checks += [
            (f"{tag}: nobody below an eligibility rule", f"{below} below, {len(r)} rated", below == 0),
            (f"{tag}: no duplicate players", f"{r.index.duplicated().sum()} dup",
             not r.index.duplicated().any() and not r["player_name"].duplicated().any()),
            (f"{tag}: z-scores mean 0, SD 1", f"max |mean| {z.mean().abs().max():.1e}, SD {z.std(ddof=0).round(6).tolist()}",
             bool((z.mean().abs() < 1e-9).all() and np.allclose(z.std(ddof=0), 1))),
            (f"{tag}: shrunk values between raw and prior", str(between_ok), between_ok),
            (f"{tag}: |corr(rating, pressure balls)| < 0.3", f"{corr:+.3f}", abs(corr) < 0.3),
        ]

    eb_df = pd.DataFrame(eb_rows)
    eb_df.to_csv(OUTPUTS / "eb_params.csv", index=False)
    f5, f6 = fig_shrinkage(pool_tabs), fig_pressure_vs_usual(rated)
    check_df = pd.DataFrame(checks, columns=["check", "value", "pass"])

    # --- console summary
    show = eb_df.assign(k=eb_df["k"].round(1), prior=eb_df["prior"].round(4), tau2=eb_df["tau2"].map("{:.2e}".format))
    print("Shrinkage parameters (k = balls for U and D; m = pseudo-matches for C):")
    print(show[["discipline", "quantity", "prior", "tau2", "k", "guard", "n_players"]].to_string(index=False))
    for disc in ("bat", "bowl"):
        r = rated[disc].head(20)
        print(f"\nTop 20 {FILE[disc]}:")
        print(r[["rank", "player_name", "ipl_2026_team", "rating", "P_hat", "U", "D_hat", "C_hat",
                 "elig_pressure_balls"]].round(1).to_string(index=False))
    print()
    print(check_df.assign(**{"pass": check_df["pass"].map({True: "PASS", False: "FAIL"})}).to_string(index=False))
    print(f"\nWrote eb_params.csv, ratings_batters.csv, ratings_bowlers.csv, top10_batters.md, top10_bowlers.md, "
          f"{f5.name}, {f6.name}")
    if not check_df["pass"].all():
        sys.exit(1)


if __name__ == "__main__":
    main()
