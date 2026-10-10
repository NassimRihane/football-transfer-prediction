# scripts/build_dataset.py
"""Build the modelling table: one row per player and season, with the season's stats as
features and the market value published after the season as target.
Writes data/processed/model_dataset.csv.
"""
import sqlite3

import numpy as np
import pandas as pd

from config import DB_PATH, PROCESSED_DIR

# Below this, per-90 stats are too noisy to mean anything
MIN_MINUTES = 450

# A player who changed club within a season has one row per club: sum them
UNDERSTAT_QUERY = """
SELECT player_id, season,
       SUM(minutes) AS minutes, SUM(matches) AS matches,
       SUM(goals) AS goals, SUM(np_goals) AS np_goals, SUM(assists) AS assists,
       SUM(xg) AS xg, SUM(np_xg) AS np_xg, SUM(xa) AS xa,
       SUM(shots) AS shots, SUM(key_passes) AS key_passes,
       SUM(xg_chain) AS xg_chain, SUM(xg_buildup) AS xg_buildup
FROM understat_player_season
GROUP BY player_id, season
"""

FBREF_QUERY = """
SELECT player_id, season,
       SUM(playing_time_starts) AS starts,
       SUM(standard_sot) AS shots_on_target,
       SUM(performance_crs) AS crosses,
       SUM(performance_int) AS interceptions,
       SUM(performance_tklw) AS tackles_won,
       SUM(performance_fls) AS fouls,
       SUM(performance_fld) AS fouled,
       SUM(performance_saves) AS saves,
       SUM(performance_ga) AS goals_against,
       SUM(performance_cs) AS clean_sheets,
       SUM(team_success_plus_minus) AS team_plus_minus,
       MAX(competition_id) AS competition_id   -- TODO: several leagues in one season
FROM fbref_player_season
GROUP BY player_id, season
"""

PLAYERS_QUERY = """
SELECT player_id, position, sub_position, foot, height_in_cm, date_of_birth
FROM players
"""

COUNT_STATS = ["goals", "np_goals", "assists", "xg", "np_xg", "xa", "shots", "key_passes",
               "xg_chain", "xg_buildup", "shots_on_target", "crosses", "interceptions",
               "tackles_won", "fouls", "fouled", "saves", "goals_against", "clean_sheets",
               "team_plus_minus"]
KEEPER_STATS = ["saves", "goals_against", "clean_sheets"]


def attach_valuation(df, valuations, date_col, direction, name):
    """Add the valuation closest to df[date_col] (before or after it) as column `name`."""
    left = df.sort_values(date_col)
    right = valuations.rename(columns={"date": "valuation_date"}).sort_values("valuation_date")
    merged = pd.merge_asof(left, right, left_on=date_col, right_on="valuation_date",
                           by="player_id", direction=direction,
                           tolerance=pd.Timedelta(days=150))
    return merged.rename(columns={"market_value_in_eur": name}).drop(columns="valuation_date")


def main():
    conn = sqlite3.connect(DB_PATH)
    understat = pd.read_sql(UNDERSTAT_QUERY, conn)
    fbref = pd.read_sql(FBREF_QUERY, conn)
    players = pd.read_sql(PLAYERS_QUERY, conn)
    valuations = pd.read_sql("SELECT player_id, date, market_value_in_eur FROM player_valuations",
                             conn, parse_dates=["date"])
    conn.close()

    # 1. Stats: Understat as the base, FBref adds the defensive and keeper columns
    df = understat.merge(fbref, on=["player_id", "season"], how="left")
    df = df.merge(players, on="player_id", how="left")
    df = df[df["minutes"] >= MIN_MINUTES]
    # FBref only fills the keeper columns for goalkeepers
    df[KEEPER_STATS] = df[KEEPER_STATS].fillna(0)

    # 2. Per-90 stats, so that a starter and a substitute can be compared
    for col in COUNT_STATS:
        df[f"{col}_p90"] = df[col] / df["minutes"] * 90

    # 3. Age at the start of the season (2019 -> 2019-08-01). Transfermarkt publishes its
    # big update in late May / June, so the end of the season is anchored on May 15
    df["season_start"] = pd.to_datetime(df["season"].astype(str) + "-08-01")
    df["season_end"] = pd.to_datetime((df["season"] + 1).astype(str) + "-05-15")
    df["age"] = (df["season_start"] - pd.to_datetime(df["date_of_birth"])).dt.days / 365.25

    # 4. Values: last one before the season (feature) and first one after it (target)
    df = attach_valuation(df, valuations, "season_start", "backward", "value_before")
    df = attach_valuation(df, valuations, "season_end", "forward", "value_after")
    df = df.dropna(subset=["value_after"])

    # Values span 3 orders of magnitude (100k to 200M): models work on the log
    df["log_value_before"] = np.log1p(df["value_before"])
    df["log_value_after"] = np.log1p(df["value_after"])

    # TODO: more features worth trying
    #   - club strength (league position, club total value), from games / clubs
    #   - previous season's stats (lag features), trend of the value
    #   - international caps

    out = PROCESSED_DIR / "model_dataset.csv"
    df.to_csv(out, index=False)
    print(f"{len(df)} player-seasons -> {out}")
    print(df.groupby("season").size().to_string())
    print(df["position"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
