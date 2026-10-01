# scripts/filter_data.py
import pandas as pd

RAW = "data/raw/"
OUT = "data/processed/"


competitions = pd.read_csv(RAW + "competitions.csv")
leagues = ["GB1", "ES1", "FR1", "IT1", "L1"]  # codes Transfermarkt
# GB1=Premier League, ES1=LaLiga, FR1=Ligue 1, IT1=Serie A, L1=Bundesliga
competitions = competitions[competitions["competition_id"].isin(leagues)]



DATE_MIN = "2019-06-01"

games_all = pd.read_csv(RAW + "games.csv", parse_dates=["date"])
games_period = games_all[
    (games_all["date"] >= DATE_MIN) &
    (games_all["competition_id"].isin(leagues))
]

appearances_all = pd.read_csv(RAW + "appearances.csv")
appearances_period = appearances_all[appearances_all["game_id"].isin(games_period["game_id"])]
historical_player_ids = appearances_period["player_id"].unique()



players_all = pd.read_csv(RAW + "players.csv")
players = players_all[players_all["player_id"].isin(historical_player_ids)]
player_ids = players["player_id"].unique()

valuations = pd.read_csv(RAW + "player_valuations.csv", parse_dates=["date"])
valuations = valuations[
    (valuations["player_id"].isin(player_ids)) &
    (valuations["date"] >= DATE_MIN)
]

transfers = pd.read_csv(RAW + "transfers.csv", parse_dates=["transfer_date"])
transfers = transfers[
    (transfers["player_id"].isin(player_ids)) &
    (transfers["transfer_date"] >= DATE_MIN)
]


# counts relegated clubs
historical_club_ids = pd.unique(games_period[["home_club_id", "away_club_id"]].values.ravel())

clubs_all = pd.read_csv(RAW + "clubs.csv")
clubs = clubs_all[clubs_all["club_id"].isin(historical_club_ids)]
club_ids = clubs["club_id"].unique()




for name, df in {
    "competitions": competitions, "clubs": clubs, "players": players,
    "player_valuations": valuations, "transfers": transfers,
    "games": games_period, "appearances": appearances_period
}.items():
    df.to_csv(OUT + f"{name}.csv", index=False)
    print(name, df.shape)