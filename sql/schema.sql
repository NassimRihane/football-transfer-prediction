-- sql/schema.sql

CREATE TABLE competitions (
    competition_id TEXT PRIMARY KEY,
    name TEXT,
    country_name TEXT,
    confederation TEXT
);

CREATE TABLE clubs (
    club_id INTEGER PRIMARY KEY,
    name TEXT,
    domestic_competition_id TEXT REFERENCES competitions(competition_id),
    squad_size INTEGER,
    average_age REAL,
    stadium_name TEXT
);

CREATE TABLE players (
    player_id INTEGER PRIMARY KEY,     
    name TEXT,
    date_of_birth DATE,
    nationality TEXT,
    position TEXT,                    
    sub_position TEXT,
    foot TEXT,
    height_in_cm INTEGER,
    current_club_id INTEGER REFERENCES clubs(club_id)
);

CREATE TABLE games (
    game_id INTEGER PRIMARY KEY,
    competition_id TEXT REFERENCES competitions(competition_id),
    season INTEGER,
    date DATE,
    home_club_id INTEGER REFERENCES clubs(club_id),
    away_club_id INTEGER REFERENCES clubs(club_id),
    home_club_goals INTEGER,
    away_club_goals INTEGER
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

CREATE TABLE player_valuations (
    player_id INTEGER REFERENCES players(player_id),
    date DATE,
    market_value_in_eur BIGINT,
    current_club_id INTEGER REFERENCES clubs(club_id),
    PRIMARY KEY (player_id, date)
);

CREATE TABLE transfers (
    player_id INTEGER REFERENCES players(player_id),
    transfer_date DATE,
    from_club_id INTEGER REFERENCES clubs(club_id),
    to_club_id INTEGER REFERENCES clubs(club_id),
    transfer_fee BIGINT,
    market_value_in_eur BIGINT
);


CREATE TABLE player_season_stats (
    player_id INTEGER REFERENCES players(player_id),
    season INTEGER,
    club_id INTEGER REFERENCES clubs(club_id),
    competition_id TEXT REFERENCES competitions(competition_id),
    matches_played INTEGER,
    minutes_played INTEGER,
    goals INTEGER,
    assists INTEGER,
    PRIMARY KEY (player_id, season, club_id)
);