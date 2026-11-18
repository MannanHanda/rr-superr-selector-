"""
lib_wp.py — the win-probability (WP) model, shared by 02_wp_model.py (fit) and 03_leverage.py (score).
Spec: docs/METHODOLOGY_SPEC.md section 1.2.

The fitted models are a plain dict (saved by 02 to data/processed/wp_models.pkl):
    erem     Poisson regression: expected remaining runs E_rem(b, w) of an average side
    erem_emp empirical mean remaining runs at b = 1, 2, 3 (replaces the Poisson curve there, D35)
    erem120  E_rem(120, 10), used to scale the curve to a match's par (f = par / erem120)
    first    logistic regression for innings 1 (projected total vs par, progress through the innings)
    chase    logistic regression for innings 2 (runs ahead of an average side)
    late_freq  outcome frequencies of chase balls with b <= 6, by runs-per-ball band (dict band -> OUTCOMES)
    bi       exact chase WP by backward induction over those outcomes, array [r, b, w] for b <= 6 (D35)

Notation: b = balls remaining, w = wickets in hand, r = runs needed, score = score before the ball.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEED = 42
DLS_NO_TARGET = [20182, 23674, 24822, 28334]
# outcome code -> (runs added, wickets lost, legal ball used); shared by the late-chase induction and 03
OUTCOMES = {"0": (0, 0, 1), "1": (1, 0, 1), "2": (2, 0, 1), "3": (3, 0, 1), "4": (4, 0, 1),
            "6": (6, 0, 1), "W": (0, 1, 1), "x": (1, 0, 0)}
LATE_B = 6          # chases with b <= LATE_B blend in the backward induction, weight (LATE_B + 1 - b) / LATE_B
EMP_EREM_B = 3      # E_rem for b <= EMP_EREM_B is the empirical mean
BI_R_MAX = 250
RPB_CUTS = (1.0, 2.0)  # late outcome frequencies by runs needed per ball: <= 1, 1-2, > 2 (D35)


def rpb_band(r, b) -> np.ndarray:
    """Band of runs needed per ball: 0 for <= 1, 1 for (1, 2], 2 for > 2."""
    return np.searchsorted(RPB_CUTS, _arr(r) / np.maximum(_arr(b), 1), side="left")


def outcome_code(b: pd.DataFrame) -> pd.Series:
    """League outcome of a ball: extra (not legal), wicket, or runs (5 -> 4, 7+ -> 6)."""
    runs = b["total_runs"].clip(0, 6).replace({5: 4}).astype(int).astype(str)
    code = np.where(b["is_legal"] != 1, "x", np.where(b["is_wicket"] == 1, "W", runs))
    return pd.Series(code, index=b.index)


def backward_induction(freq: dict) -> np.ndarray:
    """Exact chase WP V[r, b, w] for r = 0..BI_R_MAX, b = 0..LATE_B, w = 0..10 when every ball follows the
    league outcome frequencies freq[band][outcome] of its runs-per-ball band. Terminal rules as in wp():
    r <= 0 -> 1; out of balls or wickets with r == 1 (tie) -> 0.5, r > 1 -> 0. An extra adds a run and is
    bowled again (same b)."""
    V = np.zeros((BI_R_MAX + 1, LATE_B + 1, 11))
    V[0] = 1.0
    V[1, 0, :] = V[1, :, 0] = 0.5
    for b in range(1, LATE_B + 1):
        for r in range(1, BI_R_MAX + 1):
            f = freq[int(rpb_band(r, b))]
            v = f["x"] * V[r - 1, b, 1:]
            for o, (dr, dw, _) in OUTCOMES.items():
                if o == "x":
                    continue
                v = v + f[o] * V[max(r - dr, 0), b - 1, 1 - dw: 11 - dw]
            V[r, b, 1:] = v
    return V


def scored_mask(balls) -> "pd.Series":
    """Scored balls (spec 1.1): innings 1-2 of completed and tied matches, minus innings 2 of the
    4 DLS games with no revised target. Super overs and no-result/abandoned matches are excluded."""
    return (
        balls["innings"].isin([1, 2])
        & balls["status"].isin(["completed", "tie_super_over"])
        & ~(balls["match_id"].isin(DLS_NO_TARGET) & (balls["innings"] == 2))
    )


def _arr(x) -> np.ndarray:
    return np.asarray(x, dtype=float)


def erem_features(b, w) -> np.ndarray:
    b, w = _arr(b), _arr(w)
    lb = np.log(b + 1.0)
    return np.column_stack([lb, b / 120, w, w ** 2 / 10, w * lb / 10, w * b / 1200])


def erem(models: dict, b, w) -> np.ndarray:
    """Expected remaining runs; 0 when no balls or no wickets are left.

    Made non-decreasing in wickets in hand (D25): the value at w is the highest fitted value at any
    w' <= w, so more wickets in hand never means fewer expected runs.
    """
    b, w = _arr(b), _arr(w)
    bb = np.maximum(b, 0)
    grid = np.column_stack([
        models["erem"].predict(erem_features(bb, np.full_like(bb, k))) for k in range(1, 11)
    ])
    grid = np.maximum.accumulate(grid, axis=1)
    idx = np.clip(np.round(w).astype(int), 1, 10) - 1
    pred = grid[np.arange(len(bb)), idx]
    # the Poisson curve overshoots in the last balls (3.1 runs at b = 1 against 2.0 actual), so use the
    # empirical mean there (D35)
    emp = models.get("erem_emp")
    if emp is not None:
        for k, v in emp.items():
            pred = np.where(b == k, v, pred)
    return np.where((b <= 0) | (w <= 0), 0.0, pred)


def first_features(models: dict, score, b, w, max_balls, par) -> np.ndarray:
    score, b, w, max_balls, par = map(_arr, (score, b, w, max_balls, par))
    e120 = models["erem120"]
    f = par / e120
    par_adj = par * erem(models, max_balls, np.full_like(max_balls, 10.0)) / e120
    z = (score + f * erem(models, b, w) - par_adj) / 30
    prog = 1 - b / max_balls
    return np.column_stack([z, z * prog, z * prog ** 2])


def chase_features(models: dict, r, b, w, par) -> np.ndarray:
    r, b, w, par = map(_arr, (r, b, w, par))
    f = par / models["erem120"]
    m = f * erem(models, b, w) - r
    u = m / np.sqrt(b + 1.0)
    rrr = np.minimum(6 * r / np.maximum(b, 1), 36)
    return np.column_stack([u, u * np.log(b + 1.0), m / 30, w / 10, b / 120, rrr / 10])


def wp(models: dict, innings, score, b, w, r, max_balls, par) -> np.ndarray:
    """WP of the batting side in a (possibly terminal) state. Arrays of equal length.

    Innings 1: an all-out side has no balls left; the end of innings 1 is still scored by the
    first-innings model (at b = 0), so nobody is charged for a jump between models.
    Innings 2 terminal rules: r <= 0 -> 1; out of balls or wickets with r == 1 (tie) -> 0.5, r > 1 -> 0.
    Innings 2 with b <= 6: (7 - b)/6 x backward induction + the rest x logistic (D35).
    """
    innings, score, b, w, r, max_balls, par = map(_arr, (innings, score, b, w, r, max_balls, par))
    out = np.full(len(innings), np.nan)

    i1 = innings == 1
    if i1.any():
        b1 = np.where(w[i1] <= 0, 0.0, b[i1])
        X = first_features(models, score[i1], b1, w[i1], max_balls[i1], par[i1])
        out[i1] = models["first"].predict_proba(X)[:, 1]

    i2 = innings == 2
    if i2.any():
        r2, b2, w2 = r[i2], b[i2], w[i2]
        live = (r2 > 0) & (b2 > 0) & (w2 > 0)
        p = np.where(r2 <= 0, 1.0, np.where(r2 == 1, 0.5, 0.0))
        if live.any():
            X = chase_features(models, r2[live], b2[live], w2[live], par[i2][live])
            p[live] = models["chase"].predict_proba(X)[:, 1]
        # last six balls: blend in exact backward induction, all of it at b = 1 (D35)
        late = live & (b2 <= LATE_B)
        if late.any() and "bi" in models:
            rr = np.clip(r2[late], 0, BI_R_MAX).astype(int)
            bb = b2[late].astype(int)
            ww = np.clip(np.round(w2[late]), 0, 10).astype(int)
            lam = (LATE_B + 1 - bb) / LATE_B
            p[late] = lam * models["bi"][rr, bb, ww] + (1 - lam) * p[late]
        out[i2] = p
    return out
