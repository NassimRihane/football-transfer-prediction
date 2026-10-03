# scripts/build_db.py
"""Recreate db/football.db from sql/schema.sql and the CSVs in data/processed.

The stats tables are dropped with the old database: rerun the fetch_*_stats.py scripts
afterwards (they read from the soccerdata cache, so this is fast).
"""
import sqlite3

import pandas as pd

from config import DB_PATH, PROCESSED_DIR, SCHEMA_PATH

TABLES = ["competitions", "clubs", "players", "games", "appearances", "player_valuations", "transfers"]

DB_PATH.parent.mkdir(exist_ok=True)
DB_PATH.unlink(missing_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.executescript(SCHEMA_PATH.read_text())

for table in TABLES:
    schema_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    df = pd.read_csv(PROCESSED_DIR / f"{table}.csv")
    missing = [c for c in schema_cols if c not in df.columns]
    if missing:
        raise ValueError(f"{table}: columns in schema.sql but not in the CSV: {missing}")
    skipped = [c for c in df.columns if c not in schema_cols]
    if skipped:
        print(f"{table}: CSV columns not in schema.sql, skipped: {skipped}")
    df[schema_cols].to_sql(table, conn, if_exists="append", index=False)
    print(f"{table}: {len(df)} rows inserted")

violations = pd.read_sql("PRAGMA foreign_key_check", conn)
if violations.empty:
    print("Foreign keys: OK")
else:
    print("Foreign key violations:")
    print(violations.groupby(["table", "parent"]).size().to_string())

conn.commit()
conn.close()
