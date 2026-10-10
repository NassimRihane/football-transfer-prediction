# scripts/plot_players.py
"""Predict every player-season with a model that has not seen that season, then:
- save all predictions, worst errors first, to reports/predictions.csv
- plot actual vs predicted value over the seasons for a few players.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from config import PROCESSED_DIR
from train_model import CATEGORICAL, NUMERIC, POSITIONS, REPORTS_DIR, TARGET, make_pipeline

PLAYERS = ["Ferran Torres", "Frenkie de Jong", "Jules Koundé", "Thibaut Courtois"]
FEATURES_NUMERIC = NUMERIC + ["log_value_before"]


def predict_leave_one_season_out(df):
    """For each season, train on all the other seasons and predict this one.

    Unlike train_model.py, the model may learn from seasons *after* the one it predicts:
    fine to look at players, too optimistic to measure the real accuracy.
    """
    pred = pd.Series(index=df.index, dtype=float)
    for season in sorted(df["season"].unique()):
        train, test = df[df["season"] != season], df[df["season"] == season]
        pipe = make_pipeline(RandomForestRegressor(n_estimators=300, min_samples_leaf=5,
                                                   n_jobs=-1, random_state=0),
                             FEATURES_NUMERIC, CATEGORICAL)
        pipe.fit(train[FEATURES_NUMERIC + CATEGORICAL], train[TARGET])
        pred[test.index] = pipe.predict(test[FEATURES_NUMERIC + CATEGORICAL])
    return np.expm1(pred)


def plot_player(ax, rows):
    rows = rows.sort_values("season")
    labels = [f"{s}/{str(s + 1)[2:]}" for s in rows["season"]]
    ax.plot(labels, rows["value_after"] / 1e6, marker="o", label="Actual (end of season)")
    ax.plot(labels, rows["predicted"] / 1e6, marker="o", linestyle="--", label="Predicted")
    ax.plot(labels, rows["value_before"] / 1e6, color="grey", linewidth=1, alpha=0.6,
            label="Value before the season")
    for x, (_, r) in zip(labels, rows.iterrows()):
        ax.annotate(f"{int(r['minutes'])}'", (x, r["value_after"] / 1e6),
                    textcoords="offset points", xytext=(0, 8), ha="center", fontsize=7)
    ax.set(title=f"{rows['name'].iloc[0]} ({rows['position'].iloc[0]})",
           ylabel="Market value (€m)",
           ylim=(0, 1.2 * rows[["value_after", "predicted"]].max().max() / 1e6))
    ax.grid(alpha=0.3)


def main():
    df = pd.read_csv(PROCESSED_DIR / "model_dataset.csv")
    df = df[df["position"].isin(POSITIONS)]
    names = pd.read_csv(PROCESSED_DIR / "players.csv", usecols=["player_id", "name"])
    df = df.merge(names, on="player_id", how="left")

    df["predicted"] = predict_leave_one_season_out(df)
    # Ratio rather than difference: €5m off means a lot for a €2m player, little for €100m
    df["ratio"] = df["predicted"] / df["value_after"]
    df["error_eur"] = df["predicted"] - df["value_after"]

    cols = ["name", "season", "position", "age", "minutes", "goals", "assists",
            "value_before", "value_after", "predicted", "ratio", "error_eur"]
    out = df[cols].reindex(df["ratio"].map(lambda r: abs(np.log(r))).sort_values(
        ascending=False).index)
    out.to_csv(REPORTS_DIR / "predictions.csv", index=False)

    pd.set_option("display.width", 200)
    fmt = {"value_before": "{:,.0f}", "value_after": "{:,.0f}", "predicted": "{:,.0f}"}
    show = out.copy()
    for col, f in fmt.items():
        show[col] = show[col].map(lambda v: f.format(v) if pd.notna(v) else "")
    print("Model says worth MORE than Transfermarkt (biggest ratios):")
    print(show.sort_values("ratio", ascending=False).head(10).to_string(index=False))
    print("\nModel says worth LESS than Transfermarkt:")
    print(show.sort_values("ratio").head(10).to_string(index=False))

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, player in zip(axes.flat, PLAYERS):
        rows = df[df["name"] == player]
        if rows.empty:
            ax.set_title(f"{player}: not in the dataset")
            continue
        plot_player(ax, rows)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Actual vs predicted market value (minutes played above each point)")
    fig.tight_layout()
    path = REPORTS_DIR / "players.png"
    fig.savefig(path, dpi=150)
    print(f"\n-> {path}\n-> {REPORTS_DIR / 'predictions.csv'}")
    plt.show()


if __name__ == "__main__":
    main()
