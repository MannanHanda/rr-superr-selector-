"""
lib_wp.py — the win-probability (WP) model, shared by 02_wp_model.py (fit) and 03_leverage.py (score).
Spec: docs/METHODOLOGY_SPEC.md section 1.2.

The fitted models are a plain dict (saved by 02 to data/processed/wp_models.pkl):
    erem     Poisson regression: expected remaining runs E_rem(b, w) of an average side
    erem120  E_rem(120, 10), used to scale the curve to a match's par (f = par / erem120)
    first    logistic regression for innings 1 (projected total vs par, progress through the innings)
    chase    logistic regression for innings 2 (runs ahead of an average side)

Notation: b = balls remaining, w = wickets in hand, r = runs needed, score = score before the ball.
"""

from __future__ import annotations

import numpy as np

SEED = 42
DLS_NO_TARGET = [20182, 23674, 24822, 28334]


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
        out[i2] = p
    return out
