# scripts/diagnose_club_names.py
"""Suggest Transfermarkt clubs for the source clubs that could not be matched.

Reads the *_unmatched_clubs.csv files written by the fetch_*_stats.py scripts. Add the
right suggestion to CLUB_ALIASES in matching.py, then rerun the fetch script.
"""
import sqlite3

import pandas as pd
from rapidfuzz import fuzz, process

from config import DB_PATH, PROCESSED_DIR
from matching import normalize_club_name, source_club_key

conn = sqlite3.connect(DB_PATH)
tm_clubs = pd.read_sql("SELECT DISTINCT name FROM clubs", conn)
conn.close()
tm_clubs["name_norm"] = tm_clubs["name"].map(normalize_club_name)

for path in sorted(PROCESSED_DIR.glob("*_unmatched_clubs.csv")):
    unmatched = pd.read_csv(path)
    if unmatched.empty:
        continue
    print(f"== {path.name}")
    for team in unmatched["team"].unique():
        key = source_club_key(team)
        print(f"\n'{team}' (normalized: '{key}')")
        for match_norm, score, idx in process.extract(key, tm_clubs["name_norm"], scorer=fuzz.WRatio, limit=3):
            print(f"   -> '{tm_clubs.iloc[idx]['name']}' (alias value: '{match_norm}', score: {score:.0f})")
