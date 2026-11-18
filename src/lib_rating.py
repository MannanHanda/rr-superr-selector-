"""
lib_rating.py — shared rating logic for 05 (player metrics), 06 (ratings) and 07 (reliability checks).
Spec: docs/METHODOLOGY_SPEC.md sections 2.1, 2.4, 2.5, 3.1-3.4.

Everything a sensitivity variant can change is a field of Params, so 06 and 07 run exactly the same code.

Pipeline:
    d   = load_balls()                       ball values (03) joined to ball facts
    pms, offsets, cells = build_pms(d, params)   credited, tier-offset and situation-centred (D36), weighted
                                             sufficient statistics per discipline x player x match x flag
                                             (pressure / routine / dead); cells = the centring means
    e, funnel = eligibility(pms, disc)       eligibility counts on non-dead balls, all tiers (D38)
    table, eb = rate(pms, disc, rated_ids, eb_pool_ids, params[, eb])
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

TIER_WEIGHT = {"IPL": 1.0, "T20I_full": 0.8, "Emerging": 0.5, "T20I_associate": 0.3}
CORE_TIERS = ["IPL", "T20I_full"]
OFFSET_MIN_BALLS, OFFSET_MIN_PLAYERS = 150, 15
ELIG = {"total": 400, "pressure": 125, "pressure_matches": 10, "recent": 60}
RECENT_YEARS = (2025, 2026)
PRESSURE_MATCH_MIN_BALLS = 3
EB_POOL = {"total": 200, "pressure": 60}

OVER_GROUPS = ([0, 2, 6, 10, 15, 18, 20], ["1-2", "3-6", "7-10", "11-15", "16-18", "19-20"])
IPL_SHORT = {"Rajasthan Royals": "RR", "Punjab Kings": "PBKS", "Sunrisers Hyderabad": "SRH",
             "Royal Challengers Bengaluru": "RCB", "Lucknow Super Giants": "LSG", "Kolkata Knight Riders": "KKR",
             "Mumbai Indians": "MI", "Gujarat Titans": "GT", "Chennai Super Kings": "CSK", "Delhi Capitals": "DC"}

BALL_COLS = ["match_id", "innings", "innings_ball_num", "overid", "phase", "comp_tier", "year", "striker_id", "bowler_id",
             "is_ball_faced", "is_legal", "striker_out", "is_bowler_wicket", "batter_runs", "bowler_runs",
             "is_dot_faced", "is_four", "is_six"]


@dataclass(frozen=True)
class Params:
    pressure_q: float = 0.75            # pressure = LI >= this quantile of its own innings
    global_share: float | None = None   # if set (V3): pressure = top share of LI over all balls
    weights: tuple = (0.60, 0.15, 0.25)  # level, shift, consistency
    half_life: float | None = 2.0       # recency half-life in years; None = no decay
    anchor_year: int = 2026
    tier_weight: dict = field(default_factory=lambda: dict(TIER_WEIGHT))
    use_offsets: bool = True
    tiers: tuple | None = None          # restrict to these tiers (V9)
    years: tuple | None = None          # restrict to these years (time split)
    split_parts: bool = True            # shrink run and wicket parts separately (V11 = False)
    level: str = "impact"               # "wpa" (V12): pressure level = shrunk raw WPA per pressure ball
    k_cap: float = 5000.0
    m_range: tuple = (10.0, np.inf)      # no upper cap on consistency pseudo-matches (D37; was 60)
    z_scale: str = "raw"                # divide each shrunk component by the SD of its raw values (D37);
                                        # "shrunk" = the old SD of the shrunk values
    stake_weight: bool = True           # D45: weight pressure balls by their innings' median pressure LI
                                        # (V13 = False, equal innings weight)


def variant(**kw) -> Params:
    return replace(Params(), **kw)


# ---------------------------------------------------------------- ball level

def recency_weight(year, anchor: int = 2026, half_life: float | None = 2.0):
    year = np.asarray(year, float)
    if half_life is None:
        return np.ones_like(year)
    return 0.5 ** ((anchor - year) / half_life)


def load_balls() -> pd.DataFrame:
    v = pd.read_parquet(PROC / "ball_values.parquet")
    b = pd.read_parquet(PROC / "balls.parquet", columns=BALL_COLS)
    return v.merge(b, on=["match_id", "innings", "innings_ball_num"], how="left", validate="1:1")


def set_flags(d: pd.DataFrame, p: Params) -> pd.Series:
    """pressure / routine / dead. Cuts are computed on all scored balls before any tier or year filter."""
    if p.global_share is not None:
        pressure = d["LI"] >= d["LI"].quantile(1 - p.global_share)
    else:
        cut = d.groupby("innings")["LI"].quantile(p.pressure_q)
        pressure = d["LI"] >= d["innings"].map(cut)
    pressure &= ~d["is_dead"]
    return pd.Series(np.select([pressure, d["is_dead"]], ["pressure", "dead"], "routine"), index=d.index)


def stake_weights(d: pd.DataFrame, flag: pd.Series) -> pd.Series:
    """D45: per innings, median LI of its pressure balls divided by the larger median (chase = 1, first
    innings ~0.53). Computed on all scored balls, like the cut."""
    med = d.loc[flag == "pressure"].groupby("innings")["LI"].median()
    return med / med.max()


def credit(d: pd.DataFrame) -> pd.DataFrame:
    """One row per (ball, credited player): batting rows for the striker, bowling rows for the bowler (2.1)."""
    keep = ["match_id", "innings", "overid", "phase", "comp_tier", "year", "flag", "omega"]
    wpa_run, wpa_wkt = d["wp_nw"] - d["wp0"], d["wp1"] - d["wp_nw"]

    bat = d[d["is_ball_faced"] == 1]
    out_b = bat["striker_out"] == 1
    bat = bat[keep].assign(
        discipline="bat", player_id=bat["striker_id"],
        x_run=bat["x_run"], x_wkt=bat["x_wkt"].where(out_b, 0.0).where(bat["x_wkt"].notna()),
        wpa=wpa_run[bat.index] + wpa_wkt[bat.index].where(out_b, 0.0),
        n_balls=1, runs=bat["batter_runs"], dots=bat["is_dot_faced"], bnd=bat["is_four"] + bat["is_six"],
        outs=out_b.astype(int),
    )

    bowl = d
    out_w = bowl["is_bowler_wicket"] == 1
    bowl = bowl[keep].assign(
        discipline="bowl", player_id=bowl["bowler_id"],
        x_run=-bowl["x_run"], x_wkt=-(bowl["x_wkt"].where(out_w, 0.0)).where(bowl["x_wkt"].notna()),
        wpa=-(wpa_run + wpa_wkt.where(out_w, 0.0)),
        n_balls=bowl["is_legal"].astype(int), runs=bowl["bowler_runs"],
        dots=((bowl["is_legal"] == 1) & (bowl["bowler_runs"] == 0)).astype(int),
        bnd=bowl["is_four"] + bowl["is_six"], outs=out_w.astype(int),
    )
    c = pd.concat([bat, bowl], ignore_index=True)
    c["player_id"] = c["player_id"].astype("int64")
    return c


def tier_offsets(c: pd.DataFrame, tier_weight: dict) -> pd.DataFrame:
    """Mean (tier - IPL) Impact per ball of players with >= 150 balls in both, weighted by the smaller
    count; run and wicket parts separately (D30a). Zero if fewer than 15 players qualify."""
    live = c[c["flag"] != "dead"]
    per = live.groupby(["discipline", "player_id", "comp_tier"]).agg(
        n=("x_run", "size"), x_run=("x_run", "mean"), x_wkt=("x_wkt", "mean"))
    rows = []
    tiers_present = set(per.index.get_level_values("comp_tier"))
    for disc in ("bat", "bowl"):
        p = per.xs(disc, level="discipline")
        ipl = p.xs("IPL", level="comp_tier") if "IPL" in tiers_present else p.iloc[:0]
        for tier in tier_weight:
            if tier == "IPL":
                continue
            t = p.xs(tier, level="comp_tier") if tier in tiers_present else p.iloc[:0]
            j = t.add_suffix("_t").join(ipl.add_suffix("_i"), how="inner")
            j = j[(j["n_t"] >= OFFSET_MIN_BALLS) & (j["n_i"] >= OFFSET_MIN_BALLS)]
            wt = np.minimum(j["n_t"], j["n_i"])
            n_players = len(j)
            used = n_players >= OFFSET_MIN_PLAYERS
            for part in ("x_run", "x_wkt"):
                raw = float(np.average(j[f"{part}_t"] - j[f"{part}_i"], weights=wt)) if n_players else np.nan
                rows.append({"discipline": disc, "tier": tier, "part": part, "n_players": n_players,
                             "raw_offset_per_ball": raw, "applied_offset_per_ball": raw if used else 0.0,
                             "used": used})
    return pd.DataFrame(rows)


def aggregate(c: pd.DataFrame) -> pd.DataFrame:
    """Sufficient statistics per discipline x player x match x flag."""
    c = c.assign(x_run=c["x_run"].fillna(0.0), x_wkt=c["x_wkt"].fillna(0.0), w2=c["omega"] ** 2)
    c = c.assign(x_tot=c["x_run"] + c["x_wkt"])
    for col in ("x_run", "x_wkt", "x_tot", "rae", "wpa", "xc"):
        c[f"w_{col}"] = c["omega"] * c[col]
    for col in ("x_run", "x_wkt", "x_tot", "wpa"):
        c[f"w_{col}2"] = c["omega"] * c[col] ** 2
    keys = ["discipline", "player_id", "match_id", "innings", "comp_tier", "year", "flag"]
    agg = {"rows": ("omega", "size"), "n_balls": ("n_balls", "sum"), "w": ("omega", "sum"), "w2": ("w2", "sum"),
           "omega": ("omega", "first"), "wpa": ("wpa", "sum"), "runs": ("runs", "sum"), "dots": ("dots", "sum"),
           "bnd": ("bnd", "sum"), "outs": ("outs", "sum")}
    for col in ("w_x_run", "w_x_wkt", "w_x_tot", "w_rae", "w_wpa", "w_xc", "w_x_run2", "w_x_wkt2", "w_x_tot2",
                "w_wpa2"):
        agg[col] = (col, "sum")
    return c.groupby(keys, observed=True).agg(**agg).reset_index()


def centre_impact(c: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Subtract the league mean credited Impact of the same discipline x innings x over group x flag, run and
    wicket parts separately (D36), so 0 = an average outcome for that exact situation and role. The removed
    cell mean of the total is kept per ball as `xc` (role-mix check in 05). Live balls only."""
    c = c.assign(over_group=pd.cut(c["overid"], OVER_GROUPS[0], labels=OVER_GROUPS[1]))
    live = c["flag"] != "dead"
    keys = ["discipline", "innings", "over_group", "flag"]
    cells = c[live].groupby(keys, observed=True).agg(n_balls=("x_run", "size"), x_run=("x_run", "mean"),
                                                     x_wkt=("x_wkt", "mean"))
    m = cells.reindex(pd.MultiIndex.from_frame(c[keys]))
    c["xc"] = np.where(live, (m["x_run"] + m["x_wkt"]).to_numpy(), np.nan)
    for part in ("x_run", "x_wkt"):
        c[part] = c[part] - np.where(live, m[part].to_numpy(), 0.0)
    cells = cells.reset_index()
    cells["x_tot"] = cells["x_run"] + cells["x_wkt"]
    return c.drop(columns="over_group"), cells


