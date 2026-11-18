"""
92_build_report.py — report step 2: fill reports/report_template.html from outputs/ and write reports/report.html.

Run from the repo root (after 91):
    python src/92_build_report.py

Inputs  (reports/): report_template.html   the prose, with tokens
        (outputs/): report_numbers.json, report_picks.csv, report_coverage.csv and the other CSVs named below,
                    figures/*.png
Output  (reports/): report.html            one self-contained file (figures embedded as base64), A4 print CSS

Tokens in the template:
    {{key}} or {{key|spec}}   a number from report_numbers.json, or a pick field as {{bat3.P_hat|.1f}}
                              (disc + rank + "." + column of report_picks.csv); spec is a Python format spec,
                              or "ord" (1st, 2nd ...), "int", "name", or "abs" + spec (absolute value)
    {{table:name}}            a table built below from outputs/ CSVs
    {{fig:f1}}                outputs/figures/f1_*.png as an embedded image
    {{REPO_URL}}              left as is (placeholder for the owner)
A block <script type="text/x-why"> holds one line per pick, "bat|Player name|text with tokens"; the build fails
if any pick in the top 10 has no line or a line names a player who is not in the top 10. The build also fails on
any token it cannot resolve, so every number in the report comes from a file in outputs/.
"""

from __future__ import annotations

import base64
import html
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
FIGS = OUTPUTS / "figures"
TEMPLATE = ROOT / "reports" / "report_template.html"
OUT = ROOT / "reports" / "report.html"
FILE = {"bat": "batters", "bowl": "bowlers"}
TOKEN = re.compile(r"\{\{([A-Za-z0-9_.:\-]+)(?:\|([^}]*))?\}\}")
KEEP = {"REPO_URL"}


# ---------------------------------------------------------------- formatting

def ordinal(n: int) -> str:
    n = int(round(n))
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def fmt(v, spec: str | None) -> str:
    if spec == "ord":
        return ordinal(v)
    if spec == "int":
        return f"{int(round(float(v))):,}"
    if spec and spec.startswith("abs"):
        return format(abs(float(v)), spec[3:])
    if spec in (None, "", "name"):
        if isinstance(v, float) and v.is_integer():
            return f"{int(v):,}"
        return html.escape(str(v))
    out = format(float(v), spec)
    return out.replace("-", "&minus;") if out.startswith("-") or "+" in spec else out


def esc(x) -> str:
    return html.escape("" if pd.isna(x) else str(x))


def n0(x) -> str:
    return "&ndash;" if pd.isna(x) else f"{x:,.0f}"


def signed(x, d=1) -> str:
    s = f"{x:+.{d}f}"
    return s.replace("-", "&minus;")


def table(df: pd.DataFrame, cls: str = "", num_cols: tuple = (), caption: str = "") -> str:
    head = "".join(f"<th{' class=num' if c in num_cols else ''}>{c}</th>" for c in df.columns)
    rows = []
    for _, r in df.iterrows():
        cells = "".join(f"<td{' class=num' if c in num_cols else ''}>{r[c]}</td>" for c in df.columns)
        rows.append(f"<tr>{cells}</tr>")
    cap = f"<caption>{caption}</caption>" if caption else ""
    return f'<table class="{cls}">{cap}<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


# ---------------------------------------------------------------- data

N = json.loads((OUTPUTS / "report_numbers.json").read_text(encoding="utf-8"))
PICKS = pd.read_csv(OUTPUTS / "report_picks.csv")


def pick_lookup() -> dict:
    out = {}
    for _, r in PICKS.iterrows():
        for c, v in r.items():
            out[f"{r['discipline']}{int(r['rank'])}.{c}"] = v
    return out


VALUES = {**N, **pick_lookup()}


# ---------------------------------------------------------------- tables

