"""
09_top10_tables.py — Phase 2, step 8: the evidence tables for the two top-10 lists (T3 / T4).
Spec: docs/METHODOLOGY_SPEC.md sections 4.1, 4.3, 6 (T3 / T4) and 7; REVIEW_1 items 4, 5, 7, 9, 10.

Run from the repo root (after 06 and 07):
    python src/09_top10_tables.py

Inputs  (data/processed/): player_match_stats.parquet, balls.parquet, matches.parquet
        (outputs/): ratings_*.csv, bootstrap_ranks_*.csv
Outputs (outputs/): top10_batters.md, top10_bowlers.md   T3 / T4: top 20 shown, top 10 in bold
                    top10_match_detail.csv                three best / worst pressure matches per pick (D43)
                    final_top10_batters.csv, final_top10_bowlers.csv   the submission lists
                    context_players.csv   D46: the 10 eligible players with the most IPL 2025-26 balls
                                          outside each top 10, and every eligible RR player; D47: the 8
                                          best-ranked eligible players with no IPL 2026 team

Confidence band (D39) from the share of 1,000 match resamples in which the player is top 10:
secure >= 80%, probable 50-80%, marginal < 50%. Order inside a band is the point estimate only.
Chase-only pressure rank (D41): the same pressure level on innings-2 balls only. Flag (D44): high variance
if an eligibility count is within 25% of its minimum or >= 75% of pressure balls fall in one season.
Exits with code 1 if any acceptance check fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rating as lr  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

FILE = {"bat": "batters", "bowl": "bowlers"}
LABEL = {"bat": "Batters", "bowl": "Bowlers"}
SHOW = 20
BANDS = [(0.80, "secure"), (0.50, "probable"), (0.0, "marginal")]
FLAG_MARGIN = 1.25      # an eligibility count within 25% of its minimum
FLAG_ONE_SEASON = 0.75  # or one season holds >= 75% of the pressure balls


def confidence(share: pd.Series) -> pd.Series:
    return share.map(lambda s: next(lab for cut, lab in BANDS if s >= cut))


def chase_rank(pms: pd.DataFrame, disc: str, ids: pd.Index) -> pd.DataFrame:
    """REVIEW_1 item 7: the same pressure level (P = U + D, shrunk) computed on chase balls only, ranked
    within the eligible pool. Priors and k are re-estimated on chase balls."""
    ch = pms[pms["innings"] == 2]
    t, _ = lr.rate(ch, disc, ids, lr.eb_pool(ch, disc), lr.Params())
    pb = ch[(ch["discipline"] == disc) & (ch["flag"] == "pressure")].groupby("player_id")["n_balls"].sum()
    return pd.DataFrame({"chase_P_hat": 100 * t["P_hat"],
                         "chase_pressure_rank": t["P_hat"].rank(ascending=False, method="min"),
                         "chase_pressure_balls": pb.reindex(ids).fillna(0)})


def match_context() -> pd.DataFrame:
    """Date, competition and both teams for every scored innings."""
    b = pd.read_parquet(PROC / "balls.parquet", columns=["match_id", "innings", "match_date", "comp_name",
                                                         "batting_team_id", "bowling_team_id"])
    b = b[b["innings"].isin([1, 2])].drop_duplicates(["match_id", "innings"])
    m = pd.read_parquet(PROC / "matches.parquet", columns=["home_team_id", "home_team", "away_team_id", "away_team"])
    names = {**dict(zip(m["home_team_id"], m["home_team"])), **dict(zip(m["away_team_id"], m["away_team"]))}
    b["batting_team"] = b["batting_team_id"].map(names)
    b["bowling_team"] = b["bowling_team_id"].map(names)
    return b.set_index(["match_id", "innings"])


def match_detail(pms: pd.DataFrame, disc: str, top: pd.DataFrame, ctx: pd.DataFrame) -> pd.DataFrame:
    """REVIEW_1 item 9 (spec 4.3): three best and three worst pressure matches (>= 3 pressure balls, as for
    consistency) per pick by credited pressure WPA (unweighted), with the best match's share of the total."""
    s = pms[(pms["discipline"] == disc) & (pms["flag"] == "pressure") & pms["player_id"].isin(top.index)]
    g = s.groupby(["player_id", "match_id", "innings"]).agg(
        tier=("comp_tier", "first"), pressure_balls=("n_balls", "sum"), pressure_wpa=("wpa", "sum")).reset_index()
    pm = g.groupby(["player_id", "match_id"])["pressure_balls"].transform("sum")
    g = g[pm >= lr.PRESSURE_MATCH_MIN_BALLS].join(ctx, on=["match_id", "innings"])
    opp = "bowling_team" if disc == "bat" else "batting_team"
    rows = []
    for pid, r in top.iterrows():
        mine = g[g["player_id"] == pid]
        total = mine["pressure_wpa"].sum()
        best = mine.nlargest(3, "pressure_wpa").assign(kind="best")
        worst = mine.nsmallest(3, "pressure_wpa").assign(kind="worst")
        for k, (_, x) in enumerate(pd.concat([best, worst]).iterrows()):
            rows.append({
                "discipline": disc, "rank": int(r["rank"]), "player": r["player_name"], "kind": x["kind"],
                "order": k % 3 + 1, "match_id": int(x["match_id"]),
                "date": pd.Timestamp(x["match_date"]).date().isoformat(), "competition": x["comp_name"],
                "tier": x["tier"], "team": x["batting_team" if disc == "bat" else "bowling_team"],
                "opponent": x[opp], "innings": int(x["innings"]), "pressure_balls": int(x["pressure_balls"]),
                "pressure_wpa": x["pressure_wpa"], "pressure_matches": len(mine),
                "total_pressure_wpa": total,
                "total_without_best_match": total - mine["pressure_wpa"].max(),
                "best_match_share_of_total": mine["pressure_wpa"].max() / total if total > 0 else float("nan"),
            })
    return pd.DataFrame(rows)


