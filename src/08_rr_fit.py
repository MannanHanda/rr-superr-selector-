"""
08_rr_fit.py — Phase 2, step 7 (CUTTABLE): how each pick fits Rajasthan Royals.
Spec: docs/METHODOLOGY_SPEC.md sections 5 and 7.

Run from the repo root:
    python src/08_rr_fit.py

Inputs  (data/processed/): balls.parquet, ball_values.parquet, players.parquet, matches.parquet
        (outputs/):        ratings_batters.csv, ratings_bowlers.csv
Outputs (outputs/): rr_needs.csv   IPL 2025-26 pressure-ball Impact per 100 balls for each team in each cell
                                   (batting: phase x position group; bowling: phase x pace/spin), with ranks
                    rr_fit.md      needs, a role card and fit line for every top-10 pick, alternates 11-15

Cells use IPL 2025-26 pressure balls (D33: one season is too thin). A cell is usable only if all ten teams
have >= 30 pressure balls in it; other cells are listed as "too thin to judge". RR "needs" = usable cells where
RR rank 8th-10th of the ten teams. Indicative only. A pick "fits" a need cell if its role (position group,
or pace/spin) matches and at least 30% of its 2025-26 balls fall in that cell's phase (D34). The ranking
itself is untouched (Q1).
Exits with code 1 if any acceptance check fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_rating as lr  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

RR = "Rajasthan Royals"
NEED_RANKS = (8, 9, 10)
NEEDS_YEARS = (2025, 2026)
MIN_CELL_BALLS = 30
FIT_MIN_PHASE_SHARE = 0.30
ROLE_YEARS = (2025, 2026)
PHASES = ["powerplay", "middle", "death"]
FILE = {"bat": "batters", "bowl": "bowlers"}


def position_group(order: pd.Series) -> pd.Series:
    return pd.Series(np.select([order <= 3, order <= 7], ["top order (1-3)", "middle order (4-7)"], "lower (8+)"),
                     index=order.index)


def load() -> pd.DataFrame:
    v = pd.read_parquet(PROC / "ball_values.parquet",
                        columns=["match_id", "innings", "innings_ball_num", "x_run", "x_wkt", "is_pressure", "is_dead"])
    b = pd.read_parquet(PROC / "balls.parquet", columns=[
        "match_id", "innings", "innings_ball_num", "comp_tier", "year", "phase", "batting_team_id", "bowling_team_id",
        "striker_id", "bowler_id", "batting_order", "pace_or_spin", "is_ball_faced", "is_legal", "striker_out",
        "is_bowler_wicket"])
    d = v.merge(b, on=["match_id", "innings", "innings_ball_num"], how="left", validate="1:1")
    d["bat_x"] = d["x_run"] + d["x_wkt"].where(d["striker_out"] == 1, 0.0)
    d["bowl_x"] = -(d["x_run"] + d["x_wkt"].where(d["is_bowler_wicket"] == 1, 0.0))
    d["pos_group"] = position_group(d["batting_order"])
    return d


def team_names() -> dict:
    m = pd.read_parquet(PROC / "matches.parquet", columns=["home_team_id", "home_team", "away_team_id", "away_team"])
    return {**dict(zip(m["home_team_id"], m["home_team"])), **dict(zip(m["away_team_id"], m["away_team"]))}


def needs_table(d: pd.DataFrame, names: dict) -> pd.DataFrame:
    s = d[(d["comp_tier"] == "IPL") & d["year"].isin(NEEDS_YEARS) & d["is_pressure"] & ~d["is_dead"]]
    bat = s[(s["is_ball_faced"] == 1) & (s["pos_group"] != "lower (8+)")]
    bat = bat.groupby(["phase", "pos_group", "batting_team_id"]).agg(impact=("bat_x", "mean"), balls=("bat_x", "size"))
    bat = bat.reset_index().rename(columns={"pos_group": "role", "batting_team_id": "team_id"}).assign(discipline="bat")
    bowl = s.groupby(["phase", "pace_or_spin", "bowling_team_id"]).agg(impact=("bowl_x", "mean"),
                                                                         balls=("bowl_x", "size"))
    bowl = bowl.reset_index().rename(columns={"pace_or_spin": "role", "bowling_team_id": "team_id"}).assign(
        discipline="bowl")
    t = pd.concat([bat, bowl], ignore_index=True)
    t["impact_per100"] = 100 * t["impact"]
    t["team"] = t["team_id"].map(names)
    t["rank"] = t.groupby(["discipline", "phase", "role"])["impact_per100"].rank(ascending=False, method="min")
    g = t.groupby(["discipline", "phase", "role"])
    t["n_teams"] = g["team_id"].transform("nunique")
    t["min_team_balls"] = g["balls"].transform("min")
    t["usable"] = (t["n_teams"] == 10) & (t["min_team_balls"] >= MIN_CELL_BALLS)
    return t[["discipline", "phase", "role", "team", "impact_per100", "balls", "rank", "n_teams", "min_team_balls",
              "usable"]]


def role_cards(d: pd.DataFrame, picks: pd.DataFrame, disc: str, players: pd.DataFrame) -> pd.DataFrame:
    core = d[d["comp_tier"].isin(lr.CORE_TIERS) & d["match_id"].notna()]
    pl = players.set_index("player_id")
    rows = []
    for pid, r in picks.iterrows():
        if disc == "bat":
            mine = core[(core["striker_id"] == pid) & (core["is_ball_faced"] == 1)]
        else:
            mine = core[(core["bowler_id"] == pid) & (core["is_legal"] == 1)]
        recent = mine[mine["year"].isin(ROLE_YEARS)]
        use = recent if len(recent) else mine
        phase_share = use["phase"].value_counts(normalize=True).reindex(PHASES).fillna(0)
        main_phase = phase_share.idxmax()
        card = {
            "player_id": pid, "rank": int(r["rank"]), "player": r["player_name"],
            **{f"share_{p}": phase_share[p] for p in PHASES},
            "ipl_2026_team": r["ipl_2026_team"] if pd.notna(r["ipl_2026_team"]) else "no IPL 2026 team",
            "main_phase": main_phase,
            "phase_mix": " / ".join(f"{p[:2].upper() if p != 'middle' else 'MID'} {100 * phase_share[p]:.0f}%"
                                    for p in PHASES),
            "pressure_share_inn1_pct": 100 * r["pressure_share_inn1"],
        }
        if disc == "bat":
            order = use["batting_order"].median()
            card.update(batting_hand=pl.loc[pid, "batting_hand"], usual_position=order,
                        role=position_group(pd.Series([order])).iloc[0])
        else:
            card.update(bowling_type=pl.loc[pid, "bowling_type"], role=pl.loc[pid, "pace_or_spin"])
        rows.append(card)
    return pd.DataFrame(rows)


def status(team: str) -> str:
    if team == RR:
        return "already at RR"
    return "no IPL 2026 team" if team == "no IPL 2026 team" else f"at another franchise ({team})"


def main() -> None:
    d = load()
    names = team_names()
    players = pd.read_parquet(PROC / "players.parquet")
    needs = needs_table(d, names)
    needs.to_csv(OUTPUTS / "rr_needs.csv", index=False, float_format="%.3f")

    rr = needs[needs["team"] == RR].copy()
    rr["need"] = rr["usable"] & rr["rank"].isin(NEED_RANKS)
    need_cells = {(r.discipline, r.phase, r.role) for r in rr[rr["need"]].itertuples()}

    lines = ["# RR fit (generated by src/08_rr_fit.py)", "",
             "Indicative only: two IPL seasons (2025-26) of pressure balls per team. A cell is judged only if all "
             f"ten teams have at least {MIN_CELL_BALLS} pressure balls in it. The ranking is not changed by this "
             "section (Q1); it describes how each data-chosen pick would fit.", "",
             "## RR's pressure-ball record, IPL 2025-26 (Impact per 100 pressure balls; rank of 10 teams, 1 = best)",
             ""]
    show = rr.assign(cell=rr["phase"] + " / " + rr["role"]).sort_values(["discipline", "phase", "role"])
    show["verdict"] = np.select([show["need"], ~show["usable"]], ["NEED", "too thin to judge"], "")
    show["rank"] = show["rank"].where(show["usable"])
    lines += [show[["discipline", "cell", "impact_per100", "balls", "rank", "min_team_balls", "verdict"]]
              .rename(columns={"min_team_balls": "fewest balls (any team)"})
              .to_markdown(index=False, floatfmt=".1f"), ""]

    cards = {}
    for disc in ("bat", "bowl"):
        ratings = pd.read_csv(OUTPUTS / f"ratings_{FILE[disc]}.csv", index_col="player_id")
        picks = ratings[ratings["rank"] <= 15]
        c = role_cards(d, picks, disc, players)
        # fits (D34): role matches a need cell and >= 30% of the player's balls fall in that cell's phase
        c["fit_cells"] = [
            ", ".join(f"{ph} / {ro}" for (dd, ph, ro) in sorted(need_cells)
                      if dd == disc and ro == r["role"] and r[f"share_{ph}"] >= FIT_MIN_PHASE_SHARE)
            for _, r in c.iterrows()]
        c["fits_need"] = c["fit_cells"] != ""
        c["status"] = c["ipl_2026_team"].map(status)
        cards[disc] = c
        lines += [f"## {FILE[disc].capitalize()}: role cards", ""]
        for _, r in c.iterrows():
            if r["rank"] == 11:
                lines += ["", f"Alternates (ranks 11-15):", ""]
            extra = (f"{r['batting_hand']}, usually bats {r['usual_position']:.0f} ({r['role']})" if disc == "bat"
                     else f"{r['bowling_type']} ({r['role']})")
            fit = (f"**fits RR need: {r['fit_cells']}**" if r["fits_need"]
                   else "no direct RR need cell")
            lines.append(f"- {r['rank']}. {r['player']} — {extra}; main phase {r['main_phase']} ({r['phase_mix']}); "
                         f"{r['pressure_share_inn1_pct']:.0f}% of pressure balls in the first innings; "
                         f"{r['status']}; {fit}.")
        lines.append("")
    (OUTPUTS / "rr_fit.md").write_text("\n".join(lines), encoding="utf-8")

    # --- acceptance checks
    cells = needs.groupby(["discipline", "phase", "role"]).agg(n_teams=("n_teams", "first"),
                                                                 usable=("usable", "first"))
    ipl26 = set(players["ipl_2026_team"].dropna())
    top_cards = pd.concat([cards[x][cards[x]["rank"] <= 10].assign(discipline=x) for x in cards])
    key = ["player", "main_phase", "role", "status"]
    checks = [
        ("Teams in the data are the ten IPL 2026 franchises", f"{needs['team'].nunique()} teams",
         set(needs["team"]) == ipl26 and len(ipl26) == 10),
        ("Ten teams in every usable cell; thin cells flagged",
         f"{int(cells['usable'].sum())} usable, {int((~cells['usable']).sum())} flagged of {len(cells)}",
         bool((cells.loc[cells["usable"], "n_teams"] == 10).all()) and cells["usable"].any()),
        ("RR present in every cell", f"{len(rr)} of {len(cells)}", len(rr) == len(cells)),
        ("Every top-10 pick has a role card", f"{len(top_cards)} cards, {int(top_cards[key].isna().sum().sum())} gaps",
         len(top_cards) == 20 and not top_cards[key].isna().any().any()),
    ]
    check_df = pd.DataFrame(checks, columns=["check", "value", "pass"])

    # --- console summary
    print("RR in IPL 2025-26 pressure balls (rank of 10; NEED = 8th-10th in a usable cell):")
    print(show[["discipline", "cell", "impact_per100", "balls", "rank", "min_team_balls", "verdict"]].round(1)
          .to_string(index=False))
    for disc in ("bat", "bowl"):
        c = cards[disc][cards[disc]["rank"] <= 10]
        print(f"\nTop-10 {FILE[disc]}: {int(c['fits_need'].sum())} fit a need cell; "
              f"{int((c['status'] == 'already at RR').sum())} already at RR; "
              f"{int((c['status'] == 'no IPL 2026 team').sum())} with no IPL 2026 team")
        print(c[["rank", "player", "main_phase", "role", "fit_cells", "status"]].to_string(index=False))
    print()
    print(check_df.assign(**{"pass": check_df["pass"].map({True: "PASS", False: "FAIL"})}).to_string(index=False))
    print("\nWrote rr_needs.csv, rr_fit.md")
    if not check_df["pass"].all():
        sys.exit(1)


if __name__ == "__main__":
    main()
