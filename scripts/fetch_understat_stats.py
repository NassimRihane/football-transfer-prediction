# scripts/fetch_understat_stats.py
"""Fetch Understat player season stats (xG, xA, key passes, xGChain, xGBuildup) for the
Big 5 and link them to Transfermarkt ids. Pages are cached in ~/soccerdata/data/Understat.
"""
import sqlite3

import pandas as pd
import soccerdata as sd

from config import BIG5, DB_PATH, PROCESSED_DIR, STATS_SEASONS, tm_season
from matching import attach_tm_ids, write_stats_table

LEAGUE_TO_TM = {league: code for code, league in BIG5.items()}


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    understat = sd.Understat(leagues=list(BIG5.values()), seasons=STATS_SEASONS)
    raw = understat.read_player_season_stats().reset_index()
    raw.to_csv(PROCESSED_DIR / "understat_raw_stats.csv", index=False)
    print(f"Raw Understat stats: {raw.shape}")

    # A player who changed club within the league has one row, with "Club A,Club B"
    source = pd.DataFrame({
        "player": raw["player"],
        "teams": raw["team"].str.split(","),
        "tm_season": raw["season"].map(tm_season),
        "competition_id": raw["league"].map(LEAGUE_TO_TM),
        "birth_year": float("nan"),
    })

    conn = sqlite3.connect(DB_PATH)
    matched = attach_tm_ids(source, conn, "understat")
    ok = matched["status"] == "ok"

    stats = (raw.loc[ok]
             .drop(columns=["league", "season", "league_id", "season_id", "team_id"])
             .rename(columns={"team": "understat_team", "player": "understat_player",
                              "player_id": "understat_player_id"}))
    ids = matched.loc[ok, ["player_id", "club_id", "tm_season", "competition_id", "match_score"]]
    table = pd.concat([ids.rename(columns={"tm_season": "season"}), stats], axis=1)
    write_stats_table(conn, "understat_player_season", table)
    conn.close()


if __name__ == "__main__":
    main()
