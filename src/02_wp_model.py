"""
02_wp_model.py — Phase 2, step 1: fit and check the win-probability (WP) model.
Spec: docs/METHODOLOGY_SPEC.md sections 1.1-1.2 and 7.

Run from the repo root:
    python src/02_wp_model.py

Inputs  (data/processed/): balls.parquet
Outputs (data/processed/): wp_models.pkl   final models, refit on all training matches (dict, see lib_wp.py)
                           par.parquet     par first-innings score per match (leave-one-out, tier x year)
        (outputs/):        wp_model_eval.md, figures/f1_wp_calibration.png

Method in short:
  A. Expected remaining runs E_rem(b, w): Poisson regression on full-length first innings.
  B. Par = mean first-innings total in the same tier x year, leaving the match itself out.
  C. Innings 1: logistic regression on how far the projected total is above par, by progress.
  D. Innings 2: logistic regression on runs ahead of an average side, scaled by balls left.
Brier comes from an 80/20 split by match; calibration from 5-fold CV grouped by match (D26).
E_rem never falls as wickets in hand rise (D25, in lib_wp.erem). The saved models are refit on all
training matches.
Exits with code 1 if any acceptance check fails.
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib_wp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
FIGS = OUTPUTS / "figures"

PAR_MIN_MATCHES = 10
CV_FOLDS = 5
INK, INK2, BLUE, GRID = "#0b0b0b", "#52514e", "#2a78d6", "#e4e3df"

COLS = [
    "match_id", "innings", "comp_tier", "year", "status", "is_dls", "use_for_model", "max_balls",
    "balls_remaining", "wickets_before", "score_before", "runs_needed", "total_runs", "batting_team_won",
]


# ---------------------------------------------------------------- data

def load() -> pd.DataFrame:
    b = pd.read_parquet(PROC / "balls.parquet", columns=COLS)
    b["w"] = 10 - b["wickets_before"]
    b["scored"] = (
        b["innings"].isin([1, 2])
        & b["status"].isin(["completed", "tie_super_over"])
        & ~(b["match_id"].isin(lib_wp.DLS_NO_TARGET) & (b["innings"] == 2))
    )
    b["train"] = (
        b["scored"]
        & b["use_for_model"].astype(bool)
        & (b["status"] == "completed")
        & (b["is_dls"] != 1)
        & (b["comp_tier"] != "T20I_associate")
    )
    return b


def make_par(b: pd.DataFrame) -> pd.DataFrame:
    """Par per match: leave-one-out mean first-innings total of full-length completed matches
    in the same tier x year; cells with fewer than PAR_MIN_MATCHES matches use the tier mean."""
    i1 = b[b["innings"] == 1]
    m = i1.groupby("match_id").agg(
        comp_tier=("comp_tier", "first"), year=("year", "first"), status=("status", "first"),
        max_balls=("max_balls", "first"), inn1_total=("total_runs", "sum"),
    )
    # matches with ball data but no first-innings rows still need a par
    rest = b[~b["match_id"].isin(m.index)].groupby("match_id")[["comp_tier", "year"]].first()
    m = pd.concat([m, rest]).reset_index()
    m["in_par_set"] = (m["status"] == "completed") & (m["max_balls"] == 120)

    s = m[m["in_par_set"]]
    cell = s.groupby(["comp_tier", "year"])["inn1_total"].agg(["sum", "count"]).add_prefix("cell_")
    tier = s.groupby("comp_tier")["inn1_total"].agg(["sum", "count"]).add_prefix("tier_")
    m = m.join(cell, on=["comp_tier", "year"]).join(tier, on="comp_tier")
    own = np.where(m["in_par_set"], m["inn1_total"], 0.0)
    k = m["in_par_set"].astype(int)
    use_cell = m["cell_count"].fillna(0) >= PAR_MIN_MATCHES
    m["par"] = np.where(
        use_cell,
        (m["cell_sum"] - own) / (m["cell_count"] - k),
        (m["tier_sum"] - own) / (m["tier_count"] - k),
    )
    m["par_source"] = np.where(use_cell, "tier_year", "tier")
    return m[["match_id", "comp_tier", "year", "inn1_total", "in_par_set", "par", "par_source"]]


# ---------------------------------------------------------------- fit

def fit(rows: pd.DataFrame) -> dict:
    """Fit steps A, C and D on the given training rows (par already attached)."""
    models: dict = {}
    i1 = rows[rows["innings"] == 1]
    full = i1[i1["max_balls"] == 120]
    remaining = full.groupby("match_id")["total_runs"].transform("sum") - full["score_before"]
    models["erem"] = PoissonRegressor(alpha=0, max_iter=3000).fit(
        lib_wp.erem_features(full["balls_remaining"], full["w"]), remaining
    )
    models["erem120"] = float(lib_wp.erem(models, [120], [10])[0])

    Xc = lib_wp.first_features(models, i1["score_before"], i1["balls_remaining"], i1["w"],
                               i1["max_balls"], i1["par"])
    models["first"] = LogisticRegression(C=10, max_iter=3000).fit(Xc, i1["batting_team_won"].astype(int))

    i2 = rows[rows["innings"] == 2]
    Xd = lib_wp.chase_features(models, i2["runs_needed"], i2["balls_remaining"], i2["w"], i2["par"])
    models["chase"] = LogisticRegression(C=10, max_iter=3000).fit(Xd, i2["batting_team_won"].astype(int))
    return models


def predict(models: dict, rows: pd.DataFrame) -> np.ndarray:
    return lib_wp.wp(models, rows["innings"], rows["score_before"], rows["balls_remaining"], rows["w"],
                     rows["runs_needed"].fillna(0), rows["max_balls"], rows["par"])


# ---------------------------------------------------------------- evaluate

def calibration(p: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    bins = pd.cut(p, np.linspace(0, 1, 11), include_lowest=True)
    t = pd.DataFrame({"p": p, "y": y, "bin": bins}).groupby("bin", observed=True).agg(
        n=("p", "size"), predicted=("p", "mean"), actual=("y", "mean"))
    t["gap"] = (t["predicted"] - t["actual"]).abs()
    return t


def ece(cal: pd.DataFrame) -> float:
    return float((cal["gap"] * cal["n"]).sum() / cal["n"].sum())


def lgbm_benchmark(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """CUTTABLE: LightGBM with monotonic constraints on raw state features."""
    import lightgbm as lgb

    spec = {
        1: (["score_before", "balls_remaining", "w", "par", "max_balls"], [1, 1, 1, -1, 0]),
        2: (["runs_needed", "balls_remaining", "w", "par"], [-1, 1, 1, 0]),
    }
    out = {}
    for inn, (feats, mono) in spec.items():
        tr, te = train[train["innings"] == inn], test[test["innings"] == inn]
        mdl = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=200,
                                 monotone_constraints=mono, random_state=lib_wp.SEED, verbose=-1)
        mdl.fit(tr[feats], tr["batting_team_won"].astype(int))
        out[inn] = brier_score_loss(te["batting_team_won"].astype(int), mdl.predict_proba(te[feats])[:, 1])
    return out


def sanity_grid(models: dict, par: float) -> dict:
    b, w, r = np.meshgrid(np.arange(1, 121), np.arange(1, 11), np.arange(1, 201), indexing="ij")
    p = lib_wp.wp(models, np.full(b.size, 2), np.zeros(b.size), b.ravel(), w.ravel(), r.ravel(),
                  np.full(b.size, 120), np.full(b.size, par)).reshape(b.shape)
    tol = 1e-9

    def point(r_, b_, w_):
        return float(lib_wp.wp(models, [2], [0], [b_], [w_], [r_], [120], [par])[0])

    return {
        "mono_r": float((np.diff(p, axis=2) <= tol).mean()),
        "mono_w": float((np.diff(p, axis=1) >= -tol).mean()),
        "6_off_6": point(6, 6, 5), "30_off_6": point(30, 6, 5), "1_off_6": point(1, 6, 5),
    }


# ---------------------------------------------------------------- outputs

def plot_calibration(cals: dict) -> Path:
    FIGS.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3.8), sharey=True)
    titles = {1: "First innings", 2: "Chase"}
    for ax, inn in zip(axes, (1, 2)):
        c = cals[inn]
        ax.plot([0, 1], [0, 1], ls="--", lw=1, color=INK2, label="Perfect calibration")
        ax.plot(c["predicted"], c["actual"], color=BLUE, lw=2, marker="o", ms=6,
                markeredgecolor="white", markeredgewidth=1.5, label="Model (out-of-fold matches)")
        ax.set_title(f"{titles[inn]}  ·  calibration error {ece(c):.3f}", fontsize=10, color=INK, loc="left")
        ax.set_xlabel("Predicted win probability", fontsize=9, color=INK2)
        ax.set_xlim(0, 1), ax.set_ylim(0, 1)
        ax.grid(color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=8, colors=INK2)
    axes[0].set_ylabel("Actual win rate of batting side", fontsize=9, color=INK2)
    axes[0].legend(fontsize=8, frameon=False, loc="upper left")
    fig.suptitle("The win-probability model is well calibrated on matches it never saw",
                 fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    path = FIGS / "f1_wp_calibration.png"
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


def md_table(df: pd.DataFrame, floatfmt: str = ".3f") -> str:
    return df.to_markdown(floatfmt=floatfmt)


def main() -> None:
    b = load()
    par = make_par(b)
    b = b.merge(par[["match_id", "par"]], on="match_id", how="left")
    PROC.mkdir(parents=True, exist_ok=True)
    par.to_parquet(PROC / "par.parquet", index=False)

    tr_rows = b[b["train"]].reset_index(drop=True)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=lib_wp.SEED)
    tr_idx, te_idx = next(gss.split(tr_rows, groups=tr_rows["match_id"]))
    train, test = tr_rows.iloc[tr_idx], tr_rows.iloc[te_idx]

    # --- held-out evaluation: Brier on the 20% split; calibration on 5-fold CV by match (D26),
    # because one 152-match test set is too noisy for the calibration bars
    m_split = fit(train)
    test = test.assign(wp=predict(m_split, test))
    oof = np.full(len(tr_rows), np.nan)
    for a, t in GroupKFold(n_splits=CV_FOLDS).split(tr_rows, groups=tr_rows["match_id"]):
        oof[t] = predict(fit(tr_rows.iloc[a]), tr_rows.iloc[t])
    tr_rows["wp_oof"] = oof

    briers, cals, metrics = {}, {}, []
    for inn in (1, 2):
        t = test[test["innings"] == inn]
        y = t["batting_team_won"].astype(int).to_numpy()
        briers[inn] = brier_score_loss(y, t["wp"])
        cv = tr_rows[tr_rows["innings"] == inn]
        y_cv = cv["batting_team_won"].astype(int).to_numpy()
        cals[inn] = calibration(cv["wp_oof"].to_numpy(), y_cv)
        metrics.append({
            "innings": inn, "test balls": len(t), "test matches": t["match_id"].nunique(),
            "Brier": briers[inn], "Brier (coin flip)": brier_score_loss(y, np.full(len(y), y.mean())),
            "log loss": log_loss(y, np.clip(t["wp"], 1e-6, 1 - 1e-6)), "AUC": roc_auc_score(y, t["wp"]),
            "CV Brier": brier_score_loss(y_cv, cv["wp_oof"]),
            "CV ECE (10 bins)": ece(cals[inn]),
            "CV max gap, bins >= 500 balls": cals[inn].loc[cals[inn]["n"] >= 500, "gap"].max(),
        })
    late = tr_rows[(tr_rows["innings"] == 2) & (tr_rows["balls_remaining"] <= 12)]
    cal_late = calibration(late["wp_oof"].to_numpy(), late["batting_team_won"].astype(int).to_numpy())
    metrics_df = pd.DataFrame(metrics).set_index("innings")

    try:
        lgbm = lgbm_benchmark(train, test)
    except Exception as e:  # CUTTABLE benchmark must never block the pipeline
        print(f"LightGBM benchmark skipped: {e}")
        lgbm = None

    # --- final models on all training matches
    models = fit(tr_rows)
    ref = par[(par["comp_tier"] == "IPL") & (par["year"] == 2026) & par["in_par_set"]]
    ref_par = float(ref["inn1_total"].mean())
    sanity = sanity_grid(models, ref_par)
    start_wp = float(lib_wp.wp(models, [1], [0], [120], [10], [0], [120], [ref_par])[0])
    with open(PROC / "wp_models.pkl", "wb") as fh:
        pickle.dump(models, fh)

    # --- acceptance checks
    bad_train = tr_rows[(tr_rows["status"] != "completed") | (tr_rows["is_dls"] == 1)
                        | (tr_rows["comp_tier"] == "T20I_associate") | (~tr_rows["innings"].isin([1, 2]))]
    shared = set(train["match_id"]) & set(test["match_id"])
    max_gap = max(cals[i].loc[cals[i]["n"] >= 500, "gap"].max() for i in (1, 2))
    checks = [
        ("Test Brier innings 1 <= 0.225", f"{briers[1]:.4f}", briers[1] <= 0.225),
        ("Test Brier innings 2 <= 0.135", f"{briers[2]:.4f}", briers[2] <= 0.135),
        ("CV ECE innings 1 <= 0.03", f"{ece(cals[1]):.4f}", ece(cals[1]) <= 0.03),
        ("CV ECE innings 2 <= 0.03", f"{ece(cals[2]):.4f}", ece(cals[2]) <= 0.03),
        ("CV: no bin with >= 500 balls off by > 0.07", f"{max_gap:.4f}", max_gap <= 0.07),
        ("CV ECE chase balls with b <= 12 <= 0.05", f"{ece(cal_late):.4f}", ece(cal_late) <= 0.05),
        ("WP falls as r rises (>= 99% of grid)", f"{sanity['mono_r']:.4f}", sanity["mono_r"] >= 0.99),
        ("WP rises with w (>= 99% of grid)", f"{sanity['mono_w']:.4f}", sanity["mono_w"] >= 0.99),
        ("6 off 6, 5 wkts in hand > 0.80", f"{sanity['6_off_6']:.3f}", sanity["6_off_6"] > 0.80),
        ("30 off 6, 5 wkts in hand < 0.03", f"{sanity['30_off_6']:.4f}", sanity["30_off_6"] < 0.03),
        ("1 off 6, 5 wkts in hand > 0.95", f"{sanity['1_off_6']:.4f}", sanity["1_off_6"] > 0.95),
        ("Training rows: no tie/DLS/associate/super over", f"{len(bad_train)} bad rows", len(bad_train) == 0),
        ("Train and test share no match_id", f"{len(shared)} shared", len(shared) == 0),
    ]
    if lgbm is not None:
        for inn in (1, 2):
            checks.append((f"LightGBM benchmark inn {inn}: logistic within 0.01 (CUTTABLE)",
                           f"LGBM {lgbm[inn]:.4f}", briers[inn] <= lgbm[inn] + 0.01))
    check_df = pd.DataFrame(checks, columns=["check", "value", "pass"])

    # --- report
    erem_pts = [(120, 10), (60, 8), (30, 5), (12, 7), (6, 2)]
    erem_df = pd.DataFrame({"balls left": [p[0] for p in erem_pts], "wickets in hand": [p[1] for p in erem_pts],
                            "E_rem": lib_wp.erem(models, *zip(*erem_pts))})
    par_tab = (par[par["in_par_set"]].pivot_table(index="comp_tier", columns="year", values="inn1_total",
                                                  aggfunc="mean").round(0))
    coef = pd.DataFrame({
        "model": ["first"] * 4 + ["chase"] * 7,
        "term": ["intercept", "z", "z*prog", "z*prog^2", "intercept", "u", "u*ln(b+1)", "m/30", "w/10", "b/120",
                 "min(6r/b,36)/10"],
        "coef": np.r_[models["first"].intercept_, models["first"].coef_[0],
                      models["chase"].intercept_, models["chase"].coef_[0]],
    })
    n_tr = tr_rows.groupby("innings").agg(balls=("match_id", "size"), matches=("match_id", "nunique"))
    tr_split = pd.Series({"train matches": train["match_id"].nunique(), "test matches": test["match_id"].nunique()})

    lines = [
        "# Win-probability model evaluation (generated by src/02_wp_model.py)", "",
        "Spec: docs/METHODOLOGY_SPEC.md section 1.2. Brier, log loss, AUC and the LightGBM benchmark are on "
        "held-out matches (20%, split by match, seed 42). Calibration (ECE, bin gaps) is on out-of-fold "
        f"predictions from {CV_FOLDS}-fold cross-validation grouped by match, so every training match is "
        "scored once by a model that never saw it (D26). The saved models are refit on all training matches.", "",
        "## Acceptance checks", "", check_df.to_markdown(index=False), "",
        "## Held-out metrics", "", md_table(metrics_df, ".4f"), "",
        f"Chase balls with 12 or fewer balls left (CV): {len(late):,} balls, ECE {ece(cal_late):.4f}.", "",
        "## Calibration bins (5-fold CV, out of fold)", "",
        "### Innings 1", "", md_table(cals[1]), "", "### Innings 2", "", md_table(cals[2]), "",
        "### Innings 2, balls left <= 12", "", md_table(cal_late), "",
        "## Training data", "", md_table(n_tr, ".0f"), "", tr_split.to_frame("n").to_markdown(), "",
        "## Expected remaining runs (final model)", "", erem_df.to_markdown(index=False, floatfmt=".1f"), "",
        "## Mean first-innings total by tier and year (full-length completed matches; basis of par)", "",
        md_table(par_tab, ".0f"), "",
        f"Par source counts: {par['par_source'].value_counts().to_dict()}", "",
        "## Coefficients (final model)", "", coef.to_markdown(index=False, floatfmt=".4f"), "",
        "## Sanity checks (final model, chase, IPL 2026 par "
        f"{ref_par:.1f})", "",
        pd.Series(sanity).to_frame("value").to_markdown(floatfmt=".4f"), "",
        f"WP of the batting side at the first ball of an IPL 2026 match: {start_wp:.3f}.",
    ]
    if lgbm is not None:
        lines += ["", f"LightGBM benchmark test Brier: innings 1 {lgbm[1]:.4f}, innings 2 {lgbm[2]:.4f}."]
    (OUTPUTS / "wp_model_eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    fig_path = plot_calibration(cals)

    # --- console summary
    print(f"Training rows: {len(tr_rows):,} balls, {tr_rows['match_id'].nunique()} matches "
          f"(train {tr_split['train matches']}, test {tr_split['test matches']})")
    print(f"E_rem(120,10) = {models['erem120']:.1f}; IPL 2026 par {ref_par:.1f}; WP at first ball {start_wp:.3f}")
    print()
    print(check_df.assign(**{"pass": check_df["pass"].map({True: "PASS", False: "FAIL"})}).to_string(index=False))
    print(f"\nWrote {PROC / 'wp_models.pkl'}, {PROC / 'par.parquet'}, "
          f"{OUTPUTS / 'wp_model_eval.md'}, {fig_path}")
    if not check_df["pass"].all():
        sys.exit(1)


if __name__ == "__main__":
    main()
