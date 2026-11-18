"""
91_report_numbers.py — report step 1: every number the report quotes that is not already in a table in outputs/.

Run from the repo root (after 01-09):
    python src/91_report_numbers.py

Inputs  (data/processed/): balls.parquet, matches.parquet, players.parquet, ball_values.parquet
        (outputs/): wp_model_eval.md, ratings_*.csv, bootstrap_ranks_*.csv, sensitivity.csv, final_top10_*.csv
Outputs (outputs/): report_numbers.json   flat dict of scalars (raw values; the report formats them)
                    report_picks.csv      ranks 1-15 per list: team(s), role, phase mix, RR status and fit,
                                          plus the rating columns the report tables use
                    report_coverage.csv   T1: matches by tier and status

Method parameters are read from the pipeline modules themselves, so the report cannot drift from the code.
Exits with code 1 if any acceptance check fails.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rating as lr  # noqa: E402
import lib_wp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
FILE = {"bat": "batters", "bowl": "bowlers"}
IPL_SHORT = lr.IPL_SHORT


def module(name: str):
    spec = importlib.util.spec_from_file_location(f"m{name[:2]}", SRC / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def md_table(path: Path, heading: str) -> pd.DataFrame:
    """First pipe table after the line that starts with `heading` in a markdown file we generated."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(heading))
    rows = []
    for l in lines[start + 1:]:
        if l.startswith("|"):
            rows.append([c.strip() for c in l.strip().strip("|").split("|")])
        elif rows:
            break
    return pd.DataFrame(rows[2:], columns=rows[0])


def params(N: dict) -> None:
    m03, m07, m09 = module("03_leverage"), module("07_reliability"), module("09_top10_tables")
    p = lr.Params()
    N.update({
        "p.seed": lib_wp.SEED, "p.pressure_pct": 100 * m03.PRESSURE_Q, "p.crunch_pct": 100 * (1 - m03.CRUNCH_Q),
        "p.pressure_top": 100 * (1 - m03.PRESSURE_Q), "p.dead_pts": 100 * m03.DEAD_LI_RAW,
        "p.n_outcomes": len(lib_wp.OUTCOMES), "p.folds": module("02_wp_model").CV_FOLDS,
        "p.dead_li_raw": m03.DEAD_LI_RAW, "p.x_clip": m03.X_CLIP, "p.late_b": lib_wp.LATE_B,
        "p.w_level": 100 * p.weights[0], "p.w_shift": 100 * p.weights[1], "p.w_cons": 100 * p.weights[2],
        "p.half_life": p.half_life, "p.k_cap": p.k_cap, "p.m_min": p.m_range[0],
        "p.elig_total": lr.ELIG["total"], "p.elig_pressure": lr.ELIG["pressure"],
        "p.elig_matches": lr.ELIG["pressure_matches"], "p.elig_recent": lr.ELIG["recent"],
        "p.match_min_balls": lr.PRESSURE_MATCH_MIN_BALLS, "p.eb_total": lr.EB_POOL["total"],
        "p.eb_pressure": lr.EB_POOL["pressure"], "p.offset_min_balls": lr.OFFSET_MIN_BALLS,
        "p.offset_min_players": lr.OFFSET_MIN_PLAYERS, "p.n_boot": m07.N_BOOT,
        "p.time_min_pressure": m07.TIME_MIN_PRESSURE, "p.n_ceiling": m07.N_CEILING_SPLITS,
        "p.n_variants": len(m07.VARIANTS), "p.core_min": m07.CORE_MIN_VARIANTS,
        "p.secure_pct": 100 * m09.BANDS[0][0], "p.probable_pct": 100 * m09.BANDS[1][0],
        "p.flag_margin_pct": 100 * (m09.FLAG_MARGIN - 1), "p.flag_season_pct": 100 * m09.FLAG_ONE_SEASON,
        "p.flag_ipl_min": m09.FLAG_IPL_MIN,
        "p.recent_from": min(lr.RECENT_YEARS), "p.recent_to": max(lr.RECENT_YEARS), "p.anchor": p.anchor_year,
    })
    for t, w in lr.TIER_WEIGHT.items():
        N[f"p.tw_{t}"] = w
    for y in range(2022, 2027):
        N[f"p.rec_{y}"] = float(lr.recency_weight(y))