def build_pms(d: pd.DataFrame, p: Params = Params()) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    d = d.assign(flag=set_flags(d, p))
    stake = stake_weights(d, d["flag"]) if p.stake_weight else None
    if p.tiers is not None:
        d = d[d["comp_tier"].isin(p.tiers)]
    if p.years is not None:
        d = d[d["year"].isin(p.years)]
    d = d.assign(omega=d["comp_tier"].map(p.tier_weight)
                 * recency_weight(d["year"], p.anchor_year, p.half_life))
    if stake is not None:
        is_p = d["flag"] == "pressure"
        d.loc[is_p, "omega"] *= d.loc[is_p, "innings"].map(stake).to_numpy()
    c = credit(d)

    offs = tier_offsets(c, p.tier_weight)
    if p.use_offsets:
        for part in ("x_run", "x_wkt"):
            o = offs[offs["part"] == part].set_index(["discipline", "tier"])["applied_offset_per_ball"]
            key = pd.MultiIndex.from_arrays([c["discipline"], c["comp_tier"]])
            c[part] = c[part] - o.reindex(key).fillna(0.0).to_numpy()
    else:
        offs = offs.assign(applied_offset_per_ball=0.0, used=False)
    c, cells = centre_impact(c)

    # runs above expected: league mean in the same discipline x innings x phase x flag x tier (D30d)
    live = c["flag"] != "dead"
    exp = c[live].groupby(["discipline", "innings", "phase", "flag", "comp_tier"])["runs"].transform("mean")
    c["rae"] = np.nan
    c.loc[live, "rae"] = np.where(c.loc[live, "discipline"] == "bat", c.loc[live, "runs"] - exp,
                                  exp - c.loc[live, "runs"])
    return aggregate(c), offs, cells


