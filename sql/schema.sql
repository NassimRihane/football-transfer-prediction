-- sql/schema.sql
-- Transfermarkt tables, created and filled by build_db.py: only the columns listed here
-- are loaded from data/processed. The stats tables (fbref_player_season,
-- understat_player_season) are written by the fetch_*_stats.py scripts.
--
-- Columns marked "snapshot" hold the value at download time, not at the time of each
-- season: they must not be used as historical features.

CREATE TABLE competitions (
    competition_id TEXT PRIMARY KEY,
    name TEXT,
    country_name TEXT,
    confederation TEXT
);

CREATE TABLE clubs (
    club_id INTEGER PRIMARY KEY,
    name TEXT,
    domestic_competition_id TEXT,      -- snapshot: may be a lower league after relegation
    squad_size INTEGER,                -- snapshot
    average_age REAL,                  -- snapshot
    stadium_name TEXT
);

CREATE TABLE players (
    player_id INTEGER PRIMARY KEY,
    name TEXT,
    has_tm_profile INTEGER,            -- 0: only known from appearances, no profile or valuations
    date_of_birth DATE,
    country_of_citizenship TEXT,
    country_of_birth TEXT,
    position TEXT,
    sub_position TEXT,
    foot TEXT,
    height_in_cm INTEGER,
    current_club_id INTEGER,           -- snapshot, may be outside the Big 5
    contract_expiration_date DATE,     -- snapshot
    agent_name TEXT                    -- snapshot
);

CREATE TABLE games (
    game_id INTEGER PRIMARY KEY,
    competition_id TEXT REFERENCES competitions(competition_id),
    season INTEGER,
    round TEXT,
    date DATE,
    home_club_id INTEGER REFERENCES clubs(club_id),
    away_club_id INTEGER REFERENCES clubs(club_id),
    home_club_goals INTEGER,
    away_club_goals INTEGER,
    home_club_position INTEGER,        -- league position before the game
    away_club_position INTEGER
);

CREATE TABLE appearances (
    appearance_id TEXT PRIMARY KEY,
    game_id INTEGER REFERENCES games(game_id),
    player_id INTEGER REFERENCES players(player_id),
    player_club_id INTEGER REFERENCES clubs(club_id),
    competition_id TEXT REFERENCES competitions(competition_id),
    date DATE,
    goals INTEGER,
    assists INTEGER,
    minutes_played INTEGER,
    yellow_cards INTEGER,
    red_cards INTEGER
);

-- Full valuation and transfer history of the selected players, including before 2019,
-- so that past values can be used as features. Club ids may be outside the Big 5.
CREATE TABLE player_valuations (
    player_id INTEGER REFERENCES players(player_id),
    date DATE,
    market_value_in_eur BIGINT,
    current_club_id INTEGER,
    PRIMARY KEY (player_id, date)
);

CREATE TABLE transfers (
    player_id INTEGER REFERENCES players(player_id),
    transfer_date DATE,
    transfer_season TEXT,
    from_club_id INTEGER,
    from_club_name TEXT,
    to_club_id INTEGER,
    to_club_name TEXT,
    transfer_fee BIGINT,
    market_value_in_eur BIGINT
);