def data_numbers(N: dict) -> pd.DataFrame:
    m = pd.read_parquet(PROC / "matches.parquet")
    b = pd.read_parquet(PROC / "balls.parquet", columns=["match_id", "innings", "is_legal", "match_date", "comp_tier"])
    v = pd.read_parquet(PROC / "ball_values.parquet", columns=["match_id"])
    N.update({
        "d.matches": len(m), "d.matches_with_balls": b["match_id"].nunique(), "d.deliveries": len(b),
        "d.legal": int(b["is_legal"].sum()), "d.scored_balls": len(v), "d.scored_matches": v["match_id"].nunique(),
        "d.first_date": pd.Timestamp(b["match_date"].min()).strftime("%b %Y"),
        "d.last_date": pd.Timestamp(b["match_date"].max()).strftime("%b %Y"),
        "d.dls_no_target": len(lib_wp.DLS_NO_TARGET),
        "d.no_result": int(m["status"].isin(["no_result", "abandoned"]).sum()),
        "d.tied": int((m["status"] == "tie_super_over").sum()),
        "d.players": len(pd.read_parquet(PROC / "players.parquet", columns=["player_id"])),
    })
    for t, n in m["comp_tier"].value_counts().items():
        N[f"d.matches_{t}"] = int(n)
    cov = m.pivot_table(index="comp_tier", columns="status", values="match_id", aggfunc="count", fill_value=0)
    cov["total"] = cov.sum(axis=1)
    return cov.reset_index()


def wp_numbers(N: dict) -> None:
    f = OUTPUTS / "wp_model_eval.md"
    h = md_table(f, "## Held-out metrics").set_index("innings")
    for inn in ("1", "2"):
        for col, key in (("Brier", "brier"), ("Brier (coin flip)", "brier_coin"), ("AUC", "auc"),
                         ("CV ECE (10 bins)", "ece")):
            N[f"wp.{key}_{inn}"] = float(h.loc[inn, col])
    tr = md_table(f, "## Training data").set_index("innings")
    N["wp.train_matches"] = int(tr.loc["1", "matches"])
    N["wp.train_balls"] = int(tr["balls"].astype(int).sum())
    s = md_table(f, "## Sanity checks").set_index(md_table(f, "## Sanity checks").columns[0])
    for k in ("6_off_1", "4_off_1", "12_off_3", "6_off_6", "1_off_6", "30_off_6"):
        N[f"wp.{k}"] = float(s.loc[k, "value"])
    acc = md_table(f, "## Acceptance checks")
    last = acc[acc["check"].str.contains("innings 2, 1 balls left")]["value"].iloc[0]
    N["wp.last_ball_dwp"], N["wp.last_ball_se"] = map(float, re.findall(r"[-+]?\d+\.\d+", last)[:2])
    N["wp.last_ball_n"] = int(re.search(r"n (\d+)", last).group(1))
    lg = md_table(f, "### Model WP against actual results").set_index(["runs needed", "balls left"])
    N["wp.state_4off1_n"] = int(lg.loc[("4", "1"), "balls"])