def variance_flags(pms: pd.DataFrame, disc: str, r: pd.DataFrame) -> pd.Series:
    """REVIEW_1 item 10 (D44): 'high variance' if any eligibility count is below FLAG_MARGIN x its minimum,
    or one season holds >= FLAG_ONE_SEASON of the player's pressure balls. Descriptive; ranks unchanged."""
    s = pms[(pms["discipline"] == disc) & (pms["flag"] == "pressure") & pms["player_id"].isin(r.index)]
    by_year = s.groupby(["player_id", "year"])["n_balls"].sum().unstack(fill_value=0)
    share = by_year.max(axis=1) / by_year.sum(axis=1)
    top_year = by_year.idxmax(axis=1)
    counts = {"total": ("elig_balls", "balls"), "pressure": ("elig_pressure_balls", "pressure balls"),
              "pressure_matches": ("elig_pressure_matches", "pressure matches"),
              "recent": ("elig_recent_balls", "balls in 2025-26")}
    out = {}
    for pid, x in r.iterrows():
        why = [f"{int(x[col])} {lab} (min {lr.ELIG[k]})" for k, (col, lab) in counts.items()
               if x[col] < FLAG_MARGIN * lr.ELIG[k]]
        if share.get(pid, 0) >= FLAG_ONE_SEASON:
            why.append(f"{100 * share[pid]:.0f}% of pressure balls in {int(top_year[pid])}")
        out[pid] = "high variance: " + "; ".join(why) if why else ""
    return pd.Series(out)


def final_table(pms: pd.DataFrame, disc: str, r: pd.DataFrame) -> pd.DataFrame:
    """The submission list: rank, rating, 90% rank interval, pressure balls and their competition-tier mix."""
    top = r[r["rank"] <= 10]
    s = pms[(pms["discipline"] == disc) & (pms["flag"] == "pressure") & pms["player_id"].isin(top.index)]
    mix = s.groupby(["player_id", "comp_tier"])["n_balls"].sum().unstack(fill_value=0)
    mix = mix.reindex(columns=list(lr.TIER_WEIGHT), fill_value=0)
    pct = 100 * mix.div(mix.sum(axis=1), axis=0)
    return pd.DataFrame({
        "rank": top["rank"].astype(int), "player": top["player_name"],
        "ipl_2026_team": top["ipl_2026_team"].fillna("none"),
        "rating": top["rating"].round(1),
        "rank_interval_90": [f"{lo:.0f}-{hi:.0f}" for lo, hi in zip(top["rank_p5"], top["rank_p95"])],
        "top10_share_pct": (100 * top["share_top10"]).round(0).astype(int), "confidence": top["confidence"],
        "pressure_balls": top["elig_pressure_balls"].astype(int),
        **{f"pressure_balls_{t}": mix[t].reindex(top.index).astype(int) for t in mix.columns},
        "tier_mix": [" / ".join(f"{t} {pct.loc[pid, t]:.0f}%" for t in pct.columns if pct.loc[pid, t] >= 0.5)
                     for pid in top.index],
        "chase_pressure_rank": top["chase_pressure_rank"].astype(int),
        "flag": top["flag"],
    }).reset_index()