def t_summary(disc: str) -> str:
    f = pd.read_csv(OUTPUTS / f"final_top10_{FILE[disc]}.csv")
    p = PICKS[(PICKS["discipline"] == disc)].set_index("rank")
    df = pd.DataFrame({
        "#": f["rank"],
        "Player": [esc(x) for x in f["player"]],
        "Team": [esc(p.loc[k, "team_short"]) if pd.notna(p.loc[k, "team_short"]) else "&ndash;" for k in f["rank"]],
        "Rating": f["rating"].map("{:.1f}".format),
        "Confidence": [f'<span class="conf {c}">{c}</span>' for c in f["confidence"]],
    })
    return table(df, "compact", ("#", "Rating"))


def team_cell(r) -> str:
    parts = [p for p in (r["team_short"], r["national_team"]) if isinstance(p, str) and p]
    return " · ".join(esc(p) for p in parts) or "&ndash;"


def role_cell(r, disc: str) -> str:
    if disc == "bat":
        return f"{esc(r['batting_hand'])}, bats {r['usual_position']:.0f}; {esc(r['main_phase'])}"
    return f"{esc(r['bowling_type'])}; {esc(r['main_phase'])}"


def stats_cell(r, disc: str) -> str:
    if disc == "bat":
        return (f"SR {r['pressure_SR']:.0f} / {r['routine_SR']:.0f}<br>"
                f"Balls/out {r['pressure_balls_per_dismissal']:.0f} / {r['routine_balls_per_dismissal']:.0f}<br>"
                f"Bdry % {r['pressure_boundary_pct']:.0f} / {r['routine_boundary_pct']:.0f}")
    return (f"Econ {r['pressure_economy']:.2f} / {r['routine_economy']:.2f}<br>"
            f"Dot % {r['pressure_dot_pct']:.0f} / {r['routine_dot_pct']:.0f}<br>"
            f"Balls/wkt {r['pressure_balls_per_wicket']:.0f} / {r['routine_balls_per_wicket']:.0f}")


def t_top10(disc: str, why: dict) -> str:
    p = PICKS[(PICKS["discipline"] == disc) & (PICKS["rank"] <= 10)].sort_values("rank")
    rows = []
    for _, r in p.iterrows():
        flag = ' <span class="flag" title="high variance">&#9873;</span>' if isinstance(r["flag"], str) and r["flag"] else ""
        rows.append({
            "#": int(r["rank"]),
            "Player": f"<b>{esc(r['player_name'])}</b>{flag}<br><span class=muted>{team_cell(r)}</span>",
            "Role": role_cell(r, disc),
            "Rating": f"{r['rating']:.1f}",
            "Rank interval": f"{r['rank_p5']:.0f}&ndash;{r['rank_p95']:.0f}<br>"
                             f'<span class="conf {r["confidence"]}">{100 * r["share_top10"]:.0f}%</span>',
            "Pressure balls (IPL)": f"{r['elig_pressure_balls']:.0f} ({r['ipl_pressure_balls']:.0f})",
            "Pressure / routine": stats_cell(r, disc),
            "Why": why[(disc, r["player_name"])],
        })
    df = pd.DataFrame(rows).rename(columns={"Player": "Player<br><span class=muted>team(s)</span>"})
    return table(df, "top10", ("#", "Rating", "Rank interval", "Pressure balls (IPL)"))


def t_components(disc: str) -> str:
    p = PICKS[(PICKS["discipline"] == disc) & (PICKS["rank"] <= 10)].sort_values("rank")
    df = pd.DataFrame({
        "#": p["rank"], "Player": [esc(x) for x in p["player_name"]],
        "Pressure level": p["P_hat"].map(lambda x: signed(x)), "Usual level": p["U"].map(lambda x: signed(x)),
        "Shift": p["D_hat"].map(lambda x: signed(x)), "Consistency %": p["C_hat"].map("{:.0f}".format),
        "Pressure matches": p["c_matches"].map("{:.0f}".format),
        "1st-inns share %": p["pressure_share_inn1_pct"].map("{:.0f}".format),
        "Chase-only rank": p["chase_pressure_rank"].map("{:.0f}".format),
        "Variants top 10": p["n_variants_top10"].map(lambda x: f"{x:.0f}/{N['p.n_variants']:.0f}"),
    })
    return table(df, "compact comp", tuple(df.columns[2:]) + ("#",))