def leverage_numbers(N: dict) -> None:
    v = pd.read_parquet(PROC / "ball_values.parquet")
    b = pd.read_parquet(PROC / "balls.parquet", columns=["match_id", "innings", "innings_ball_num", "phase", "overid"])
    d = v.merge(b, on=["match_id", "innings", "innings_ball_num"], how="left", validate="1:1")
    cut = d.groupby("innings")["LI"].quantile(lr.Params().pressure_q)
    pb = d[d["is_pressure"]]
    glob = d["LI"] >= d["LI"].quantile(0.80)
    N.update({
        "lev.cut_1": cut[1], "lev.cut_2": cut[2],
        "lev.dead_pct": 100 * d["is_dead"].mean(), "lev.crunch_pct": 100 * d["is_crunch"].mean(),
        "lev.pressure_balls": len(pb),
        "lev.median_li_1": pb.loc[pb["innings"] == 1, "LI"].median(),
        "lev.median_li_2": pb.loc[pb["innings"] == 2, "LI"].median(),
        "lev.p95_li": d["LI"].quantile(0.95), "lev.p99_li": d["LI"].quantile(0.99), "lev.max_li": d["LI"].max(),
        "lev.inn1_pp_share_all": 100 * ((pb["innings"] == 1) & (pb["phase"] == "powerplay")).mean(),
        "lev.over1_flag": 100 * d.loc[(d["innings"] == 1) & (d["overid"] == 1), "is_pressure"].mean(),
        "lev.over2_flag": 100 * d.loc[(d["innings"] == 1) & (d["overid"] == 2), "is_pressure"].mean(),
        "lev.chase_close_pct": 100 * pb.loc[pb["innings"] == 2, "wp0"].between(0.2, 0.8).mean(),
        "lev.global_cut_chase_pct": 100 * (d.loc[glob, "innings"] == 2).mean(),
        "lev.stake_w1": lr.stake_weights(d, lr.set_flags(d, lr.Params()))[1],  # D45
    })
    for inn in (1, 2):
        mix = pb[pb["innings"] == inn]["phase"].value_counts(normalize=True)
        for ph in ("powerplay", "middle", "death"):
            N[f"lev.mix_{inn}_{ph}"] = 100 * mix.get(ph, 0.0)


def validation_numbers(N: dict) -> None:
    v = pd.read_csv(OUTPUTS / "pressure_validation.csv", dtype={"innings": str})
    a = v[v["table"] == "mean_abs_wp_change"]
    for _, r in a.iterrows():
        key = r["phase"] if r["band"] == "all" else r["band"]
        N[f"val.abswp_{key}"] = 100 * r["value"]
    w = v[v["table"] == "pressure_minus_routine_within_cell"]
    for _, r in w.iterrows():
        for col in ("value", "lo90", "hi90"):
            N[f"val.w_{r['innings']}_{r['phase']}_{r['metric']}_{col}"] = r[col]
    c = v[v["table"] == "pressure_minus_routine_crude"]
    for _, r in c.iterrows():
        N[f"val.c_{r['innings']}_{r['phase']}_{r['metric']}"] = r["value"]
    cc = pd.read_csv(OUTPUTS / "impact_centering_check.csv").set_index("discipline")
    for disc in ("bat", "bowl"):
        N[f"cent.{disc}_before"] = cc.loc[disc, "mean raw shift before"]
        N[f"cent.{disc}_after"] = cc.loc[disc, "mean raw shift after"]
        N[f"cent.{disc}_corr_before"] = cc.loc[disc, "corr(role-mix, raw shift) before"]
        N[f"cent.{disc}_corr_after"] = cc.loc[disc, "corr(role-mix, raw shift) after"]
    n = pd.read_csv(OUTPUTS / "naive_vs_leverage.csv", dtype={"innings": str}).set_index("innings")
    N["naive.chase_usual_dead_below"] = n.loc["2", "usual_share_dead_or_below_median_pct"]
    N["naive.chase_missed"] = n.loc["2", "pressure_missed_by_usual_pct"]
    N["naive.crunch_missed"] = n.loc["2", "crunch_missed_by_usual_pct"]