CONTEXT_N = 10  # most-used IPL 2025-26 players shown outside each top 10 (D46)
NO_TEAM_N = 8   # best-ranked eligible players with no IPL 2026 team (D47)
COMPONENTS = {"P_hat": "pressure level", "D_hat": "shift", "C_hat": "consistency"}


def ipl_recent_balls(disc: str) -> pd.Series:
    """IPL balls faced (batters) or legal balls bowled (bowlers) in 2025-26: how much franchises used a player."""
    key, cnt = ("striker_id", "is_ball_faced") if disc == "bat" else ("bowler_id", "is_legal")
    b = pd.read_parquet(PROC / "balls.parquet", columns=["innings", "year", "comp_tier", key, cnt])
    b = b[b["innings"].isin([1, 2]) & (b["comp_tier"] == "IPL") & b["year"].isin(lr.RECENT_YEARS)]
    return b.groupby(key)[cnt].sum()


def context_players(r: pd.DataFrame, disc: str) -> pd.DataFrame:
    """D46: (a) the CONTEXT_N eligible players outside the top 10 with the most IPL 2025-26 balls, a data
    stand-in for "names a reader expects"; (b) every eligible player in RR's IPL 2026 squad. For each, the rating
    component on which the player is furthest behind the #10 pick (nominal weight x z-score gap)."""
    r = r.assign(ipl_recent_balls=ipl_recent_balls(disc).reindex(r.index).fillna(0))
    for col in COMPONENTS:
        r[f"{col}_rank"] = r[col].rank(ascending=False, method="min")
    tenth = r[r["rank"] == 10].iloc[0]
    w = dict(zip(COMPONENTS, lr.Params().weights))
    gap = pd.DataFrame({c: w[c] * (r[f"z_{c}"] - tenth[f"z_{c}"]) for c in COMPONENTS})
    most_used = r[r["rank"] > 10].sort_values("ipl_recent_balls", ascending=False).head(CONTEXT_N).index
    rr = r[r["ipl_2026_team"] == "Rajasthan Royals"].sort_values("rank").index
    no_team = r[r["ipl_2026_team"].isna()].sort_values("rank").head(NO_TEAM_N).index
    out = []
    for group, ids in (("most_used", most_used), ("rr", rr), ("no_team", no_team)):
        t = r.loc[ids]
        out.append(pd.DataFrame({
            "discipline": disc, "group": group, "rank": t["rank"].astype(int), "player_name": t["player_name"],
            "ipl_2026_team": t["ipl_2026_team"].fillna("none"),
            "team_short": t["ipl_2026_team"].map(lr.IPL_SHORT).fillna(""),
            "ipl_recent_balls": t["ipl_recent_balls"].astype(int), "rating": t["rating"],
            "share_top10": t["share_top10"], "confidence": t["confidence"],
            "P_hat": t["P_hat"], "P_rank": t["P_hat_rank"].astype(int), "D_hat": t["D_hat"],
            "D_rank": t["D_hat_rank"].astype(int), "C_hat": t["C_hat"], "C_rank": t["C_hat_rank"].astype(int),
            "chase_pressure_rank": t["chase_pressure_rank"].astype(int),
            "ipl_pressure_balls": t["ipl_pressure_balls"].astype(int),
            "furthest_behind_on": gap.loc[ids].idxmin(axis=1).map(COMPONENTS),
            "gap_rating_points": 10 * gap.loc[ids].min(axis=1),
            "pool_size": len(r),
        }))
    return pd.concat(out).reset_index()


def load(disc: str, pms: pd.DataFrame) -> pd.DataFrame:
    r = pd.read_csv(OUTPUTS / f"ratings_{FILE[disc]}.csv", index_col="player_id")
    b = pd.read_csv(OUTPUTS / f"bootstrap_ranks_{FILE[disc]}.csv", index_col="player_id")
    r = r.join(b[["rank_median", "rank_p5", "rank_p95", "share_top10"]]).join(chase_rank(pms, disc, r.index))
    r["confidence"] = confidence(r["share_top10"])
    r["flag"] = variance_flags(pms, disc, r)
    return r.sort_values("rank")