def eligibility(pms: pd.DataFrame, disc: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Eligibility counts (3.2) on non-dead balls in all four tiers (D38; was IPL + T20I_full only), and the
    funnel. IPL pressure balls are counted alongside so readers can see where each player's evidence is from."""
    s = pms[(pms["discipline"] == disc) & (pms["flag"] != "dead")]
    pr = s[s["flag"] == "pressure"]
    pm = pr.groupby(["player_id", "match_id"])["n_balls"].sum()
    e = pd.DataFrame({
        "elig_balls": s.groupby("player_id")["n_balls"].sum(),
        "elig_pressure_balls": pr.groupby("player_id")["n_balls"].sum(),
        "elig_pressure_matches": (pm >= PRESSURE_MATCH_MIN_BALLS).groupby("player_id").sum(),
        "elig_recent_balls": s[s["year"].isin(RECENT_YEARS)].groupby("player_id")["n_balls"].sum(),
        "ipl_pressure_balls": pr[pr["comp_tier"] == "IPL"].groupby("player_id")["n_balls"].sum(),
    }).fillna(0)
    rules = [("total", e["elig_balls"] >= ELIG["total"]),
             ("pressure", e["elig_pressure_balls"] >= ELIG["pressure"]),
             ("pressure_matches", e["elig_pressure_matches"] >= ELIG["pressure_matches"]),
             ("recent", e["elig_recent_balls"] >= ELIG["recent"])]
    ok = pd.Series(True, index=e.index)
    funnel = [{"discipline": disc, "step": "any live ball (all tiers)", "players": int((e["elig_balls"] > 0).sum())}]
    for name, rule in rules:
        ok &= rule
        funnel.append({"discipline": disc, "step": f"+ {name} >= {ELIG[name]}", "players": int(ok.sum())})
    e["eligible"] = ok
    return e, pd.DataFrame(funnel)


def eb_pool(pms: pd.DataFrame, disc: str) -> pd.Index:
    """Players used to estimate priors and k (3.1): >= 200 live balls and >= 60 pressure balls, all tiers."""
    s = pms[(pms["discipline"] == disc) & (pms["flag"] != "dead")]
    tot = s.groupby("player_id")["n_balls"].sum()
    prs = s[s["flag"] == "pressure"].groupby("player_id")["n_balls"].sum().reindex(tot.index).fillna(0)
    return tot.index[(tot >= EB_POOL["total"]) & (prs >= EB_POOL["pressure"])]


# ---------------------------------------------------------------- rating

def shrink(raw, n, k, prior):
    return prior + n / (n + k) * (raw - prior)


def player_sums(pms: pd.DataFrame, disc: str) -> pd.DataFrame:
    """Per player: weighted sums for pressure (P) and routine (R) balls, wide format."""
    s = pms[(pms["discipline"] == disc) & (pms["flag"] != "dead")]
    cols = ["rows", "n_balls", "w", "w2", "w_x_run", "w_x_wkt", "w_x_tot", "w_x_run2", "w_x_wkt2", "w_x_tot2",
            "wpa", "w_wpa", "w_wpa2"]
    cols += [c for c in ("w_xc",) if c in s.columns]
    g = s.groupby(["player_id", "flag"])[cols].sum().unstack("flag")
    out = pd.DataFrame(index=g.index)
    for flag, tag in (("pressure", "P"), ("routine", "R")):
        for col in cols:
            out[f"{tag}_{col}"] = g[(col, flag)] if (col, flag) in g.columns else np.nan
    return out


def consistency_sums(pms: pd.DataFrame, disc: str) -> pd.DataFrame:
    """Per player: matches with >= 3 pressure balls, weighted share with positive credited pressure WPA."""
    s = pms[(pms["discipline"] == disc) & (pms["flag"] == "pressure")]
    m = s.groupby(["player_id", "match_id"]).agg(n=("n_balls", "sum"), wpa=("wpa", "sum"), om=("omega", "first"))
    m = m[m["n"] >= PRESSURE_MATCH_MIN_BALLS]
    m["pos"] = (m["wpa"] > 0).astype(float)
    g = m.assign(om_pos=m["om"] * m["pos"], om2=m["om"] ** 2).groupby("player_id").agg(
        c_matches=("pos", "size"), c_w=("om", "sum"), c_w2=("om2", "sum"), c_wpos=("om_pos", "sum"))
    g["c_raw"] = g["c_wpos"] / g["c_w"]
    g["c_neff"] = g["c_w"] ** 2 / g["c_w2"]
    return g


def _pooled_var(sums: pd.DataFrame, tag: str, part: str) -> tuple[float, float]:
    w = sums[f"{tag}_w"].sum()
    mean = sums[f"{tag}_w_{part}"].sum() / w
    return mean, sums[f"{tag}_w_{part}2"].sum() / w - mean ** 2


def _k(raw: pd.Series, n: pd.Series, sigma2: float, cap: float) -> tuple[float, float, bool]:
    tau2 = raw.var() - (sigma2 / n).mean()
    k = sigma2 / tau2 if tau2 > 0 else np.inf
    guard = not np.isfinite(k) or k > cap
    return (cap if guard else k), tau2, guard


def estimate_eb(sums: pd.DataFrame, cons: pd.DataFrame, pool: pd.Index, p: Params) -> dict:
    """Priors and shrinkage strengths (3.1) from the EB pool."""
    s = sums.loc[sums.index.intersection(pool)].dropna(subset=["P_w", "R_w"])
    eb = {}
    n_R = s["R_w"] ** 2 / s["R_w2"]
    n_P = s["P_w"] ** 2 / s["P_w2"]
    parts = ("x_run", "x_wkt") if p.split_parts else ("x_tot",)
    for part in parts:
        prior, sigma2 = _pooled_var(s, "R", part)
        raw = s[f"R_w_{part}"] / s["R_w"]
        k, tau2, guard = _k(raw, n_R, sigma2, p.k_cap)
        eb[f"U_{part}"] = {"prior": prior, "sigma2": sigma2, "tau2": tau2, "k": k, "guard": guard, "n_players": len(s)}

    if p.level == "wpa":
        prior, sigma2 = _pooled_var(s, "P", "wpa")
        k, tau2, guard = _k(s["P_w_wpa"] / s["P_w"], n_P, sigma2, p.k_cap)
        eb["P_wpa"] = {"prior": prior, "sigma2": sigma2, "tau2": tau2, "k": k, "guard": guard, "n_players": len(s)}

    mP, s2P = _pooled_var(s, "P", "x_tot")
    mR, s2R = _pooled_var(s, "R", "x_tot")
    d_raw = s["P_w_x_tot"] / s["P_w"] - s["R_w_x_tot"] / s["R_w"]
    tau2 = d_raw.var() - (s2P / n_P + s2R / n_R).mean()
    k = s2P / tau2 if tau2 > 0 else np.inf
    guard = not np.isfinite(k) or k > p.k_cap
    eb["D"] = {"prior": mP - mR, "sigma2": s2P, "tau2": tau2, "k": p.k_cap if guard else k, "guard": guard,
               "n_players": len(s)}

    c = cons.loc[cons.index.intersection(pool)]
    cbar = c["c_wpos"].sum() / c["c_w"].sum()
    h = (1 / c["c_neff"]).mean()
    tau2 = (c["c_raw"].var() - cbar * (1 - cbar) * h) / (1 - h)
    m = cbar * (1 - cbar) / tau2 - 1 if tau2 > 0 else np.inf
    lo, hi = p.m_range
    eb["C"] = {"prior": cbar, "sigma2": cbar * (1 - cbar), "tau2": tau2, "k": float(np.clip(m, lo, hi)),
               "guard": not (lo <= m <= hi), "n_players": len(c)}
    return eb


def rate(pms: pd.DataFrame, disc: str, rated: pd.Index, pool: pd.Index, p: Params = Params(),
         eb: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Shrunk components and the reliability rating for the rated players (2.4, 2.5, 3.1).
    Values are per ball (x100 = per 100 balls). Pass eb to hold priors and k fixed (bootstrap)."""
    sums, cons = player_sums(pms, disc), consistency_sums(pms, disc)
    if eb is None:
        eb = estimate_eb(sums, cons, pool, p)
    return rate_from_sums(sums, cons, rated, p, eb), eb


def rate_from_sums(sums: pd.DataFrame, cons: pd.DataFrame, rated: pd.Index, p: Params, eb: dict) -> pd.DataFrame:
    """The rating formula on per-player sums (also used directly by the 07 bootstrap).
    A player with no balls of a kind (possible in a resample or a variant) gets the prior for that part."""
    t = sums.reindex(rated)
    c = cons.reindex(rated)
    n_R = (t["R_w"] ** 2 / t["R_w2"]).fillna(0.0)
    n_P = (t["P_w"] ** 2 / t["P_w2"]).fillna(0.0)

    def sh(raw, n, e):
        return shrink(raw, n, e["k"], e["prior"]).fillna(e["prior"])

    out = pd.DataFrame(index=rated)
    out["n_P"], out["n_R"] = n_P, n_R
    out["P_raw"] = t["P_w_x_tot"] / t["P_w"]
    out["R_raw"] = t["R_w_x_tot"] / t["R_w"]
    out["D_raw"] = out["P_raw"] - out["R_raw"]
    if p.split_parts:
        for part, lab in (("x_run", "run"), ("x_wkt", "wkt")):
            out[f"R_{lab}_raw"] = t[f"R_w_{part}"] / t["R_w"]
            out[f"U_{lab}"] = sh(out[f"R_{lab}_raw"], n_R, eb[f"U_{part}"])
        out["U"] = out["U_run"] + out["U_wkt"]
    else:
        out["U"] = sh(out["R_raw"], n_R, eb["U_x_tot"])
    out["D_hat"] = sh(out["D_raw"], n_P, eb["D"])
    if p.level == "wpa":
        out["P_hat"] = sh(t["P_w_wpa"] / t["P_w"], n_P, eb["P_wpa"])
    else:
        out["P_hat"] = out["U"] + out["D_hat"]
    e = eb["C"]
    out["c_matches"] = c["c_matches"].fillna(0)
    out["C_raw"] = c["c_raw"]
    out["C_hat"] = (c["c_neff"] * c["c_raw"] + e["k"] * e["prior"]) / (c["c_neff"] + e["k"])
    out["C_hat"] = out["C_hat"].fillna(e["prior"])
    out["P_wpa_sum"] = t["P_wpa"]
    out["P_level_raw"] = t["P_w_wpa"] / t["P_w"] if p.level == "wpa" else out["P_raw"]

    # D37: scale by the spread of the raw values, so a component that shrinkage pulls almost flat (a noisy
    # one) also counts for little in the rating; the old way divided by the spread after shrinkage
    wl, ws, wc = p.weights
    for col, raw in (("P_hat", "P_level_raw"), ("D_hat", "D_raw"), ("C_hat", "C_raw")):
        sd = out[raw].std(ddof=0) if p.z_scale == "raw" else out[col].std(ddof=0)
        out[f"z_{col}"] = (out[col] - out[col].mean()) / sd if sd > 0 else 0.0
    out["rating_z"] = wl * out["z_P_hat"] + ws * out["z_D_hat"] + wc * out["z_C_hat"]
    out["rating"] = 50 + 10 * out["rating_z"]
    out = out.sort_values(["rating", "P_hat"], ascending=False)
    out["rank"] = np.arange(1, len(out) + 1)
    out.index.name = "player_id"
    return out