def time_split_numbers(N: dict) -> None:
    t = pd.read_csv(OUTPUTS / "time_split.csv")
    keys = {"(1) full rating": "rating", "(2) pressure level (shrunk)": "level", "(3) raw pressure Impact": "raw",
            "(4) shift alone (raw)": "shift", "(5) usual approach (death / RRR>10 SR or econ)": "usual",
            "(extra) usual level (shrunk)": "ulevel", "(extra) consistency (shrunk)": "cons",
            "(variant) V3 chases only (global cut)": "v3", "(variant) V4 pressure level only": "v4",
            "(variant) V12 level = raw WPA": "v12", "(variant) V13 innings weighted equally": "v13"}
    for _, r in t.iterrows():
        k = f"ts.{r['discipline']}_{keys[r['predictor']]}"
        N[k], N[k + "_lo"], N[k + "_hi"] = r["spearman"], r["lo90"], r["hi90"]
        N[f"ts.{r['discipline']}_n"] = int(r["n"])
    c = pd.read_csv(OUTPUTS / "time_split_ceiling.csv").set_index("discipline")
    for d in ("bat", "bowl"):
        N[f"ts.{d}_ceiling"] = c.loc[d, "max_attainable_correlation"]
        N[f"ts.{d}_split_half"] = c.loc[d, "split_half_spearman"]


def rating_numbers(N: dict) -> None:
    for disc in ("bat", "bowl"):
        r = pd.read_csv(OUTPUTS / f"ratings_{FILE[disc]}.csv")
        p = lr.Params()
        sd = np.array([r[f"z_{c}"].std(ddof=0) for c in ("P_hat", "D_hat", "C_hat")])
        eff = 100 * np.array(p.weights) * sd / (np.array(p.weights) * sd).sum()
        N[f"eff.{disc}_level"], N[f"eff.{disc}_shift"], N[f"eff.{disc}_cons"] = eff
        N[f"pool.{disc}"] = len(r)
        N[f"pool.{disc}_median_pressure_balls"] = r["elig_pressure_balls"].median()
        N[f"pool.{disc}_shift_min"], N[f"pool.{disc}_shift_max"] = r["D_hat"].min(), r["D_hat"].max()
        f = pd.read_csv(OUTPUTS / f"final_top10_{FILE[disc]}.csv")
        for band in ("secure", "probable", "marginal"):
            N[f"conf.{disc}_{band}"] = int((f["confidence"] == band).sum())
        N[f"top10.{disc}_ipl_teams"] = int((f["ipl_2026_team"] != "none").sum())
        N[f"top10.{disc}_rr"] = int((f["ipl_2026_team"] == "Rajasthan Royals").sum())
        s = pd.read_csv(OUTPUTS / "sensitivity.csv")
        s = s[(s["discipline"] == disc) & (s["headline_rank"] <= 10)]
        N[f"sens.{disc}_core"] = int(s["core_pick"].sum())
        ss = pd.read_csv(OUTPUTS / "sensitivity_summary.csv").set_index(["variant", "discipline"])
        N[f"sens.{disc}_v13_overlap"] = int(ss.loc[("V13 innings weighted equally", disc), "top10_overlap"])  # D45
        cx = pd.read_csv(OUTPUTS / "context_players.csv")  # D46
        cx = cx[cx["discipline"] == disc]
        mu, rr = cx[cx["group"] == "most_used"], cx[cx["group"] == "rr"]
        best = mu.loc[mu["share_top10"].idxmax()]
        N[f"ctx.{disc}_n"] = len(mu)
        N[f"ctx.{disc}_best_name"], N[f"ctx.{disc}_best_rank"] = best["player_name"], int(best["rank"])
        N[f"ctx.{disc}_best_share"] = 100 * best["share_top10"]
        N[f"ctx.{disc}_n_level"] = int((mu["furthest_behind_on"] == "pressure level").sum())
        N[f"ctx.{disc}_n_top30"] = int((mu["rank"] <= 30).sum())
        N[f"ctx.rr_{disc}_n"] = len(rr)
        N[f"ctx.rr_{disc}_top10"] = int((rr["rank"] <= 10).sum())
        nxt = rr[rr["rank"] > 10].iloc[0]
        N[f"ctx.rr_{disc}_next_name"], N[f"ctx.rr_{disc}_next_rank"] = nxt["player_name"], int(nxt["rank"])
        N[f"ctx.rr_{disc}_next_share"] = 100 * nxt["share_top10"]
        b = pd.read_csv(OUTPUTS / f"bootstrap_ranks_{FILE[disc]}.csv")
        for k in (11, 12):
            N[f"boot.{disc}_share_{k}"] = 100 * b.loc[b["headline_rank"] == k, "share_top10"].iloc[0]
            N[f"boot.{disc}_name_{k}"] = b.loc[b["headline_rank"] == k, "player_name"].iloc[0]