def t_wp() -> str:
    rows = [{"Innings": lab, "Brier": f"{N[f'wp.brier_{i}']:.3f}", "Brier, constant guess": f"{N[f'wp.brier_coin_{i}']:.3f}",
             "AUC": f"{N[f'wp.auc_{i}']:.2f}", "Calibration error": f"{N[f'wp.ece_{i}']:.3f}"}
            for i, lab in (("1", "First innings"), ("2", "Chase"))]
    return table(pd.DataFrame(rows), "compact", ("Brier", "Brier, constant guess", "AUC", "Calibration error"))


def t_pressure_profile() -> str:
    rows = []
    for i, lab in ((1, "First innings"), (2, "Chase")):
        rows.append({"Innings": lab, "LI cut": f"{N[f'lev.cut_{i}']:.2f}", "Median LI of pressure balls": f"{N[f'lev.median_li_{i}']:.2f}",
                     "Powerplay %": f"{N[f'lev.mix_{i}_powerplay']:.0f}", "Middle %": f"{N[f'lev.mix_{i}_middle']:.0f}",
                     "Death %": f"{N[f'lev.mix_{i}_death']:.0f}"})
    return table(pd.DataFrame(rows), "compact mini profile", tuple(list(rows[0])[1:]))


def t_abswp() -> str:
    ph = [("Powerplay", "powerplay"), ("Middle", "middle"), ("Death", "death")]
    bd = [("Low (bottom 50%)", "low"), ("Medium", "medium"), ("Pressure", "pressure"), ("Crunch (top 5%)", "crunch")]
    left = table(pd.DataFrame([{k: f"{N[f'val.abswp_{v}']:.2f}" for k, v in ph}]), "compact mini", tuple(k for k, _ in ph),
                 "By phase")
    right = table(pd.DataFrame([{k: f"{N[f'val.abswp_{v}']:.2f}" for k, v in bd}]), "compact mini", tuple(k for k, _ in bd),
                  "By leverage band")
    return f'<div class="pair">{left}{right}</div>'


def t_metrics() -> str:
    rows = [
        ("Impact per 100 balls", "As defined in 2.1, averaged and ×100.", "Same, from the bowling side."),
        ("Pressure WPA", "Sum of win probability added on pressure balls (1.00 = one match won).", "Same, from the bowling side."),
        ("Strike rate / economy", "100 × runs ÷ balls faced.", "6 × runs conceded ÷ legal balls (byes and leg-byes not charged)."),
        ("Dot %", "Balls faced with no runs off the bat.", "Legal balls with no runs charged to the bowler."),
        ("Boundary %", "Fours and sixes ÷ balls faced.", "Fours and sixes conceded ÷ legal balls."),
        ("Dismissal rate", "Balls faced per dismissal.", "Legal balls per bowler wicket (run-outs not credited)."),
    ]
    return table(pd.DataFrame(rows, columns=["Metric", "Batting", "Bowling"]), "defs")


def t_components_def() -> str:
    rows = [
        ("U", "Usual level", "Impact per 100 routine balls; run and wicket parts shrunk separately."),
        ("D", "Pressure shift", "Pressure Impact minus routine Impact, shrunk towards the pool average shift."),
        ("P = U + D", "Pressure level", "Best estimate of the player's Impact per 100 pressure balls."),
        ("C", "Consistency", f"Share of pressure matches (≥ {N['p.match_min_balls']:.0f} pressure balls) in which the player's pressure WPA was positive, shrunk towards the pool rate."),
    ]
    return table(pd.DataFrame(rows, columns=["Symbol", "Component", "Definition"]), "defs compdef")


