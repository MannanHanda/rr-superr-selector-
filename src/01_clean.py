"""
01_clean.py — Phase 0: turn the raw data pack into clean, analysis-ready tables.

Run from the repo root:
    python src/01_clean.py

Inputs  (data/raw/):  ball_by_ball.csv, matches.csv, competitions.csv, teams.csv,
                      playing_eleven.csv, competition_team_player_mapping.csv
Outputs (data/processed/):
    matches.parquet   one row per match, with status / DLS / tier flags and innings totals
    balls.parquet     one row per delivery, with correct ball/run accounting and
                      the match state BEFORE the ball (score, wickets, balls left, target)
    players.parquet   one row per player: name, volumes, seasons, teams, IPL 2026 team
Report  (outputs/):   data_quality.md

Accounting rules (verified against match results; see outputs/data_quality.md):
  * Legal ball      = not a wide and not a no-ball. No-balls are extras_type
                      'Overstep' or 'other'. Legal balls per over come out at 6.
  * Ball faced      = every delivery except wides (no-balls count as faced).
  * Total runs      = runs + extras1_runs + extras_2_runs.
  * Batter runs     = runs (off the bat).
  * Bowler conceded = runs off the bat + wide runs + the no-ball penalty.
                      Byes, leg-byes and penalty runs are NOT charged to the bowler.
  * Bowler wicket   = Caught, Bowled, LBW, Stump, Hit Wicket.
                      Run outs, retired out and obstructing the field are not credited.
  * Revised overs   = first_inn_revised_overs / second_inn_revised_overs are in BALLS.
  * Innings 3 and 4 = super overs.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
REPORTS = ROOT / "outputs"

FULL_MEMBERS = {
    "India", "Pakistan", "Australia", "England", "New Zealand", "South Africa",
    "West Indies", "Sri Lanka", "Bangladesh", "Afghanistan", "Zimbabwe", "Ireland",
}
NO_BALL_TYPES = {"Overstep", "other"}
BOWLER_WICKETS = {"Caught", "Bowled", "LBW", "Stump", "Hit Wicket"}
PHASES = [(1, 6, "powerplay"), (7, 15, "middle"), (16, 20, "death")]


def read_csv(name: str, **kw) -> pd.DataFrame:
    path = RAW / name
    if not path.exists():
        sys.exit(f"Missing {path}. Copy the data pack CSVs into data/raw/ first.")
    # keep_default_na=False stops pandas turning the literal string 'None' into NaN
    return pd.read_csv(path, low_memory=False, keep_default_na=False, na_values=[""], **kw)


def clean_matches(m: pd.DataFrame, comps: pd.DataFrame) -> pd.DataFrame:
    m = m.merge(comps, on="comp_id", how="left")
    m["match_date"] = pd.to_datetime(m["match_date"])
    m["year"] = m["match_date"].dt.year
    res = m["result"].fillna("").str.lower()

    m["status"] = np.select(
        [res.str.contains("abandon"), res.str.contains("no result"),
         res.str.contains("tied|super over")],
        ["abandoned", "no_result", "tie_super_over"],
        default="completed",
    )
    m["is_dls"] = res.str.contains(r"d/l|dls") | m["revised_target"].notna()

    is_ipl = m["comp_name"].str.startswith("IPL")
    is_emerging = m["match_format"].eq("T20") & ~is_ipl
    both_full = m["home_team"].isin(FULL_MEMBERS) & m["away_team"].isin(FULL_MEMBERS)
    m["comp_tier"] = np.select(
        [is_ipl, is_emerging, both_full],
        ["IPL", "Emerging", "T20I_full"],
        default="T20I_associate",
    )
    return m


def clean_balls(b: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    b = b.copy()
    b["extras_type"] = b["extras_type"].fillna("None")

    # ---- ball and run accounting -------------------------------------------------
    b["is_wide"] = b["extras_type"].eq("wide")
    b["is_noball"] = b["extras_type"].isin(NO_BALL_TYPES)
    b["is_legal"] = ~(b["is_wide"] | b["is_noball"])
    b["is_ball_faced"] = ~b["is_wide"]
    b["total_runs"] = b["runs"] + b["extras1_runs"] + b["extras_2_runs"]
    b["batter_runs"] = b["runs"]
    b["bowler_runs"] = b["runs"] + np.where(b["is_wide"] | b["is_noball"], b["extras1_runs"], 0)
    b["is_dot_faced"] = b["is_ball_faced"] & (b["batter_runs"] == 0)
    b["is_bowler_wicket"] = b["is_wicket"] & b["dismissal_type"].isin(BOWLER_WICKETS)
    b["striker_out"] = b["is_wicket"] & (b["dismissed_player_id"] == b["striker_id"])
    b["is_super_over"] = b["innings"] > 2

    # ---- match context -----------------------------------------------------------
    meta_cols = ["match_id", "match_date", "year", "season", "comp_id", "comp_name",
                 "match_format", "comp_tier", "stage", "knock_out", "venue_id",
                 "venue_country", "home_team_id", "status", "is_dls", "win_team_id",
                 "first_inn_revised_overs", "second_inn_revised_overs", "revised_target"]
    b = b.merge(m[meta_cols], on="match_id", how="left")

    # ---- state BEFORE each ball, per innings -------------------------------------
    b = b.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)
    g = b.groupby(["match_id", "innings"], sort=False)
    b["score_before"] = g["total_runs"].cumsum() - b["total_runs"]
    b["wickets_before"] = g["is_wicket"].cumsum() - b["is_wicket"].astype(int)
    b["legal_balls_before"] = g["is_legal"].cumsum() - b["is_legal"].astype(int)

    max_balls = np.where(
        b["innings"] == 1, b["first_inn_revised_overs"],
        np.where(b["innings"] == 2, b["second_inn_revised_overs"], 6),
    )
    b["max_balls"] = pd.Series(max_balls, index=b.index).fillna(120).astype(int)
    b.loc[b["is_super_over"], "max_balls"] = 6
    b["balls_remaining"] = (b["max_balls"] - b["legal_balls_before"]).clip(lower=0)

    b["phase"] = "death"
    for lo, hi, name in PHASES:
        b.loc[b["overid"].between(lo, hi), "phase"] = name
    b.loc[b["is_super_over"], "phase"] = "super_over"

    # ---- chase state (innings 2 only) --------------------------------------------
    inn_tot = (b[b["innings"] <= 2].groupby(["match_id", "innings"])["total_runs"].sum()
               .unstack().rename(columns={1: "inn1_total", 2: "inn2_total"}))
    b = b.merge(inn_tot[["inn1_total"]], left_on="match_id", right_index=True, how="left")
    target = b["revised_target"].fillna(b["inn1_total"] + 1)
    is_chase = b["innings"] == 2
    b["target"] = np.where(is_chase, target, np.nan)
    b["runs_needed"] = np.where(is_chase, b["target"] - b["score_before"], np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        b["req_run_rate"] = np.where(
            is_chase & (b["balls_remaining"] > 0),
            b["runs_needed"] * 6 / b["balls_remaining"], np.nan)
        b["cur_run_rate"] = np.where(
            b["legal_balls_before"] > 0,
            b["score_before"] * 6 / b["legal_balls_before"], np.nan)

    # ---- outcome label for a win-probability model -------------------------------
    b["batting_team_won"] = np.where(
        b["win_team_id"].notna(), (b["win_team_id"] == b["batting_team_id"]).astype(float), np.nan)
    # Usable for modelling: a result exists, normal innings
    b["use_for_model"] = b["status"].isin(["completed", "tie_super_over"]) & ~b["is_super_over"] \
        & b["batting_team_won"].notna()

    drop = ["first_inn_revised_overs", "second_inn_revised_overs", "delivery_ist_time"]
    return b.drop(columns=drop)


def build_players(b: pd.DataFrame, mapping: pd.DataFrame, comps: pd.DataFrame) -> pd.DataFrame:
    names = pd.concat([
        b[["striker_id", "striker_name"]].set_axis(["player_id", "player_name"], axis=1),
        b[["bowler_id", "bowler_name"]].set_axis(["player_id", "player_name"], axis=1),
        mapping[["player_id", "player_name"]],
    ])
    name = names.groupby("player_id")["player_name"].agg(lambda s: s.mode().iat[0])

    bat = b.groupby("striker_id").agg(
        balls_faced=("is_ball_faced", "sum"), bat_runs=("batter_runs", "sum"),
        bat_matches=("match_id", "nunique"), batting_hand=("batting_type", lambda s: s.mode().iat[0]))
    bowl = b.groupby("bowler_id").agg(
        legal_balls_bowled=("is_legal", "sum"), runs_conceded=("bowler_runs", "sum"),
        bowl_wickets=("is_bowler_wicket", "sum"), bowl_matches=("match_id", "nunique"),
        bowling_type=("bowling_type", lambda s: s.mode().iat[0]),
        pace_or_spin=("pace_or_spin", lambda s: s.mode().iat[0]))

    involved = pd.concat([
        b[["striker_id", "year", "comp_tier"]].set_axis(["player_id", "year", "comp_tier"], axis=1),
        b[["bowler_id", "year", "comp_tier"]].set_axis(["player_id", "year", "comp_tier"], axis=1),
    ]).drop_duplicates()
    span = involved.groupby("player_id").agg(first_year=("year", "min"), last_year=("year", "max"),
                                             tiers=("comp_tier", lambda s: ",".join(sorted(set(s)))))

    mp = mapping.merge(comps[["comp_id", "comp_name"]], on=["comp_id", "comp_name"], how="left")
    teams = mp.groupby("player_id")["team_name"].agg(lambda s: ", ".join(sorted(set(s))))
    ipl26 = mp[mp["comp_name"].eq("IPL 2026")].groupby("player_id")["team_name"].first()

    p = (pd.DataFrame({"player_name": name}).join(bat).join(bowl).join(span)
         .join(teams.rename("all_teams")).join(ipl26.rename("ipl_2026_team")))
    p.index.name = "player_id"
    for c in ["balls_faced", "bat_runs", "bat_matches", "legal_balls_bowled",
              "runs_conceded", "bowl_wickets", "bowl_matches"]:
        p[c] = p[c].fillna(0).astype(int)
    return p.reset_index()


def quality_report(b: pd.DataFrame, m: pd.DataFrame, p: pd.DataFrame) -> str:
    lines = ["# Data quality report (generated by src/01_clean.py)\n"]
    lines.append(f"- Matches in matches.csv: {len(m)}; with ball-by-ball data: {b.match_id.nunique()}")
    lines.append(f"- Deliveries: {len(b):,}; legal: {int(b.is_legal.sum()):,}; wides: {int(b.is_wide.sum())}; "
                 f"no-balls: {int(b.is_noball.sum())}")
    lines.append("\n## Matches by tier and status\n")
    lines.append(m.pivot_table(index="comp_tier", columns="status", values="match_id",
                               aggfunc="count", fill_value=0).to_markdown())
    lines.append("\n## Matches by year and tier\n")
    lines.append(m.pivot_table(index="year", columns="comp_tier", values="match_id",
                               aggfunc="count", fill_value=0).to_markdown())

    # reconciliation of computed innings totals against the result text
    t = (b[~b.is_super_over].groupby(["match_id", "innings"]).total_runs.sum().unstack()
         .rename(columns={1: "t1", 2: "t2"}))
    d = m.set_index("match_id").join(t)
    ok, bad = 0, []
    for mid, r in d.iterrows():
        res = str(r.result)
        mr = re.search(r"by (\d+) runs?", res, re.I)
        mw = re.search(r"by (\d+) wickets?", res, re.I)
        if pd.isna(r.get("t2")):
            continue
        if mr:
            good = r.t1 - r.t2 == int(mr.group(1))
        elif mw:
            good = r.t2 > r.t1 or pd.notna(r.revised_target)
        else:
            continue
        ok += good
        if not good:
            bad.append(f"  - {mid}: {res} (inn1 {r.t1:.0f}, inn2 {r.t2:.0f}, revised target {r.revised_target})")
    lines.append(f"\n## Run-total reconciliation\n\n- Results that reconcile with computed totals: {ok}")
    lines.append(f"- Results that do not: {len(bad)} (all expected to be DLS or super-over games)")
    lines.extend(bad)

    lpo = b[~b.is_super_over].groupby(["match_id", "innings", "overid"]).is_legal.sum()
    lines.append(f"\n- Overs with exactly 6 legal balls: {(lpo == 6).mean():.1%} "
                 "(the rest are incomplete overs at the end of an innings)")
    dls_no_target = m[m.is_dls & m.revised_target.isna() & m.status.eq("completed")]
    lines.append(f"- DLS games without a revised_target (chase target may be wrong): "
                 f"{', '.join(map(str, dls_no_target.match_id)) or 'none'}")
    lines.append(f"- Super-over matches: {b[b.is_super_over].match_id.nunique()}")
    lines.append(f"- Impact-player rows in playing_eleven: see is_impact (IPL 2023+)")
    lines.append(f"- bowl_speed missing (0): {(b.bowl_speed.fillna(0) == 0).mean():.1%} — do not rely on it")
    lines.append(f"- Deliveries usable for a win-probability model (result known, not super over): "
                 f"{int(b.use_for_model.sum()):,}")

    lines.append("\n## Player volumes\n")
    lines.append(f"- Players: {len(p)}; batters with >=300 balls faced: {(p.balls_faced >= 300).sum()}; "
                 f"bowlers with >=300 legal balls: {(p.legal_balls_bowled >= 300).sum()}")
    lines.append(f"- Players in an IPL 2026 squad: {p.ipl_2026_team.notna().sum()}")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    comps = read_csv("competitions.csv")
    matches = read_csv("matches.csv")
    balls = read_csv("ball_by_ball.csv")
    mapping = read_csv("competition_team_player_mapping.csv")

    m = clean_matches(matches, comps)
    b = clean_balls(balls, m)
    p = build_players(b, mapping, comps)

    m.to_parquet(OUT / "matches.parquet", index=False)
    b.to_parquet(OUT / "balls.parquet", index=False)
    p.to_parquet(OUT / "players.parquet", index=False)
    report = quality_report(b, m, p)
    (REPORTS / "data_quality.md").write_text(report, encoding="utf-8")

    print(f"matches.parquet  {len(m):>7,} rows")
    print(f"balls.parquet    {len(b):>7,} rows, {b.shape[1]} columns")
    print(f"players.parquet  {len(p):>7,} rows")
    print("Wrote outputs/data_quality.md")


if __name__ == "__main__":
    main()