def picks_table() -> pd.DataFrame:
    m08 = module("08_rr_fit")
    d = m08.load()
    players = pd.read_parquet(PROC / "players.parquet")
    needs = m08.needs_table(d, m08.team_names())
    rr = needs[needs["team"] == m08.RR]
    need_cells = {(x.discipline, x.phase, x.role) for x in rr.itertuples()
                  if x.usable and x.rank in m08.NEED_RANKS}
    franchises = set(IPL_SHORT)
    nat = {}
    for _, p in players.iterrows():
        teams = [t.strip() for t in str(p["all_teams"]).split(",")]
        nat[p["player_id"]] = next((t for t in teams if t not in franchises and not t.endswith(" A")
                                    and t != "nan"), "")
    out = []
    for disc in ("bat", "bowl"):
        r = pd.read_csv(OUTPUTS / f"ratings_{FILE[disc]}.csv", index_col="player_id")
        b = pd.read_csv(OUTPUTS / f"bootstrap_ranks_{FILE[disc]}.csv", index_col="player_id")
        s = pd.read_csv(OUTPUTS / "sensitivity.csv", index_col="player_id")
        s = s[s["discipline"] == disc]
        f = pd.read_csv(OUTPUTS / f"final_top10_{FILE[disc]}.csv", index_col="player_id")
        for col, lab in (("P_hat", "P_rank"), ("U", "U_rank"), ("D_hat", "D_rank"), ("C_hat", "C_rank")):
            r[lab] = r[col].rank(ascending=False, method="min").astype(int)
        r["pool_size"] = len(r)
        r["pressure_share_inn1_pct"] = 100 * r["pressure_share_inn1"]
        r["pressure_share_inn2_pct"] = 100 - r["pressure_share_inn1_pct"]
        md = pd.read_csv(OUTPUTS / "top10_match_detail.csv")
        md = md[md["discipline"] == disc].drop_duplicates("rank").set_index("rank")
        r["best_match_share_pct"] = 100 * r["rank"].map(md["best_match_share_of_total"])
        r["total_pressure_wpa"] = r["rank"].map(md["total_pressure_wpa"])
        r["total_without_best"] = r["rank"].map(md["total_without_best_match"])
        picks = r[r["rank"] <= 15]
        cards = m08.role_cards(d, picks, disc, players).set_index("player_id")
        t = picks.join(cards[[c for c in cards.columns if c not in picks.columns]])
        t = t.join(b[["rank_p5", "rank_p95", "share_top10"]]).join(s[["n_variants_top10"]])
        t["ipl_only_rank"] = s["V9 IPL balls only"].reindex(t.index)  # D50
        # D50: one standard error of chance on raw pressure Impact (per 100 balls), and the gap to usual level
        eb = pd.read_csv(OUTPUTS / "eb_params.csv").set_index(["discipline", "quantity"])
        t["P_raw_se"] = 100 * np.sqrt(eb.loc[(disc, "D"), "sigma2"] / t["n_P"])
        t["P_gap_se"] = (t["P_raw"] - t["U"]) / t["P_raw_se"]
        t = t.join(f[["chase_pressure_rank", "confidence", "flag", "tier_mix"]])
        t["discipline"] = disc
        t["status"] = t["ipl_2026_team"].fillna("no IPL 2026 team").map(m08.status)
        t["team_short"] = t["ipl_2026_team"].map(IPL_SHORT).fillna("")
        t["national_team"] = [nat.get(i, "") for i in t.index]
        t["fit_cells"] = [", ".join(f"{ph} / {ro}" for (dd, ph, ro) in sorted(need_cells)
                                    if dd == disc and ro == x["role"] and x[f"share_{ph}"] >= m08.FIT_MIN_PHASE_SHARE)
                          for _, x in t.iterrows()]
        out.append(t.reset_index())
    return pd.concat(out, ignore_index=True)