def t_effective() -> str:
    rows = [{"List": lab, "Level": f"{N['p.w_level']:.0f} / {N[f'eff.{d}_level']:.0f}",
             "Shift": f"{N['p.w_shift']:.0f} / {N[f'eff.{d}_shift']:.0f}",
             "Consistency": f"{N['p.w_cons']:.0f} / {N[f'eff.{d}_cons']:.0f}"}
            for d, lab in (("bat", "Batters"), ("bowl", "Bowlers"))]
    return table(pd.DataFrame(rows), "compact", ("Level", "Shift", "Consistency"),
                 "Weight % (nominal / effective)")


def t_eb() -> str:
    e = pd.read_csv(OUTPUTS / "eb_params.csv").set_index(["discipline", "quantity"])
    lab = {"U_x_run": "Usual level, run part", "U_x_wkt": "Usual level, wicket part", "D": "Pressure shift",
           "C": "Consistency (pseudo-matches)"}
    rows = []
    for q, l in lab.items():
        rows.append({"Quantity": l,
                     "Batters": f"{e.loc[('bat', q), 'k']:,.0f}{' (cap)' if e.loc[('bat', q), 'guard'] else ''}",
                     "Bowlers": f"{e.loc[('bowl', q), 'k']:,.0f}{' (cap)' if e.loc[('bowl', q), 'guard'] else ''}"})
    return table(pd.DataFrame(rows), "compact", ("Batters", "Bowlers"))


def t_eligibility() -> str:
    rows = [
        ("Career volume", f"≥ {N['p.elig_total']:.0f} live balls faced", f"≥ {N['p.elig_total']:.0f} live legal balls bowled"),
        ("Pressure volume", f"≥ {N['p.elig_pressure']:.0f} pressure balls faced", f"≥ {N['p.elig_pressure']:.0f} pressure balls bowled"),
        ("Pressure matches", f"≥ {N['p.elig_matches']:.0f} matches with ≥ {N['p.match_min_balls']:.0f} pressure balls", "same"),
        ("Recent", f"≥ {N['p.elig_recent']:.0f} balls in {N['p.recent_from']:.0f}&ndash;{N['p.recent_to']:.0f}", "same"),
    ]
    return table(pd.DataFrame(rows, columns=["Rule", "Batters", "Bowlers"]), "defs")


def t_funnel() -> str:
    f = pd.read_csv(OUTPUTS / "eligibility_funnel.csv")
    piv = f.pivot(index="step", columns="discipline", values="players").reindex(f["step"].drop_duplicates())
    df = pd.DataFrame({"Step": [esc(s) for s in piv.index], "Batters": piv["bat"].map(n0).to_numpy(),
                       "Bowlers": piv["bowl"].map(n0).to_numpy()})
    return table(df, "compact", ("Batters", "Bowlers"))


def t_tiers() -> str:
    o = pd.read_csv(OUTPUTS / "tier_offsets.csv")
    g = o.groupby(["discipline", "tier"]).agg(off=("applied_offset_per_ball", "sum"), n=("n_players", "first"))
    rows = []
    for t in ("IPL", "T20I_full", "Emerging", "T20I_associate"):
        def cell(d):
            if t == "IPL":
                return "0 (reference)"
            off, n = g.loc[(d, t), "off"], g.loc[(d, t), "n"]
            if n >= N["p.offset_min_players"]:
                return f"{signed(100 * off)} ({n:.0f} players)"
            return "0 (no player qualifies)" if n == 0 else f"0 (only {n:.0f} qualif{'ies' if n == 1 else 'y'})"
        rows.append({"Tier": t.replace("_", " "), "Relevance weight": f"{N[f'p.tw_{t}']:.1f}",
                     "Offset, batters (Impact/100)": cell("bat"), "Offset, bowlers (Impact/100)": cell("bowl")})
    return table(pd.DataFrame(rows), "compact", ("Relevance weight",))


def t_recency() -> str:
    df = pd.DataFrame([{str(y): f"{N[f'p.rec_{y}']:.2f}" for y in range(2022, 2027)}])
    return table(df, "compact mini", tuple(df.columns), "Recency weight by season")


