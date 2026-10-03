# football-transfer-prediction

Predicting the market value of football players in Europe's Big 5 leagues (Premier League, LaLiga, Ligue 1, Serie A, Bundesliga).

The plan: train on the 2019/20 to 2023/24 seasons, check the predictions against how values really evolved in 2024/25 and 2025/26, then add those two seasons to forecast the future.

The project combines three data sources:

- **Transfermarkt** via the Kaggle dataset [`davidcariboo/player-scores`](https://www.kaggle.com/datasets/davidcariboo/player-scores): players, clubs, games, appearances, market valuations and transfers.
- **FBref** via [`soccerdata`](https://github.com/probberechts/soccerdata): per-season player stats (standard, shooting, keeper, playing time, misc).
- **Understat** via `soccerdata`: xG, xA, key passes, xGChain and xGBuildup per player and season.

Everything is loaded into a local SQLite database (`db/football.db`).

> **Status:** data collection and preparation. No model yet.

## Project structure

```
.
├── data/
│   ├── raw/            # Kaggle CSVs as downloaded (git-ignored)
│   └── processed/      # Filtered CSVs, raw stats and match reviews (git-ignored)
├── db/
│   └── football.db     # SQLite database (git-ignored)
├── scripts/
│   ├── config.py                 # Paths, leagues, seasons: shared by every script
│   ├── matching.py               # Links FBref/Understat rows to Transfermarkt ids
│   ├── download_data.py          # 1. Download the Kaggle dataset into data/raw
│   ├── filter_data.py            # 2. Keep the Big 5 leagues from 2019-06-01 onwards
│   ├── build_db.py               # 3. Create db/football.db from sql/schema.sql
│   ├── fetch_understat_stats.py  # 4. Understat stats -> understat_player_season
│   ├── fetch_fbref_stats.py      # 5. FBref stats -> fbref_player_season
│   ├── diagnose_club_names.py    # Help: suggest matches for unmatched club names
│   ├── remove_leagues.py         # Utility: delete leagues from the DB
│   └── test_queries.py           # Example SQL queries against the DB
├── sql/
│   └── schema.sql      # Schema of the Transfermarkt tables
└── requirements.txt
```

## Setup

Requires Python 3 (developed with 3.14).

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`download_data.py` uses `kagglehub`, so you need Kaggle credentials: either
`~/.kaggle/kaggle.json` or the `KAGGLE_USERNAME` / `KAGGLE_KEY` environment variables.
See the [Kaggle API docs](https://www.kaggle.com/docs/api).

FBref is scraped through a headless Chrome (SeleniumBase), so Chrome must be installed.

## Running the pipeline

```bash
python scripts/download_data.py          # data/raw/*.csv
python scripts/filter_data.py            # data/processed/*.csv
python scripts/build_db.py               # db/football.db, rebuilt from scratch
python scripts/fetch_understat_stats.py  # a few minutes
python scripts/fetch_fbref_stats.py      # ~2 hours the first time, see below
```

`build_db.py` deletes the database, including the stats tables, so rerun the two fetch scripts after it. soccerdata caches every page in `~/soccerdata/data/`, so reruns are fast.

### 1. Download: `download_data.py`
Downloads the Transfermarkt dataset with `kagglehub` and copies its CSVs into `data/raw/`.

### 2. Filter: `filter_data.py`
Keeps the Big 5 leagues (Transfermarkt codes `GB1`, `ES1`, `FR1`, `IT1`, `L1`):

- games from **2019-06-01** onwards in those competitions, and their appearances;
- every club that played in those games, including clubs that were later relegated;
- every player with at least one of those appearances, with all their valuations and transfers.

### 3. Build the database: `build_db.py`
Creates the tables from `sql/schema.sql` (with primary and foreign keys), then loads the processed CSVs. **The schema decides which columns are kept:** to add a column, add it to `schema.sql`. The script prints the CSV columns it skips and checks the foreign keys at the end.

### 4–5. Stats: `fetch_understat_stats.py` and `fetch_fbref_stats.py`
Both fetch player season stats for the seasons in `STATS_SEASONS` (`config.py`), link each row to a Transfermarkt `player_id` and `club_id` (see [Matching](#matching)) and write one table:

| Table | One row per | Main columns |
|---|---|---|
| `understat_player_season` | player, season, league | xG, npxG, xA, shots, key passes, xGChain, xGBuildup |
| `fbref_player_season` | player, season, club | minutes, starts, goals, assists, shots, saves, cards, fouls, crosses, interceptions, tackles won, on/off-pitch team goals |

Both tables have `player_id`, `club_id`, `season` (Transfermarkt convention: `2019` = 2019/20), `competition_id` and `match_score`. The raw stats are also saved in `data/processed/`.

FBref throttles requests: each page takes about 5 minutes, and there are 5 pages per season.

## Matching

FBref and Understat don't use Transfermarkt ids, so `matching.py` links them by name:

1. **Clubs**, within each league and season: exact match on the normalized name (no accents, no
   "FC"/"AC"...), then aliases from `CLUB_ALIASES`, then fuzzy matching. Each Transfermarkt club is used only once. Fuzzy matches are printed so you can check them.
2. **Players**, within the matched club and season. A candidate is accepted when:
   - the name score (`rapidfuzz` `WRatio`) is at least 90, or
   - the score is at least 80 and the surnames match ("Mat Ryan" / "Mathew Ryan"), or
   - the birth year is the same and the score is at least 75 or the surnames match
     ("Kostas Manolas" / "Konstantinos Manolas"). Only FBref has birth years.

   A birth year more than one year off rules a candidate out.

Current match rates: **FBref 99.4%** (2019/20), **Understat 97.4%** (2019/20 to 2023/24).
The rows that need a look are written to data/processed:

| File | Contents |
|---|---|
| `{source}_review.csv` | Unmatched rows, and matches with a score below 90 |
| `{source}_unmatched_clubs.csv` | Source clubs with no Transfermarkt club |

For unmatched clubs, run `diagnose_club_names.py`: it suggests the 3 closest Transfermarkt clubs, and you can add the right one to `CLUB_ALIASES`.

## Known data limitations

- **Transfermarkt profiles are incomplete.** The Kaggle `players.csv` only lists players that
  Transfermarkt still tracks, so about a quarter of the players in 2019/20 (often those who left for other leagues, like Firmino or Mata) have no profile and **no valuations**.
  They are kept in `players` with their name only and `has_tm_profile = 0`, but they can't be used as training targets.
- **Some appearances are missing** (e.g. Conor Gallagher at Crystal Palace in 2021/22). The
  matching also looks at the club recorded on each valuation to make up for it.
- **Valuations and transfers start at 2019-06-01**: the current Kaggle version has nothing earlier.
- **Snapshot columns.** `players.contract_expiration_date`, `agent_name` and `current_club_id`,
  and `clubs.squad_size` / `average_age`, hold the value at download time. Don't use them as features for past seasons.
- **No advanced stats on FBref.** FBref no longer has the Opta tables (passing, defense,
  possession, goal-creating actions), so there are no progressive passes, tackles or pressures for now.
- **Season conventions:** FBref and Understat use `"1920"` for 2019/20, Transfermarkt uses
  `2019`. `config.tm_season` converts between them.

## Utilities

- **`test_queries.py`**: example queries (highest valuations, top-scoring clubs, most expensive transfers, row counts). Set `current_query` to the one you want to run.
- **`remove_leagues.py`**: deletes the leagues in `LEAGUES_TO_REMOVE` with their clubs, players, games, appearances, valuations and transfers.
