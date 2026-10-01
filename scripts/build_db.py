# scripts/build_db.py
import sqlite3
import pandas as pd
import os

os.makedirs("db", exist_ok=True)

db_path = "db/football.db"

if os.path.exists(db_path):
    os.remove(db_path)


conn = sqlite3.connect("db/football.db")

#with open("sql/schema.sql") as f:
#    conn.executescript(f.read())


EXPECTED_COLUMNS = {
    "competitions": ["competition_id", "name", "country_name", "confederation"],
    "clubs": ["club_id", "name", "domestic_competition_id", "squad_size", "average_age", "stadium_name"],
    "players": ["player_id", "name", "date_of_birth", "country_of_citizenship", "position","sub_position","foot","height_in_cm", "current_club_id",],
    "games": ["game_id", "competition_id", "season",round,"date", "home_club_id", "away_club_id", "home_club_goals", "away_club_goals"],
    "appearances": ["appearance_id", "game_id", "player_id", "player_club_id", "date", "competition_id","yellow_cards", "red_cards", "goals", "assists", "minutes_played"],
    "player_valuations": ["player_id", "date","market_value_in_eur", "current_club_id"],
    "transfers": ["player_id", "transfer_date", "from_club_id", "to_club_id","transfer_fee", "market_value_in_eur"]
}

for table, expected_cols in EXPECTED_COLUMNS.items():
    df = pd.read_csv(f"data/processed/{table}.csv")
    available = [col for col in df.columns if col in expected_cols]
    missing = [col for col in df.columns if col not in expected_cols]
    if missing:
        print(f"{table}: column missing from CSV: {missing}")
    df = df[available]
    df.to_sql(table, conn, if_exists="append", index=False)
    print(f"{table}: {len(df)} insertion done")

conn.close()