def t_context(disc: str, group: str) -> str:
    """RT fix 2 (D46): most-used IPL 2025-26 players outside the top 10, or RR's own eligible players."""
    c = pd.read_csv(OUTPUTS / "context_players.csv")
    c = c[(c["discipline"] == disc) & (c["group"] == group)]
    weak = {"pressure level": lambda r: f"pressure level ({ordinal(r['P_rank'])})",
            "shift": lambda r: f"shift ({signed(r['D_hat'])}, {ordinal(r['D_rank'])})",
            "consistency": lambda r: f"consistency ({r['C_hat']:.0f}%, {ordinal(r['C_rank'])})"}
    cols = {"#": c["rank"], "Player": [esc(x) for x in c["player_name"]]}
    if group == "most_used":
        cols["Team"] = [esc(t) if isinstance(t, str) and t else "&ndash;" for t in c["team_short"]]
        cols["IPL balls 2025&ndash;26"] = c["ipl_recent_balls"].map("{:,.0f}".format)
    cols.update({
        "Top-10 share %": (100 * c["share_top10"]).map("{:.0f}".format),
        "Pressure level": c["P_rank"].map(ordinal),
        "Chase-only": c["chase_pressure_rank"].map(ordinal),
        "IPL pressure balls": c["ipl_pressure_balls"].map("{:,.0f}".format),
    })
    if group == "most_used":  # half-width RR tables leave it out; there it is almost always pressure level
        cols["Furthest behind #10 on"] = [weak[r["furthest_behind_on"]](r) for _, r in c.iterrows()]
    df = pd.DataFrame(cols)
    num = ("#", "IPL balls 2025&ndash;26", "Top-10 share %", "Pressure level", "Chase-only", "IPL pressure balls")
    return table(df, "compact tiny ctx", num)


def t_sensitivity() -> str:
    s = pd.read_csv(OUTPUTS / "sensitivity_summary.csv")
    piv = s.pivot(index="variant", columns="discipline", values="top10_overlap").reindex(s["variant"].drop_duplicates())
    sp = s.pivot(index="variant", columns="discipline", values="spearman_vs_headline").reindex(piv.index)
    df = pd.DataFrame({"Variant": [esc(v) for v in piv.index],
                       "Bat: same top 10": piv["bat"].map(lambda x: f"{x:.0f}/10").to_numpy(),
                       "Bat: rank corr.": sp["bat"].map("{:.2f}".format).to_numpy(),
                       "Bowl: same top 10": piv["bowl"].map(lambda x: f"{x:.0f}/10").to_numpy(),
                       "Bowl: rank corr.": sp["bowl"].map("{:.2f}".format).to_numpy()})
    return table(df, "compact tiny sens", tuple(df.columns[1:]))


def t_timesplit() -> str:
    t = pd.read_csv(OUTPUTS / "time_split.csv")
    c = pd.read_csv(OUTPUTS / "time_split_ceiling.csv").set_index("discipline")
    piv = t.pivot(index="predictor", columns="discipline", values="spearman").reindex(t["predictor"].drop_duplicates())
    lo = t.pivot(index="predictor", columns="discipline", values="lo90").reindex(piv.index)
    hi = t.pivot(index="predictor", columns="discipline", values="hi90").reindex(piv.index)
    def cell(d, p):
        return f"{signed(piv.loc[p, d], 2)} <span class=muted>({signed(lo.loc[p, d], 2)} to {signed(hi.loc[p, d], 2)})</span>"
    rows = [{"2022&ndash;24 predictor": esc(re.sub(r"^\(\w+\) ", "", p)), "Batters": cell("bat", p), "Bowlers": cell("bowl", p)}
            for p in piv.index]
    rows.append({"2022&ndash;24 predictor": "<i>Noise ceiling (most any predictor could reach)</i>",
                 "Batters": f"{c.loc['bat', 'max_attainable_correlation']:.2f}",
                 "Bowlers": f"{c.loc['bowl', 'max_attainable_correlation']:.2f}"})
    return table(pd.DataFrame(rows), "compact", ("Batters", "Bowlers"),
                 f"Spearman correlation with 2025&ndash;26 raw pressure Impact (n = {int(t[t.discipline == 'bat'].n.max())} batters, "
                 f"{int(t[t.discipline == 'bowl'].n.max())} bowlers; 90% interval)")


