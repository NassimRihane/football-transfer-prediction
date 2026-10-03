# scripts/filter_data.py
"""Keep the Big 5 leagues from DATE_MIN onwards and write the tables to data/processed."""
import pandas as pd

from config import BIG5, DATE_MIN, PROCESSED_DIR, RAW_DIR


def read_raw(name, **kwargs):
    return pd.read_csv(RAW_DIR / f"{name}.csv", **kwargs)


competitions = read_raw("competitions")
competitions = competitions[competitions["competition_id"].isin(BIG5)]

games = read_raw("games", parse_dates=["date"])
games = games[(games["date"] >= DATE_MIN) & games["competition_id"].isin(BIG5)]

appearances = read_raw("appearances", parse_dates=["date"])
appearances = appearances[appearances["game_id"].isin(games["game_id"])]

# Includes clubs that were relegated later on
club_ids = pd.unique(games[["home_club_id", "away_club_id"]].values.ravel())
clubs = read_raw("clubs")
clubs = clubs[clubs["club_id"].isin(club_ids)]

# players.csv only contains the players Transfermarkt still lists, so many players who
# appear in these games (often ones who left for other leagues) have no profile and no
# valuations. They are kept with their name only, so every appearance has its player.
players = read_raw("players")
players = players[players["player_id"].isin(appearances["player_id"])].assign(has_tm_profile=1)
no_profile = (
    appearances[~appearances["player_id"].isin(players["player_id"])]
    .sort_values("date")
    .groupby("player_id", as_index=False)["player_name"].last()
    .rename(columns={"player_name": "name"})
    .assign(has_tm_profile=0)
)
players = pd.concat([players, no_profile], ignore_index=True)
print(f"players: {len(players)}, of which {len(no_profile)} without a Transfermarkt profile")

# Full history (no DATE_MIN) so that past values and transfers can be used as features
valuations = read_raw("player_valuations")
valuations = valuations[valuations["player_id"].isin(players["player_id"])]
valuations = valuations.drop_duplicates(["player_id", "date"])

transfers = read_raw("transfers")
transfers = transfers[transfers["player_id"].isin(players["player_id"])]

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
for name, df in {
    "competitions": competitions, "clubs": clubs, "players": players,
    "player_valuations": valuations, "transfers": transfers,
    "games": games, "appearances": appearances,
}.items():
    df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)
    print(name, df.shape)
