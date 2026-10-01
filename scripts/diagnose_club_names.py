# scripts/diagnose_club_names.py
import sqlite3
import pandas as pd
from rapidfuzz import process, fuzz
import unicodedata

DB_PATH = "db/football.db"

def normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return name.lower().strip()

STOPWORDS = {"de", "fc", "cf", "afc", "cd", "ud", "sc", "ac", "the", "club"}

def normalize_club_name(name: str) -> str:
    name = normalize_name(name)
    tokens = [t for t in name.split() if t not in STOPWORDS]
    return " ".join(tokens)

# Colle ici la liste "Clubs with no correspondance" de ta dernière exécution,
# juste les noms de clubs (sans la saison, puisqu'ils sont tous en "1920")
UNMATCHED_FBREF_CLUBS = [
    "Bologna", "Bordeaux", "Rennes", "Valladolid"
]

conn = sqlite3.connect(DB_PATH)
sql_clubs = pd.read_sql("SELECT DISTINCT name FROM clubs", conn)
sql_clubs["name_norm"] = sql_clubs["name"].apply(normalize_club_name)

for fbref_name in UNMATCHED_FBREF_CLUBS:
    fbref_norm = normalize_club_name(fbref_name)
    top3 = process.extract(
        fbref_norm, sql_clubs["name_norm"], scorer=fuzz.WRatio, limit=3
    )
    print(f"\nFBref: '{fbref_name}' (normalisé: '{fbref_norm}')")
    for match_norm, score, idx in top3:
        original_name = sql_clubs.iloc[idx]["name"]
        print(f"   -> '{original_name}' (score: {score:.0f})")

conn.close()