# scripts/fetch_fbref_stats.py
"""Fetch FBref player season stats for the Big 5 and link them to Transfermarkt ids.

FBref throttles requests (about 5 minutes per page here); soccerdata caches every page
in ~/soccerdata/data/FBref, so only the first run is slow.
"""
import sqlite3

import pandas as pd
import soccerdata as sd

from config import BIG5, DB_PATH, PROCESSED_DIR, STATS_SEASONS, tm_season
from matching import attach_tm_ids, snake_case, write_stats_table

# FBref no longer has the Opta-based tables (passing, defense, possession, gca...)
STAT_TYPES = ["standard", "shooting", "keeper", "playing_time", "misc"]
KEY_COLS = ["league", "season", "team", "player"]
LEAGUE_TO_TM = {league: code for code, league in BIG5.items()}


def flatten_columns(df):
    df = df.reset_index()
    df.columns = ["_".join(c).strip("_") if isinstance(c, tuple) else c for c in df.columns]
    # soccerdata leaves the league empty for the Bundesliga rows of the combined table
    missing_leagues = set(BIG5.values()) - set(df["league"].dropna())
    if df["league"].isna().any():
        assert len(missing_leagues) == 1, f"Cannot infer the empty league: {missing_leagues}"
        df["league"] = df["league"].fillna(missing_leagues.pop())
    return df


def fetch_fbref(seasons) -> pd.DataFrame:
    fbref = sd.FBref(leagues="Big 5 European Leagues Combined", seasons=seasons)
    merged = None
    for stat_type in STAT_TYPES:
        print(f"Fetching {stat_type}...")
        df = flatten_columns(fbref.read_player_season_stats(stat_type=stat_type))
        if merged is None:
            merged = df
            continue
        new_cols = [c for c in df.columns if c not in merged.columns]
        merged = merged.merge(df[KEY_COLS + new_cols], on=KEY_COLS, how="left")
    return merged


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    raw = fetch_fbref(STATS_SEASONS)
    raw.to_csv(PROCESSED_DIR / "fbref_raw_stats.csv", index=False)
    print(f"Raw FBref stats: {raw.shape}")

    source = pd.DataFrame({
        "player": raw["player"],
        "teams": raw["team"].map(lambda t: [t]),
        "tm_season": raw["season"].map(tm_season),
        "competition_id": raw["league"].map(LEAGUE_TO_TM),
        "birth_year": pd.to_numeric(raw["born"], errors="coerce"),
    })

    conn = sqlite3.connect(DB_PATH)
    matched = attach_tm_ids(source, conn, "fbref")
    ok = matched["status"] == "ok"

    stats = raw.loc[ok].drop(columns=["league", "season"]).rename(columns={"team": "fbref_team", "player": "fbref_player"})
    stats.columns = snake_case(stats.columns)
    ids = matched.loc[ok, ["player_id", "club_id", "tm_season", "competition_id", "match_score"]]
    table = pd.concat([ids.rename(columns={"tm_season": "season"}), stats], axis=1)
    write_stats_table(conn, "fbref_player_season", table)
    conn.close()


if __name__ == "__main__":
    main()