def match_consistency_numbers(N: dict) -> None:
    """D52: picks that stay top 10 without their best pressure match, and picks above the pool's share of
    pressure matches with positive Impact."""
    mc = pd.read_csv(OUTPUTS / "match_consistency.csv")
    for disc in ("bat", "bowl"):
        t = mc[mc["discipline"] == disc]
        N[f"mc.{disc}_stay"] = int((t["rank_without_best_match"] <= 10).sum())
        N[f"mc.{disc}_above_pool"] = int((t["positive_impact_match_pct"] > t["pool_positive_impact_match_pct"]).sum())
        N[f"mc.{disc}_pool_pct"] = t["pool_positive_impact_match_pct"].iloc[0]


def chance_numbers(N: dict, picks: pd.DataFrame) -> None:
    """D50: how far raw pressure Impact moves by chance, and whether bowlers' gaps are wider than chance."""
    from scipy.stats import norm
    eb = pd.read_csv(OUTPUTS / "eb_params.csv").set_index(["discipline", "quantity"])
    for disc in ("bat", "bowl"):
        r = pd.read_csv(OUTPUTS / f"ratings_{FILE[disc]}.csv")
        N[f"eb.{disc}_P_se_median"] = 100 * np.sqrt(eb.loc[(disc, "D"), "sigma2"] / r["n_P"].median())
        N[f"eb.{disc}_D_tau2"] = eb.loc[(disc, "D"), "tau2"]
    b1 = picks[(picks["discipline"] == "bowl") & (picks["rank"] == 1)].iloc[0]
    N["eb.bowl1_expected_gaps"] = N["pool.bowl"] * 2 * norm.sf(abs(b1["P_gap_se"]))


def wp_coefficients(N: dict) -> None:
    """D49: fitted coefficients of the two regressions, for the formula box in 1.1."""
    import pickle
    with open(PROC / "wp_models.pkl", "rb") as fh:
        m = pickle.load(fh)
    N["wp.erem120"] = m["erem120"]
    for tag, key in (("f", "first"), ("c", "chase")):
        N[f"wp.{tag}0"] = float(m[key].intercept_[0])
        for i, v in enumerate(m[key].coef_[0], start=1):
            N[f"wp.{tag}{i}"] = float(v)
    eb = pd.read_csv(OUTPUTS / "eb_params.csv")
    for disc in ("bat", "bowl"):
        N[f"cons.{disc}_pool"] = 100 * eb.loc[(eb["discipline"] == disc) & (eb["quantity"] == "C"), "prior"].iloc[0]