def top_table(r: pd.DataFrame, disc: str) -> str:
    t = r.head(SHOW)

    def pr(a, b, fmt="{:.0f}"):
        return [f"{fmt.format(x)} / {fmt.format(y)}" if pd.notna(x) and pd.notna(y) else "-"
                for x, y in zip(t[a], t[b])]

    out = pd.DataFrame({
        "Rank": [f"**{k}**" if k <= 10 else str(k) for k in t["rank"]],
        "Player": t["player_name"], "IPL 2026 team": t["ipl_2026_team"].fillna("-"),
        "Confidence": t["confidence"],
        "Rating": t["rating"].round(1),
        "90% rank interval": [f"{lo:.0f}-{hi:.0f}" for lo, hi in zip(t["rank_p5"], t["rank_p95"])],
        "Top-10 share %": (100 * t["share_top10"]).round(0).astype(int),
        "Pressure level": t["P_hat"].round(1), "Usual level": t["U"].round(1), "Shift": t["D_hat"].round(1),
        "Consistency %": t["C_hat"].round(0).astype(int),
        "Pressure balls": t["elig_pressure_balls"].astype(int),
        "IPL pressure balls": t["ipl_pressure_balls"].astype(int),
        "% pressure balls in 1st inns": (100 * t["pressure_share_inn1"]).round(0).astype(int),
        "Chase-only pressure rank": t["chase_pressure_rank"].astype(int),
        "Chase pressure balls": t["chase_pressure_balls"].astype(int),
        "Pressure matches": t["c_matches"].astype(int),
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
    out["Flag"] = t["flag"].replace("", "-")
    return out.to_markdown(index=False)


def band_note(r: pd.DataFrame) -> str:
    top = r[r["rank"] <= 10]
    counts = top["confidence"].value_counts().reindex([lab for _, lab in BANDS]).fillna(0).astype(int)
    edge = r[r["rank"].between(9, 12)]
    edge_txt = ", ".join(f"#{int(x['rank'])} {x['player_name']} {100 * x['share_top10']:.0f}%" for _, x in edge.iterrows())
    flagged = top[top["flag"] != ""]
    flag_txt = "; ".join(f"#{int(x['rank'])} {x['player_name']} ({x['flag'].removeprefix('high variance: ')})"
                         for _, x in flagged.iterrows()) or "none"
    return (f"Confidence in the top 10: {counts['secure']} secure, {counts['probable']} probable, "
            f"{counts['marginal']} marginal. The order inside a band is the point estimate only. Places 9-10 "
            f"against 11-12 (share of resamples in the top 10): {edge_txt}. The intervals hold the WP model, "
            "priors and shrinkage strengths fixed, so they understate the true uncertainty. High-variance picks "
            f"(an eligibility count within {100 * (FLAG_MARGIN - 1):.0f}% of its minimum, or >= "
            f"{100 * FLAG_ONE_SEASON:.0f}% of pressure balls in one season): {flag_txt}.")


def main() -> None:
    checks, details, contexts = [], [], []
    pms = pd.read_parquet(PROC / "player_match_stats.parquet")
    ctx = match_context()
    for disc in ("bat", "bowl"):
        r = load(disc, pms)
        md = match_detail(pms, disc, r[r["rank"] <= 10], ctx)
        cp = context_players(r, disc)
        contexts.append(cp)
        details.append(md)
        fin = final_table(pms, disc, r)
        fin.to_csv(OUTPUTS / f"final_top10_{FILE[disc]}.csv", index=False)
        tier_sum = fin[[c for c in fin.columns if c.startswith("pressure_balls_")]].sum(axis=1)
        text = (f"# Top {SHOW} {FILE[disc]} by reliability rating (generated by src/09_top10_tables.py)\n\n"
                "Ranks 1-10 in bold are the submission. Levels and shift are Impact per 100 balls (0 = average "
                "outcome for the same situation; positive = helps the team's win chances). Consistency = shrunk "
                "share of pressure matches with positive win probability added. Rank interval and top-10 share: "
                "1,000 match resamples (src/07_reliability.py). Confidence: secure = top 10 in >= 80% of "
                "resamples, probable 50-80%, marginal < 50%. Pressure balls count all tiers; IPL pressure balls "
                "shows how many of them are IPL. First-innings pressure balls are mostly the new ball (overs 1-2 "
                "of a first innings are almost all flagged), so the chase-only pressure rank (same pressure "
                f"level, chase balls only, rank among the {len(r)} eligible) shows who also holds up when "
                "chasing. P / R = pressure / routine balls (plain stats on IPL + full-member T20Is).\n\n"
                + band_note(r) + "\n\n" + top_table(r, disc) + "\n")
        (OUTPUTS / f"top10_{FILE[disc]}.md").write_text(text, encoding="utf-8")
        top = r[r["rank"] <= 10]
        checks += [
            (f"{LABEL[disc]}: 10 picks, no duplicates", f"{len(top)} / {top['player_name'].nunique()}",
             len(top) == 10 and top["player_name"].nunique() == 10),
            (f"{LABEL[disc]}: every pick has an interval and a band",
             f"{int(top[['rank_p5', 'rank_p95', 'confidence']].notna().all(axis=1).sum())}/10",
             bool(top[["rank_p5", "rank_p95", "confidence"]].notna().all().all())),
            (f"{LABEL[disc]}: 3 best + 3 worst pressure matches per pick, opponent known",
             f"{len(md)} rows, {int(md['opponent'].isna().sum())} unknown opponents",
             len(md) == 60 and md["opponent"].notna().all()),
            (f"{LABEL[disc]}: final list = ratings top 10; tier mix sums to pressure balls",
             f"{len(fin)} rows", len(fin) == 10 and bool((tier_sum == fin["pressure_balls"]).all())),
            (f"{LABEL[disc]}: pressure-match counts agree with the consistency count (06)",
             "", bool((md.groupby("rank")["pressure_matches"].first()
                       == top.set_index("rank")["c_matches"].reindex(md["rank"].unique())).all())),
            (f"{LABEL[disc]}: {CONTEXT_N} most-used players outside the top 10; every eligible RR player listed",
             f"{(cp['group'] == 'most_used').sum()} / {(cp['group'] == 'rr').sum()} rows",
             bool((cp.loc[cp["group"] == "most_used", "rank"] > 10).all()
                  and (cp["group"] == "most_used").sum() == CONTEXT_N
                  and (cp["group"] == "rr").sum() == int((r["ipl_2026_team"] == "Rajasthan Royals").sum()))),
        ]
        print(f"\n{LABEL[disc]}: most-used IPL 2025-26 players outside the top 10, then RR's eligible players")
        print(cp[["group", "rank", "player_name", "ipl_recent_balls", "share_top10", "P_rank", "D_hat", "C_rank",
                  "chase_pressure_rank", "furthest_behind_on"]].round(2).to_string(index=False))
        sm = md.drop_duplicates("rank").set_index("rank")
        print(f"\n{LABEL[disc]} pressure WPA: total, without best match, best match share")
        print(sm[["player", "pressure_matches", "total_pressure_wpa", "total_without_best_match",
                  "best_match_share_of_total"]].round(2).to_string())
        print(f"\n{LABEL[disc]}: {band_note(r)}")
        print(top[["rank", "player_name", "rating", "rank_p5", "rank_p95", "share_top10", "confidence",
                   "elig_pressure_balls", "ipl_pressure_balls", "pressure_share_inn1", "chase_pressure_rank",
                   "chase_pressure_balls"]].round(2).to_string(index=False))
    pd.concat(details, ignore_index=True).to_csv(OUTPUTS / "top10_match_detail.csv", index=False, float_format="%.4f")
    pd.concat(contexts, ignore_index=True).to_csv(OUTPUTS / "context_players.csv", index=False, float_format="%.4f")
    check_df = pd.DataFrame(checks, columns=["check", "value", "pass"])
    print()
    print(check_df.assign(**{"pass": check_df["pass"].map({True: "PASS", False: "FAIL"})}).to_string(index=False))
    print("\nWrote top10_batters.md, top10_bowlers.md, top10_match_detail.csv, final_top10_batters.csv, "
          "final_top10_bowlers.csv, context_players.csv")
    if not check_df["pass"].all():
        sys.exit(1)


if __name__ == "__main__":
    main()