def t_rr_needs() -> str:
    n = pd.read_csv(OUTPUTS / "rr_needs.csv")
    rr = n[(n["team"] == "Rajasthan Royals") & n["usable"]].copy()
    rr["Need"] = rr["rank"].map(lambda k: "<b>need</b>" if k >= 8 else "")
    rr = rr.sort_values(["discipline", "phase", "role"])
    df = pd.DataFrame({"Discipline": rr["discipline"].map({"bat": "Batting", "bowl": "Bowling"}),
                       "Cell": (rr["phase"] + " / " + rr["role"]).map(esc),
                       "RR Impact/100 pressure balls": rr["impact_per100"].map(signed),
                       "RR pressure balls": rr["balls"].map(n0), "RR rank of 10": rr["rank"].map("{:.0f}".format),
                       "": rr["Need"]})
    return table(df, "compact", ("RR Impact/100 pressure balls", "RR pressure balls", "RR rank of 10"))


def rr_lines(disc: str) -> str:
    """One row per pick (ranks 1-15): role, phase mix, IPL 2026 status and whether he fills an RR need."""
    p = PICKS[PICKS["discipline"] == disc].sort_values("rank")
    rows = []
    for _, r in p.iterrows():
        role = (f"{esc(r['batting_hand'])}, bats {r['usual_position']:.0f}" if disc == "bat" else esc(r["bowling_type"]))
        team = r["ipl_2026_team"]
        status = ("<b>already at RR</b>" if team == "Rajasthan Royals"
                  else ("no IPL 2026 team" if pd.isna(team) else esc(r["team_short"])))
        fit = f'<b>fills: {esc(r["fit_cells"])}</b>' if isinstance(r["fit_cells"], str) and r["fit_cells"] else "&ndash;"
        rows.append({"#": int(r["rank"]), "Player": esc(r["player_name"]), "Role": role,
                     "Balls by phase (PP / mid / death)": esc(r["phase_mix"]).replace("PO ", "").replace("MID ", "").replace("DE ", ""),
                     "IPL 2026": status, "RR need": fit})
    df = pd.DataFrame(rows)
    df["#"] = [f"<span class=muted>{k}</span>" if k > 10 else str(k) for k in df["#"]]
    return table(df, "compact tiny rr", ("#",))


def t_coverage() -> str:
    c = pd.read_csv(OUTPUTS / "report_coverage.csv")
    cols = {"completed": "Completed", "tie_super_over": "Tied", "no_result": "No result", "abandoned": "Abandoned",
            "total": "Total"}
    df = pd.DataFrame({"Tier": c["comp_tier"].str.replace("_", " ").map(esc),
                       **{lab: c[k].map(n0) for k, lab in cols.items()}})
    tot = {"Tier": "<b>All</b>", **{lab: f"<b>{c[k].sum():,.0f}</b>" for k, lab in cols.items()}}
    df = pd.concat([df, pd.DataFrame([tot])], ignore_index=True)
    return table(df, "compact", tuple(cols.values()))


def t_match_reliance() -> str:
    md = pd.read_csv(OUTPUTS / "top10_match_detail.csv").drop_duplicates(["discipline", "rank"])
    md = md.assign(share=md["best_match_share_of_total"])
    rows = []
    for _, r in md.iterrows():
        rows.append({"List": "Bat" if r["discipline"] == "bat" else "Bowl", "#": r["rank"], "Player": esc(r["player"]),
                     "Pressure matches": f"{r['pressure_matches']:.0f}",
                     "Pressure WPA": signed(r["total_pressure_wpa"], 2),
                     "Without best match": signed(r["total_without_best_match"], 2)})
    return table(pd.DataFrame(rows), "compact tiny", ("#", "Pressure matches", "Pressure WPA", "Without best match"))


