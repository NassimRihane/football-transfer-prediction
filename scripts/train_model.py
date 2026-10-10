# scripts/train_model.py
"""Train market value regressors on data/processed/model_dataset.csv (see build_dataset.py)
and compare them on a held-out season. Plots are saved in reports/.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import PROCESSED_DIR, ROOT

REPORTS_DIR = ROOT / "reports"
TARGET = "log_value_after"

# Train on the past, test on the most recent season: a random split would let the model
# see a player's 2022 season while predicting his 2021 one
TEST_SEASON = 2023

NUMERIC = [
    "age", "height_in_cm", "minutes", "starts",
    "goals_p90", "np_xg_p90", "assists_p90", "xa_p90", "shots_p90", "key_passes_p90",
    "xg_chain_p90", "xg_buildup_p90", "crosses_p90", "interceptions_p90",
    "tackles_won_p90", "fouled_p90", "saves_p90", "goals_against_p90",
    "clean_sheets_p90", "team_plus_minus_p90",
]
CATEGORICAL = ["position", "competition_id", "foot"]

# The value before the season is by far the strongest feature: a model with it mostly
# learns "value changes", one without it learns "what a season like this is worth".
# Try both.
USE_VALUE_BEFORE = True

POSITIONS = ["Attack", "Midfield", "Defender", "Goalkeeper"]


def make_pipeline(model, numeric, categorical):
    preprocess = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("scale", StandardScaler())]), numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
    ])
    return Pipeline([("preprocess", preprocess), ("model", model)])


def evaluate(name, y_true_log, y_pred_log):
    """R² on the log (what the model optimises) and MAE in euros (what we read)."""
    mae = mean_absolute_error(np.expm1(y_true_log), np.expm1(y_pred_log))
    r2 = r2_score(y_true_log, y_pred_log)
    print(f"{name:<32} R² (log) = {r2:.3f}   MAE = €{mae / 1e6:.2f}m")
    return {"model": name, "r2_log": r2, "mae_eur": mae}


def plot_predictions(y_true_log, y_pred_log, title, path):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(np.expm1(y_true_log), np.expm1(y_pred_log), s=8, alpha=0.4)
    lims = [1e5, 3e8]
    ax.plot(lims, lims, color="grey", linestyle="--", linewidth=1)
    ax.set(xscale="log", yscale="log", xlim=lims, ylim=lims, title=title,
           xlabel="Actual value (€)", ylabel="Predicted value (€)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_importance(pipeline, X, y, title, path):
    """Permutation importance: how much the score drops when a feature is shuffled."""
    result = permutation_importance(pipeline, X, y, n_repeats=5, random_state=0)
    imp = pd.Series(result.importances_mean, index=X.columns).sort_values().tail(15)
    fig, ax = plt.subplots(figsize=(6, 5))
    imp.plot.barh(ax=ax)
    ax.set(title=title, xlabel="Drop in R² when shuffled")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    df = pd.read_csv(PROCESSED_DIR / "model_dataset.csv")
    df = df[df["position"].isin(POSITIONS)]

    numeric = NUMERIC + (["log_value_before"] if USE_VALUE_BEFORE else [])
    features = numeric + CATEGORICAL
    train, test = df[df["season"] < TEST_SEASON], df[df["season"] == TEST_SEASON]
    print(f"Train: {len(train)} rows, test: {len(test)} rows (season {TEST_SEASON})\n")

    results = []

    # 1. Baseline: "the value doesn't change". Any model must beat this
    has_before = test["log_value_before"].notna()
    results.append(evaluate("Baseline (value before)", test.loc[has_before, TARGET],
                            test.loc[has_before, "log_value_before"]))

    # 2. One model for every player, position as a feature
    models = {
        "Ridge": Ridge(alpha=1.0),
        "Random forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=5,
                                               n_jobs=-1, random_state=0),
        # TODO: try HistGradientBoostingRegressor, tune with GridSearchCV + TimeSeriesSplit
    }
    for name, model in models.items():
        pipe = make_pipeline(model, numeric, CATEGORICAL)
        pipe.fit(train[features], train[TARGET])
        pred = pipe.predict(test[features])
        results.append(evaluate(f"{name} (global)", test[TARGET], pred))
        plot_predictions(test[TARGET], pred, f"{name}, season {TEST_SEASON}",
                         REPORTS_DIR / f"pred_{name.lower().replace(' ', '_')}.png")

    # 3. One model per position: each learns its own weights (the "profiles")
    categorical = [c for c in CATEGORICAL if c != "position"]
    pred = pd.Series(index=test.index, dtype=float)
    for position in POSITIONS:
        tr, te = train[train["position"] == position], test[test["position"] == position]
        pipe = make_pipeline(RandomForestRegressor(n_estimators=300, min_samples_leaf=5,
                                                   n_jobs=-1, random_state=0),
                             numeric, categorical)
        pipe.fit(tr[numeric + categorical], tr[TARGET])
        pred[te.index] = pipe.predict(te[numeric + categorical])
        evaluate(f"  {position}", te[TARGET], pred[te.index])
        plot_importance(pipe, te[numeric + categorical], te[TARGET],
                        f"What drives the value: {position}",
                        REPORTS_DIR / f"importance_{position.lower()}.png")
    results.append(evaluate("Random forest (per position)", test[TARGET], pred))

    print()
    print(pd.DataFrame(results).to_string(index=False))
    # TODO: look at the biggest errors (who is over/undervalued, and why?)
    # TODO: once happy, retrain on 2019-2023 and check against 2024/25 and 2025/26 values


if __name__ == "__main__":
    main()
