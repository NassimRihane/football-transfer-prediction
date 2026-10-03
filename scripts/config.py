# scripts/config.py
"""Paths and settings shared by every script, resolved from the repo root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DB_PATH = ROOT / "db" / "football.db"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"

# Transfermarkt competition code -> soccerdata league name
BIG5 = {
    "GB1": "ENG-Premier League",
    "ES1": "ESP-La Liga",
    "FR1": "FRA-Ligue 1",
    "IT1": "ITA-Serie A",
    "L1": "GER-Bundesliga",
}

# Games, appearances and clubs are kept from this date onwards
DATE_MIN = "2019-06-01"

# Seasons fetched from FBref and Understat ("1920" = 2019/20)
STATS_SEASONS = ["1920", "2021", "2122", "2223", "2324"]


def tm_season(season: str) -> int:
    """FBref/Understat season ("1920") -> Transfermarkt season (2019)."""
    return 2000 + int(str(season)[:2])