TABLES = {
    "summary_bat": lambda w: t_summary("bat"), "summary_bowl": lambda w: t_summary("bowl"),
    "top10_bat": lambda w: t_top10("bat", w), "top10_bowl": lambda w: t_top10("bowl", w),
    "comp_bat": lambda w: t_components("bat"), "comp_bowl": lambda w: t_components("bowl"),
    "wp": lambda w: t_wp(), "pressure_profile": lambda w: t_pressure_profile(), "abswp": lambda w: t_abswp(),
    "metrics": lambda w: t_metrics(), "components_def": lambda w: t_components_def(),
    "effective": lambda w: t_effective(), "eb": lambda w: t_eb(), "eligibility": lambda w: t_eligibility(),
    "funnel": lambda w: t_funnel(), "tiers": lambda w: t_tiers(), "recency": lambda w: t_recency(),
    "sensitivity": lambda w: t_sensitivity(), "timesplit": lambda w: t_timesplit(),
    "rr_needs": lambda w: t_rr_needs(), "rr_bat": lambda w: rr_lines("bat"), "rr_bowl": lambda w: rr_lines("bowl"),
    "coverage": lambda w: t_coverage(), "reliance": lambda w: t_match_reliance(),
    "ctx_bat": lambda w: t_context("bat", "most_used"), "ctx_bowl": lambda w: t_context("bowl", "most_used"),
    "rr_own_bat": lambda w: t_context("bat", "rr"), "rr_own_bowl": lambda w: t_context("bowl", "rr"),
}


# ---------------------------------------------------------------- build

def figure(key: str) -> str:
    path = next(FIGS.glob(f"{key}_*.png"))
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img src="data:image/png;base64,{data}" alt="{key.upper()}">'


def resolve(text: str, why: dict | None, missing: list) -> str:
    def sub(m):
        key, spec = m.group(1), m.group(2)
        if key in KEEP:
            return m.group(0)
        if key.startswith("table:"):
            return TABLES[key[6:]](why)
        if key.startswith("fig:"):
            return figure(key[4:])
        if key not in VALUES or pd.isna(VALUES[key]):
            missing.append(key)
            return m.group(0)
        return fmt(VALUES[key], spec)
    return TOKEN.sub(sub, text)


def main() -> None:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    missing: list = []
    block = re.search(r'<script type="text/x-why">(.*?)</script>', tpl, re.S)
    why = {}
    for line in block.group(1).strip().splitlines():
        disc, name, text = line.strip().split("|", 2)
        why[(disc, name)] = resolve(text, None, missing)
    tpl = tpl.replace(block.group(0), "")
    top = {(d, n) for d, n in zip(PICKS["discipline"], PICKS["player_name"])
           if PICKS.loc[(PICKS["discipline"] == d) & (PICKS["player_name"] == n), "rank"].iloc[0] <= 10}
    no_line, stale = top - set(why), set(why) - top
    body = resolve(tpl, why, missing) if not no_line else ""
    problems = []
    if no_line:
        problems.append(f"top-10 picks without a 'why' line: {sorted(no_line)}")
    if stale:
        problems.append(f"'why' lines for players not in the top 10: {sorted(stale)}")
    if missing:
        problems.append(f"unresolved tokens: {sorted(set(missing))}")
    leftover = [t for t in TOKEN.findall(body) if t[0] not in KEEP]
    if leftover:
        problems.append(f"tokens left in output: {leftover[:10]}")
    if problems:
        print("BUILD FAILED\n  " + "\n  ".join(problems))
        sys.exit(1)
    OUT.write_text(body, encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB), {len(TOKEN.findall(tpl))} tokens resolved, "
          f"{len(why)} 'why' lines.")


if __name__ == "__main__":
    main()
