# scripts/remove_leagues.py
"""Delete leagues, and their clubs, players, games and related rows, from the database.

Not needed with the current filter_data.py (it only keeps the Big 5); useful if the
database was built from a wider selection of leagues.
"""
import sqlite3

from config import DB_PATH

LEAGUES_TO_REMOVE = ["NL1", "PO1"]  # Eredivisie, Liga Portugal

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON;")
cur = conn.cursor()

placeholders = ",".join("?" for _ in LEAGUES_TO_REMOVE)

# 1. Collect the club ids before deleting anything
cur.execute(
    f"SELECT club_id FROM clubs WHERE domestic_competition_id IN ({placeholders})",
    LEAGUES_TO_REMOVE
)
club_ids = [row[0] for row in cur.fetchall()]
print(f"Clubs: {len(club_ids)}")

if club_ids:
    club_placeholders = ",".join("?" for _ in club_ids)

    # 2. Players currently at those clubs
    cur.execute(
        f"SELECT player_id FROM players WHERE current_club_id IN ({club_placeholders})",
        club_ids
    )
    player_ids = [row[0] for row in cur.fetchall()]
    print(f"Players: {len(player_ids)}")
    player_placeholders = ",".join("?" for _ in player_ids) if player_ids else None

    # 3. Games of those competitions
    cur.execute(
        f"SELECT game_id FROM games WHERE competition_id IN ({placeholders})",
        LEAGUES_TO_REMOVE
    )
    game_ids = [row[0] for row in cur.fetchall()]
    print(f"Games: {len(game_ids)}")
    game_placeholders = ",".join("?" for _ in game_ids) if game_ids else None

    # 4. Delete from the most dependent tables to the root ones
    if game_placeholders:
        cur.execute(f"DELETE FROM appearances WHERE game_id IN ({game_placeholders})", game_ids)
        print(f"appearances deleted: {cur.rowcount}")

        cur.execute(f"DELETE FROM games WHERE game_id IN ({game_placeholders})", game_ids)
        print(f"games deleted: {cur.rowcount}")

    if player_placeholders:
        cur.execute(f"DELETE FROM player_valuations WHERE player_id IN ({player_placeholders})", player_ids)
        print(f"player_valuations deleted: {cur.rowcount}")

        cur.execute(f"DELETE FROM transfers WHERE player_id IN ({player_placeholders})", player_ids)
        print(f"transfers deleted: {cur.rowcount}")

        cur.execute(f"DELETE FROM players WHERE player_id IN ({player_placeholders})", player_ids)
        print(f"players deleted: {cur.rowcount}")

    cur.execute(f"DELETE FROM clubs WHERE club_id IN ({club_placeholders})", club_ids)
    print(f"clubs deleted: {cur.rowcount}")

cur.execute(f"DELETE FROM competitions WHERE competition_id IN ({placeholders})", LEAGUES_TO_REMOVE)
print(f"competitions deleted: {cur.rowcount}")

conn.commit()
conn.close()
print("Done")