def ordinal(n: int) -> str:
    n = int(round(n))
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def auction_numbers(N: dict, picks: pd.DataFrame) -> None:
    """D47: numbers for the auction view in section 6."""
    m08 = module("08_rr_fit")
    nd = pd.read_csv(OUTPUTS / "rr_needs.csv")
    cells = nd.drop_duplicates(["discipline", "phase", "role"])
    rr = nd[nd["team"] == m08.RR]
    need = rr[rr["usable"] & rr["rank"].isin(m08.NEED_RANKS)]
    N["rr.cells_total"], N["rr.cells_usable"] = len(cells), int(cells["usable"].sum())
    N["rr.death_usable"] = int(cells.loc[cells["phase"] == "death", "usable"].sum())
    N["rr.n_needs"] = len(need)
    N["rr.needs_txt"] = "; ".join(
        f"{x.phase} overs, {x.role} {'batting' if x.discipline == 'bat' else 'bowling'} ({ordinal(x.rank)} of 10)"
        for x in need.itertuples())
    notes = pd.read_csv(ROOT / "docs" / "availability_notes.csv").set_index("player_name")["note"]
    cx = pd.read_csv(OUTPUTS / "context_players.csv")
    for disc in ("bat", "bowl"):
        top = picks[(picks["discipline"] == disc) & (picks["rank"] <= 10)]
        N[f"auc.{disc}_top10_elsewhere"] = int(top["status"].str.startswith("at another franchise").sum())
        N[f"auc.{disc}_top10_no_team"] = int((top["status"] == "no IPL 2026 team").sum())
        nt = cx[(cx["discipline"] == disc) & (cx["group"] == "no_team")]
        N[f"auc.{disc}_no_team_n"] = len(nt)
        N[f"auc.{disc}_no_team_barred"] = int(nt["player_name"].isin(notes.index).sum())
        op = nt[~nt["player_name"].isin(notes.index)].iloc[0]
        N[f"auc.{disc}_open_name"], N[f"auc.{disc}_open_rank"] = op["player_name"], int(op["rank"])
        N[f"auc.{disc}_open_share"] = 100 * op["share_top10"]
        fit = picks[(picks["discipline"] == disc) & picks["fit_cells"].notna()
                    & (picks["status"] != "already at RR")]
        N[f"auc.{disc}_fit_n"] = len(fit)
    N["auc.no_team_barred"] = N["auc.bat_no_team_barred"] + N["auc.bowl_no_team_barred"]
    N["auc.no_team_n"] = N["auc.bat_no_team_n"] + N["auc.bowl_no_team_n"]


def main() -> None:
    N: dict = {}
    params(N)
    cov = data_numbers(N)
    wp_numbers(N)
    leverage_numbers(N)
    validation_numbers(N)
    rating_numbers(N)
    time_split_numbers(N)
    wp_coefficients(N)
    picks = picks_table()
    auction_numbers(N, picks)
    chance_numbers(N, picks)
    match_consistency_numbers(N)
    for k, v in list(N.items()):
        if isinstance(v, (np.integer,)):
            N[k] = int(v)
        elif isinstance(v, (np.floating,)):
            N[k] = float(v)
    (OUTPUTS / "report_numbers.json").write_text(json.dumps(N, indent=1, sort_keys=True), encoding="utf-8")
    picks.to_csv(OUTPUTS / "report_picks.csv", index=False, float_format="%.4f")
    cov.to_csv(OUTPUTS / "report_coverage.csv", index=False)

    checks = [
        ("Scored balls match leverage_summary.md", f"{N['d.scored_balls']:,}",
         f"Scored balls: {N['d.scored_balls']:,}" in (OUTPUTS / "leverage_summary.md").read_text(encoding="utf-8")),
        ("Pressure cuts match leverage_summary.md (3 dp)", f"{N['lev.cut_1']:.3f} / {N['lev.cut_2']:.3f}",
         all(f"{N[f'lev.cut_{i}']:.3f}" in (OUTPUTS / "leverage_summary.md").read_text(encoding="utf-8")
             for i in (1, 2))),
        ("30 picks with role cards (ranks 1-15 x 2)", f"{len(picks)} rows, {int(picks['role'].isna().sum())} no role",
         len(picks) == 30 and picks["role"].notna().all()),
        ("No NaN scalars", f"{sum(1 for v in N.values() if isinstance(v, float) and np.isnan(v))} NaN",
         not any(isinstance(v, float) and np.isnan(v) for v in N.values())),
    ]
    check_df = pd.DataFrame(checks, columns=["check", "value", "pass"])
    print(f"{len(N)} numbers written.")
    print(check_df.assign(**{"pass": check_df["pass"].map({True: "PASS", False: "FAIL"})}).to_string(index=False))
    print("\nWrote report_numbers.json, report_picks.csv, report_coverage.csv")
    if not check_df["pass"].all():
        sys.exit(1)


if __name__ == "__main__":
    main()
