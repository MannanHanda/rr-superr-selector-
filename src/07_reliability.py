"""
07_reliability.py — Phase 2, step 6: how sure are we of the rankings?
Spec: docs/METHODOLOGY_SPEC.md section 4 and 7.

Run from the repo root:
    python src/07_reliability.py

Inputs  (data/processed/): player_match_stats.parquet, ball_values.parquet, balls.parquet
        (outputs/):        ratings_batters.csv, ratings_bowlers.csv, eb_params.csv (via lib_rating re-estimate)
Outputs (outputs/): bootstrap_ranks_batters.csv, bootstrap_ranks_bowlers.csv   rank intervals (4.1)
                    time_split.csv                                             2022-24 -> 2025-26 test (4.2)
                    time_split_ceiling.csv                                     noise ceiling of that test (D40)
                    sensitivity.csv, sensitivity_summary.csv                   13 variants (4.4)
                    figures/f7_rank_intervals.png, figures/f8_time_split.png

4.1 Bootstrap: resample matches with replacement (1,000 times, seed 42). WP model, leverage, pressure cuts,
    tier offsets, priors, k and the eligible pool are held fixed; raw sums, shrunk values, ratings and ranks
    are recomputed from player x match sufficient statistics with the same formula as 06.
4.2 Time split: rate on 2022-24 only (recency anchored at 2024); correlate predictors with raw pressure
    Impact in 2025-26 for players with >= 75 pressure balls (all tiers, as eligibility, D38) in both periods.
4.4 Sensitivity: V1-V13 re-rank the headline eligible pool (held fixed, D32).
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
from scipy import sparse
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rating as lr  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
FIGS = OUTPUTS / "figures"

SEED = 42
N_BOOT = 1000
N_BOOT_PLAYERS = 1000
TIME_MIN_PRESSURE = 75
N_CEILING_SPLITS = 200
EARLY, LATE = (2022, 2023, 2024), (2025, 2026)
# D48: the same time split for four existing variants' full ratings, against the same headline outcome
TS_VARIANTS = {
    "(variant) V3 chases only (global cut)": dict(global_share=0.20),
    "(variant) V4 pressure level only": dict(weights=(1.0, 0.0, 0.0)),
    "(variant) V12 level = raw WPA": dict(level="wpa"),
    "(variant) V13 innings weighted equally": dict(stake_weight=False),
    "(variant) V14 shift split into runs and wickets": dict(split_shift=True),
}
N_TS_BASE = 7  # predictors (1)-(5) and the two extras
CORE_MIN_VARIANTS = 10
FILE = {"bat": "batters", "bowl": "bowlers"}
LABEL = {"bat": "Batters", "bowl": "Bowlers"}
INK, INK2, MUTED, GRID, BLUE, ORANGE = "#0b0b0b", "#52514e", "#a3a29c", "#e4e3df", "#2a78d6", "#eb6834"

VARIANTS = {
    "V1 cut at 80th pct": dict(pressure_q=0.80),
    "V2 cut at 70th pct": dict(pressure_q=0.70),
    "V3 global top-20% cut": dict(global_share=0.20),
    "V4 weights 100/0/0": dict(weights=(1.0, 0.0, 0.0)),
    "V5 weights 40/20/40": dict(weights=(0.40, 0.20, 0.40)),
    "V6 weights 34/33/33": dict(weights=(0.34, 0.33, 0.33)),
    "V7 no recency decay": dict(half_life=None),
    "V8 one-year half-life": dict(half_life=1.0),
    "V9 IPL balls only": dict(tiers=("IPL",)),
    "V10 tiers equal, no offsets": dict(tier_weight={t: 1.0 for t in lr.TIER_WEIGHT}, use_offsets=False),
    "V11 no run/wicket split": dict(split_parts=False),
    "V12 level = raw WPA": dict(level="wpa"),
    "V13 innings weighted equally": dict(stake_weight=False),
    "V14 shift split runs/wickets": dict(split_shift=True),
}
# variants that change the ball-level build (pressure flags, weights, tiers) need new sufficient statistics
REBUILD = {"pressure_q", "global_share", "half_life", "tiers", "tier_weight", "use_offsets", "stake_weight"}


# ---------------------------------------------------------------- 4.1 bootstrap

SUM_COLS = ["rows", "n_balls", "w", "w2", "w_x_run", "w_x_wkt", "w_x_tot", "w_x_run2", "w_x_wkt2", "w_x_tot2",
            "wpa", "w_wpa", "w_wpa2"]


def boot_matrices(pms: pd.DataFrame, disc: str, rated: pd.Index, matches: pd.Index) -> dict:
    """Sparse player x match matrices of every sufficient statistic, so a resample is one matrix product."""
    s = pms[(pms["discipline"] == disc) & pms["player_id"].isin(rated) & (pms["flag"] != "dead")]
    pidx = pd.Series(np.arange(len(rated)), index=rated)
    midx = pd.Series(np.arange(len(matches)), index=matches)
    shape = (len(rated), len(matches))

    def mat(df: pd.DataFrame, col: str):
        return sparse.csr_matrix((df[col].to_numpy(float), (pidx[df["player_id"]].to_numpy(),
                                                            midx[df["match_id"]].to_numpy())), shape=shape)

    mats = {}
    for flag, tag in (("pressure", "P"), ("routine", "R")):
        g = s[s["flag"] == flag].groupby(["player_id", "match_id"])[SUM_COLS].sum().reset_index()
        for col in SUM_COLS:
            mats[f"{tag}_{col}"] = mat(g, col)
    m = s[s["flag"] == "pressure"].groupby(["player_id", "match_id"]).agg(
        n=("n_balls", "sum"), wpa=("wpa", "sum"), om=("omega", "first")).reset_index()
    m = m[m["n"] >= lr.PRESSURE_MATCH_MIN_BALLS].assign(one=1.0)
    m["om2"] = m["om"] ** 2
    m["om_pos"] = m["om"] * (m["wpa"] > 0)
    for col, name in (("one", "c_matches"), ("om", "c_w"), ("om2", "c_w2"), ("om_pos", "c_wpos")):
        mats[name] = mat(m, col)
    return mats


def sums_from_counts(mats: dict, counts: np.ndarray, rated: pd.Index) -> tuple[pd.DataFrame, pd.DataFrame]:
    sums = pd.DataFrame({k: v @ counts for k, v in mats.items() if k[:2] in ("P_", "R_")}, index=rated)
    for k in sums.columns:  # a player with no balls of a kind has NaN sums, as in lr.player_sums
        tag = k[:2]
        sums.loc[sums[f"{tag}w"] == 0, k] = np.nan
    cons = pd.DataFrame({k: mats[k] @ counts for k in ("c_matches", "c_w", "c_w2", "c_wpos")}, index=rated)
    cons = cons.replace({"c_w": {0: np.nan}})
    cons["c_raw"] = cons["c_wpos"] / cons["c_w"]
    cons["c_neff"] = cons["c_w"] ** 2 / cons["c_w2"]
    return sums, cons


def bootstrap(pms: pd.DataFrame, rated: dict, ebs: dict, p: lr.Params) -> tuple[dict, dict]:
    matches = pd.Index(np.sort(pms["match_id"].unique()))
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(matches), size=(N_BOOT, len(matches)))
    out, repro = {}, {}
    for disc in ("bat", "bowl"):
        ids = rated[disc]
        mats = boot_matrices(pms, disc, ids, matches)
        # un-resampled run must reproduce 06 exactly
        s0, c0 = sums_from_counts(mats, np.ones(len(matches)), ids)
        base = lr.rate_from_sums(s0, c0, ids, p, ebs[disc])
        ref, _ = lr.rate(pms, disc, ids, None, p, eb=ebs[disc])
        repro[disc] = (float((base["rating"] - ref["rating"].reindex(base.index)).abs().max()),
                       bool((base["rank"] == ref["rank"].reindex(base.index)).all()))
        ranks = np.empty((N_BOOT, len(ids)))
        for b in range(N_BOOT):
            counts = np.bincount(draws[b], minlength=len(matches)).astype(float)
            s, c = sums_from_counts(mats, counts, ids)
            ranks[b] = lr.rate_from_sums(s, c, ids, p, ebs[disc])["rank"].reindex(ids).to_numpy()
        out[disc] = pd.DataFrame(ranks, columns=ids)
    return out, repro


# ---------------------------------------------------------------- 4.2 time split

def usual_definition_stat(balls: pd.DataFrame, disc: str) -> pd.Series:
    """The common approach, early period: SR (batters) or minus economy (bowlers) in overs 16-20 or
    chase required rate above 10, IPL + T20I_full. Higher = better for both."""
    b = balls[balls["year"].isin(EARLY) & balls["comp_tier"].isin(lr.CORE_TIERS)]
    b = b[(b["overid"] >= 16) | ((b["innings"] == 2) & (b["req_run_rate"] > 10))]
    if disc == "bat":
        f = b[b["is_ball_faced"] == 1].groupby("striker_id").agg(r=("batter_runs", "sum"), n=("batter_runs", "size"))
        return 100 * f["r"] / f["n"]
    g = b.groupby("bowler_id").agg(r=("bowler_runs", "sum"), n=("is_legal", "sum"))
    return -6 * g["r"] / g["n"].replace(0, np.nan)


def spearman_ci(x: pd.Series, y: pd.Series, rng) -> tuple[int, float, float, float]:
    j = pd.concat([x, y], axis=1).dropna()
    n = len(j)
    rho = spearmanr(j.iloc[:, 0], j.iloc[:, 1])[0]
    a, b = j.iloc[:, 0].to_numpy(), j.iloc[:, 1].to_numpy()
    boots = []
    for _ in range(N_BOOT_PLAYERS):
        i = rng.integers(0, n, n)
        boots.append(spearmanr(a[i], b[i])[0])
    return n, rho, float(np.nanquantile(boots, 0.05)), float(np.nanquantile(boots, 0.95))


def noise_ceiling(pl: pd.DataFrame, disc: str, ids: pd.Index, rng) -> dict:
    """Split-half reliability of the late outcome (raw pressure Impact, 2025-26): split matches at random into
    two halves, correlate players' halves (Spearman), Spearman-Brown to full length, average over
    N_CEILING_SPLITS splits. sqrt(reliability) is the highest correlation any predictor could reach."""
    s = pl[(pl["discipline"] == disc) & (pl["flag"] == "pressure") & pl["player_id"].isin(ids)]
    g = s.groupby(["player_id", "match_id"])[["w", "w_x_tot"]].sum().reset_index()
    pid = pd.Index(ids)
    mids = pd.Index(g["match_id"].unique())
    pi, mi = pid.get_indexer(g["player_id"]), mids.get_indexer(g["match_id"])
    W = sparse.csr_matrix((g["w"], (pi, mi)), shape=(len(pid), len(mids)))
    X = sparse.csr_matrix((g["w_x_tot"], (pi, mi)), shape=(len(pid), len(mids)))
    rs = []
    for _ in range(N_CEILING_SPLITS):
        half = rng.integers(0, 2, len(mids)).astype(float)
        with np.errstate(invalid="ignore", divide="ignore"):  # a player with every match in one half
            a = (X @ half) / (W @ half)
            b = (X @ (1 - half)) / (W @ (1 - half))
        ok = np.isfinite(a) & np.isfinite(b)
        rs.append(spearmanr(a[ok], b[ok])[0])
    r = float(np.mean(rs))
    rel = 2 * r / (1 + r) if r > 0 else 0.0
    return {"discipline": disc, "n": len(ids), "split_half_spearman": r, "split_half_lo90": float(np.quantile(rs, 0.05)),
            "split_half_hi90": float(np.quantile(rs, 0.95)), "reliability_spearman_brown": rel,
            "max_attainable_correlation": float(np.sqrt(rel))}


def time_split(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pe = lr.build_pms(d, lr.variant(years=EARLY, anchor_year=2024))[0]
    pl = lr.build_pms(d, lr.variant(years=LATE, half_life=None))[0]
    balls = pd.read_parquet(PROC / "balls.parquet", columns=[
        "match_id", "innings", "year", "comp_tier", "overid", "req_run_rate", "is_ball_faced", "is_legal",
        "striker_id", "bowler_id", "batter_runs", "bowler_runs"])
    sc = d[["match_id", "innings"]].drop_duplicates()
    balls = balls.merge(sc, on=["match_id", "innings"])  # scored innings only
    rng = np.random.default_rng(SEED)
    rows, ceil = [], []
    for disc in ("bat", "bowl"):
        ee, _ = lr.eligibility(pe, disc)
        el, _ = lr.eligibility(pl, disc)
        ids = ee.index[ee["elig_pressure_balls"] >= TIME_MIN_PRESSURE].intersection(
            el.index[el["elig_pressure_balls"] >= TIME_MIN_PRESSURE])
        early, _ = lr.rate(pe, disc, ids, lr.eb_pool(pe, disc), lr.variant(anchor_year=2024))
        ls = lr.player_sums(pl, disc)
        y = (ls["P_w_x_tot"] / ls["P_w"]).reindex(ids)
        preds = {
            "(1) full rating": early["rating"], "(2) pressure level (shrunk)": early["P_hat"],
            "(3) raw pressure Impact": early["P_raw"], "(4) shift alone (raw)": early["D_raw"],
            "(5) usual approach (death / RRR>10 SR or econ)": usual_definition_stat(balls, disc),
            "(extra) usual level (shrunk)": early["U"],
            "(extra) consistency (shrunk)": early["C_hat"],
        }
        for name, kw in TS_VARIANTS.items():
            vp = lr.variant(years=EARLY, anchor_year=2024, **kw)
            ve = lr.build_pms(d, vp)[0] if REBUILD & set(kw) else pe
            preds[name] = lr.rate(ve, disc, ids, lr.eb_pool(ve, disc), vp)[0]["rating"]
        for name, x in preds.items():
            n, rho, lo, hi = spearman_ci(x.reindex(ids), y, rng)
            rows.append({"discipline": disc, "predictor": name, "n": n, "spearman": rho, "lo90": lo, "hi90": hi})
        ceil.append(noise_ceiling(pl, disc, ids, rng))
    return pd.DataFrame(rows), pd.DataFrame(ceil)


# ---------------------------------------------------------------- 4.4 sensitivity

def sensitivity(d: pd.DataFrame, pms: pd.DataFrame, rated: dict, head: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rank_cols, summary = {disc: {} for disc in rated}, []
    for name, kw in VARIANTS.items():
        p = lr.variant(**kw)
        vp = lr.build_pms(d, p)[0] if REBUILD & set(kw) else pms
        for disc in ("bat", "bowl"):
            sums = lr.player_sums(vp, disc)
            ids = rated[disc].intersection(sums.index[(sums["P_w"] > 0) & (sums["R_w"] > 0)])
            t, _ = lr.rate(vp, disc, ids, lr.eb_pool(vp, disc), p)
            r = t["rank"].reindex(rated[disc])
            rank_cols[disc][name] = r
            h = head[disc]["rank"].reindex(rated[disc])
            top_h, top_v = set(h.index[h <= 10]), set(r.index[r <= 10])
            summary.append({"variant": name, "discipline": disc, "players_rated": len(ids),
                            "top10_overlap": len(top_h & top_v),
                            "spearman_vs_headline": spearmanr(h[ids], r[ids])[0],
                            "dropped_out": "; ".join(head[disc].loc[list(top_h - top_v), "player_name"]),
                            "came_in": "; ".join(head[disc].loc[list(top_v - top_h), "player_name"])})
    tabs = []
    for disc in ("bat", "bowl"):
        t = pd.DataFrame(rank_cols[disc])
        t.insert(0, "headline_rank", head[disc]["rank"].reindex(t.index))
        t.insert(0, "player_name", head[disc]["player_name"].reindex(t.index))
        t.insert(0, "discipline", disc)
        t["n_variants_top10"] = (t[list(VARIANTS)] <= 10).sum(axis=1)
        t["core_pick"] = (t["headline_rank"] <= 10) & (t["n_variants_top10"] >= CORE_MIN_VARIANTS)
        tabs.append(t.sort_values("headline_rank"))
    return pd.concat(tabs), pd.DataFrame(summary)


# ---------------------------------------------------------------- figures

def style(ax, axis="x") -> None:
    ax.grid(axis=axis, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=7, colors=INK2)


def fig_intervals(br: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 5.2))
    for ax, disc in zip(axes, ("bat", "bowl")):
        t = br[disc].sort_values("headline_rank").head(20)
        y = np.arange(len(t))[::-1]
        top = t["headline_rank"] <= 10
        for yy, (_, r), is_top in zip(y, t.iterrows(), top):
            c = ORANGE if is_top else MUTED
            ax.plot([r["rank_p5"], r["rank_p95"]], [yy, yy], color=c, lw=2, solid_capstyle="round")
            ax.scatter([r["headline_rank"]], [yy], s=18, color=c, edgecolors="white", lw=0.8, zorder=3)
            sh = 100 * r["share_top10"]  # D49: one decimal if rounding would cross the 50% or 80% band edge
            lab = f"{sh:.1f}%" if (round(sh) >= 50) != (sh >= 50) or (round(sh) >= 80) != (sh >= 80) else f"{sh:.0f}%"
            ax.text(r["rank_p95"] + 1, yy, lab, fontsize=6, color=INK2, va="center")
        ax.axvline(10.5, color=INK2, lw=0.8, ls=":")
        ax.set_yticks(y, [f"{int(k)}. {n}" for k, n in zip(t["headline_rank"], t["player_name"])], fontsize=6.5)
        ax.set_xlim(0, max(45, t["rank_p95"].max() + 6))
        ax.set_xlabel("Rank (dot = headline, bar = 90% bootstrap interval)", fontsize=7, color=INK2)
        ax.set_title(LABEL[disc], fontsize=9, color=INK, loc="left")
        style(ax)
    fig.suptitle("How secure is each place? Rank intervals from 1,000 match resamples\n"
                 "(% = share of resamples in which the player is top 10)", fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    path = FIGS / "f7_rank_intervals.png"
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


def fig_time_split(ts: pd.DataFrame, ceil: pd.DataFrame) -> Path:
    order = list(dict.fromkeys(ts["predictor"]))
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 1.6 + 0.33 * len(order)), sharey=True)
    y = np.arange(len(order))[::-1]
    for ax, disc in zip(axes, ("bat", "bowl")):
        t = ts[ts["discipline"] == disc].set_index("predictor").reindex(order)
        colors = [BLUE if p.startswith(("(1)", "(2)")) else MUTED for p in order]
        ax.barh(y, t["spearman"], color=colors, height=0.55)
        ax.errorbar(t["spearman"], y, xerr=[t["spearman"] - t["lo90"], t["hi90"] - t["spearman"]],
                    fmt="none", ecolor=INK2, elinewidth=0.8, capsize=2)
        ax.axvline(0, color=INK2, lw=0.8)
        n_var = sum(p.startswith("(variant)") for p in order)
        if n_var:  # separate our predictors from the variants' full ratings
            ax.axhline(n_var - 0.5, color=GRID, lw=1.0)
        c = float(ceil.set_index("discipline").loc[disc, "max_attainable_correlation"])
        ax.axvline(c, color=ORANGE, lw=1.2, ls="--")
        ax.text(c, y.max() + 0.6, f" noise ceiling {c:.2f}", fontsize=6.5, color=ORANGE, va="bottom", ha="left")
        ax.set_xlim(-0.6, 0.9)
        ax.set_ylim(-0.6, y.max() + 1.3)
        ax.set_title(f"{LABEL[disc]} (n = {int(t['n'].max())})", fontsize=9, color=INK, loc="left")
        style(ax)
    fig.supxlabel("Spearman correlation with 2025-26 raw pressure Impact", fontsize=8, color=INK2)
    axes[0].set_yticks(y, order, fontsize=7)
    # D48: title states what holds; the rating's own bars are labelled (1) on the chart
    bw = ts[ts["discipline"] == "bowl"].set_index("predictor")
    best = bw["spearman"].idxmax()
    best_lab = best.split(") ", 1)[1].replace(" (shrunk)", "")
    fig.suptitle(f"Does 2022-24 predict 2025-26 pressure Impact?\nBowlers: {best_lab} does best "
                 f"({bw.loc[best, 'spearman']:.2f}); batters: no measure clearly does\n"
                 "(bars = 90% interval; dashed = the most any predictor could reach, given outcome noise)",
                 fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    path = FIGS / "f8_time_split.png"
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


# ---------------------------------------------------------------- main

def main() -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    pms = pd.read_parquet(PROC / "player_match_stats.parquet")
    p = lr.Params()
    head, rated, ebs = {}, {}, {}
    for disc in ("bat", "bowl"):
        head[disc] = pd.read_csv(OUTPUTS / f"ratings_{FILE[disc]}.csv", index_col="player_id")
        rated[disc] = head[disc].index
        _, ebs[disc] = lr.rate(pms, disc, rated[disc], lr.eb_pool(pms, disc), p)

    # 4.1 bootstrap
    boot, repro = bootstrap(pms, rated, ebs, p)
    br = {}
    for disc in ("bat", "bowl"):
        b = boot[disc]
        t = pd.DataFrame({
            "player_name": head[disc]["player_name"], "headline_rank": head[disc]["rank"],
            "rank_median": b.median(), "rank_p5": b.quantile(0.05), "rank_p95": b.quantile(0.95),
            "share_top10": (b <= 10).mean(), "share_top20": (b <= 20).mean(),
        }).sort_values("headline_rank")
        t["top20"] = t["headline_rank"] <= 20
        t.to_csv(OUTPUTS / f"bootstrap_ranks_{FILE[disc]}.csv", float_format="%.3f")
        br[disc] = t

    # 4.2 time split, 4.4 sensitivity (both rebuild sufficient statistics from ball level)
    d = lr.load_balls()
    ts, ceil = time_split(d)
    ts.to_csv(OUTPUTS / "time_split.csv", index=False, float_format="%.4f")
    ceil.to_csv(OUTPUTS / "time_split_ceiling.csv", index=False, float_format="%.4f")
    sens, sens_sum = sensitivity(d, pms, rated, head)
    sens.to_csv(OUTPUTS / "sensitivity.csv", float_format="%.0f")
    sens_sum.to_csv(OUTPUTS / "sensitivity_summary.csv", index=False, float_format="%.3f")

    f7, f8 = fig_intervals(br), fig_time_split(ts, ceil)

    # --- acceptance checks
    checks = []
    for disc in ("bat", "bowl"):
        err, same_rank = repro[disc]
        t20 = br[disc][br[disc]["top20"]]
        checks += [
            (f"{LABEL[disc]}: un-resampled run reproduces 06", f"max rating diff {err:.1e}, ranks same {same_rank}",
             err < 1e-9 and same_rank),
            (f"{LABEL[disc]}: {N_BOOT} resamples", str(len(boot[disc])), len(boot[disc]) == N_BOOT),
            (f"{LABEL[disc]}: every top-20 player has an interval", f"{t20[['rank_p5', 'rank_p95']].notna().all(axis=1).sum()}/20",
             bool(len(t20) == 20 and t20[["rank_p5", "rank_p95"]].notna().all().all())),
        ]
    n_var = sens_sum.groupby("discipline")["variant"].nunique()
    checks += [
        (f"All {len(VARIANTS)} variants present (both lists)", n_var.to_dict().__str__(), bool((n_var == len(VARIANTS)).all())),
        ("Time-split table has n and intervals", f"{len(ts)} rows",
         bool(ts[["n", "lo90", "hi90"]].notna().all().all() and len(ts) == 2 * (N_TS_BASE + len(TS_VARIANTS)))),
        ("Noise ceiling for both lists", f"{ceil['max_attainable_correlation'].round(2).tolist()}",
         len(ceil) == 2 and ceil["max_attainable_correlation"].notna().all()),
    ]
    check_df = pd.DataFrame(checks, columns=["check", "value", "pass"])

    # --- console summary
    for disc in ("bat", "bowl"):
        t = br[disc].head(10)
        print(f"\nTop 10 {FILE[disc]}: headline rank, 90% interval, share of resamples in top 10, variants in top 10")
        v = sens[sens["discipline"] == disc].set_index(sens[sens["discipline"] == disc].index)
        for pid, r in t.iterrows():
            print(f"  {int(r['headline_rank']):2d}. {r['player_name']:<24} {int(r['rank_p5']):>3}-{int(r['rank_p95']):<3} "
                  f"{100 * r['share_top10']:3.0f}%   {int(v.loc[pid, 'n_variants_top10'])}/{len(VARIANTS)}")
    print("\nTime split (Spearman with 2025-26 raw pressure Impact, 90% interval):")
    tsp = ts.assign(ci=ts["lo90"].round(2).astype(str) + " to " + ts["hi90"].round(2).astype(str))
    print(tsp.pivot(index="predictor", columns="discipline", values="spearman").round(2)
          .join(tsp.pivot(index="predictor", columns="discipline", values="ci").add_suffix("_90ci")).to_string())
    print(f"n players: {ts.groupby('discipline')['n'].max().to_dict()}")
    print("Noise ceiling (split-half reliability of the 2025-26 outcome):")
    print(ceil.round(3).to_string(index=False))
    print("\nSensitivity (top-10 overlap with headline):")
    print(sens_sum.pivot(index="variant", columns="discipline", values="top10_overlap").reindex(VARIANTS).to_string())
    for disc in ("bat", "bowl"):
        core = sens[(sens["discipline"] == disc) & sens["core_pick"]]["player_name"].tolist()
        print(f"Core {FILE[disc]} (top 10 in >= {CORE_MIN_VARIANTS}/{len(VARIANTS)} variants): {len(core)}: {', '.join(core)}")
    print()
    print(check_df.assign(**{"pass": check_df["pass"].map({True: "PASS", False: "FAIL"})}).to_string(index=False))
    print(f"\nWrote bootstrap_ranks_*.csv, time_split.csv, sensitivity.csv, sensitivity_summary.csv, {f7.name}, {f8.name}")
    if not check_df["pass"].all():
        sys.exit(1)


if __name__ == "__main__":
    main()
