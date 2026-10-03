import sqlite3
import pandas as pd

from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)


# Top 10 highest valuations by player
query ="""
SELECT p.name, p.position, c.name AS club, comp.name AS league, pv.market_value_in_eur, pv.date
FROM players p
JOIN clubs c ON p.current_club_id = c.club_id
JOIN competitions comp ON comp.competition_id = c.domestic_competition_id
JOIN player_valuations pv ON p.player_id = pv.player_id
WHERE pv.date = (
    SELECT MAX(date) FROM player_valuations pv2 WHERE pv2.player_id = p.player_id
)
ORDER BY pv.market_value_in_eur DESC
LIMIT 10
"""

# Top scoring clubs in 2023/24
query2 = """
SELECT c.name AS club, comp.name AS league, SUM(a.goals) AS total_goals
FROM appearances a
JOIN games g ON a.game_id = g.game_id
JOIN clubs c ON a.player_club_id = c.club_id
JOIN competitions comp ON g.competition_id = comp.competition_id
WHERE g.season = 2023
GROUP BY c.club_id
ORDER BY total_goals DESC
LIMIT 15
"""

# Most expensive transfers
query3 = """
SELECT p.name, cf.name AS from_club, ct.name AS to_club, t.transfer_fee, t.transfer_date
FROM transfers t
JOIN players p ON t.player_id = p.player_id
LEFT JOIN clubs cf ON t.from_club_id = cf.club_id
JOIN clubs ct ON t.to_club_id = ct.club_id
WHERE t.transfer_fee IS NOT NULL
ORDER BY t.transfer_fee DESC
LIMIT 15
"""


query4 = """
SELECT
    (SELECT COUNT(*) FROM players) AS nb_players,
    (SELECT COUNT(DISTINCT player_id) FROM appearances) AS nb_players_with_appearances,
    (SELECT COUNT(*) FROM clubs) AS nb_clubs,
    (SELECT COUNT(*) FROM competitions) AS nb_competitions;
"""



current_query = query4


df = pd.read_sql(current_query, conn)
print(df)
