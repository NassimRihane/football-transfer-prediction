import sqlite3
import pandas as pd
import soccerdata as sd
from rapidfuzz import process, fuzz
import unicodedata
import os

DB_PATH = "db/football.db"
OUT_DIR = "data/processed"


LEAGUES = ["ENG-Premier League"]
LEAGUE_CODE_MAP = {
    "ENG-Premier League": "GB1"
}
SEASONS = ["1920"]


# LEAGUES = ["ENG-Premier League", "ESP-La Liga", "FRA-Ligue 1", "ITA-Serie A", "GER-Bundesliga"]
# LEAGUE_CODE_MAP = {
#     "ENG-Premier League": "GB1", "ESP-La Liga": "ES1", "FRA-Ligue 1": "FR1",
#     "ITA-Serie A": "IT1", "GER-Bundesliga": "L1",
# }
# SEASONS = ["1920", "2021", "2122", "2223", "2324"]

BASIC_STAT_TYPES = ["standard", "shooting", "keeper", "playing_time", "misc"]


def normalize_columns(df):
    df = df.reset_index()
    df.columns = ["_".join(c).strip("_") if isinstance(c, tuple) else c
                  for c in df.columns]
    return df


def normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return name.lower().strip()


STOPWORDS = {"de", "fc", "cf", "afc", "cd", "ud", "sc", "ac", "the", "club"}

def normalize_club_name(name: str) -> str:
    name = normalize_name(name)
    tokens = [t for t in name.split() if t not in STOPWORDS]
    return " ".join(tokens)

CLUB_ALIASES = {
    "alaves": "deportivo alaves",
    "angers": "angers sco",
    "atalanta": "atalanta bc",
    "athletic": "athletic bilbao",
    "bologna": "bologna football club 1909",
    "bordeaux": "fc girondins bordeaux",
    "brescia": "brescia calcio",
    "brest": "stade brestois 29",
    "brighton": "brighton & hove albion",
    "cagliari": "cagliari calcio",
    "dijon": "dijon fco",
    "dortmund": "borussia dortmund",
    "dusseldorf": "fortuna dusseldorf",
    "eibar": "sd eibar",
    "espanyol": "rcd espanyol barcelona",
    "fiorentina": "acf fiorentina",
    "frankfurt": "eintracht frankfurt",
    "genoa": "genoa cfc",
    "gladbach": "borussia monchengladbach",
    "hoffenheim": "tsg 1899 hoffenheim",
    "inter": "inter milan",
    "koln": "1.fc koln",
    "lazio": "societa sportiva lazio s.p.a.",
    "lecce": "us lecce",
    "leverkusen": "bayer 04 leverkusen",
    "lille": "losc lille",
    "lyon": "olympique lyon",
    "mainz 05": "1.fsv mainz 05",
    "mallorca": "rcd mallorca",
    "manchester utd": "manchester united",
    "marseille": "olympique marseille",
    "monaco": "as monaco",
    "montpellier": "montpellier hsc",
    "napoli": "ssc napoli",
    "newcastle": "newcastle united",
    "nice": "ogc nice",
    "nimes": "nimes olympique",
    "osasuna": "ca osasuna",
    "paris sg": "paris saint-germain",
    "parma": "parma calcio 1913",
    "real betis": "real betis balompie",
    "reims": "stade reims",
    "rennes": "stade rennais fc",
    "roma": "associazione sportiva roma",
    "saint-etienne": "as saint-etienne",
    "sampdoria": "uc sampdoria",
    "sassuolo": "us sassuolo",
    "strasbourg": "rc strasbourg alsace",
    "tottenham": "tottenham hotspur",
    "udinese": "udinese calcio",
    "union berlin": "1.fc union berlin",
    "valladolid": "real valladolid cf",
    "werder bremen": "sv werder bremen",
    "west ham": "west ham united",
    "wolfsburg": "vfl wolfsburg",
    "wolves": "wolverhampton wanderers"
}

def resolve_club_alias(name_norm: str) -> str:
    aliased = CLUB_ALIASES.get(name_norm, name_norm)
    return normalize_club_name(aliased)

def fetch_basic_stats(league_key, seasons):
    fbref = sd.FBref(leagues=league_key, seasons=seasons)
    dfs = {}
    for st in BASIC_STAT_TYPES:
        print(f"  [{league_key}] fetching {st}...")
        dfs[st] = normalize_columns(fbref.read_player_season_stats(stat_type=st))
    return dfs


def merge_stat_types(dfs: dict, key_cols=("league", "season", "team", "player")):
    key_cols = list(key_cols)
    base_name = next(iter(dfs))
    merged = dfs[base_name]
    for name, df in dfs.items():
        if name == base_name:
            continue
        cols_to_add = [c for c in df.columns if c not in merged.columns]
        merged = merged.merge(df[key_cols + cols_to_add], on=key_cols, how="left")
    return merged


def fetch_fbref_all():
    all_frames = []
    print("Big 5 European Leagues Combined")
    big5_basic = fetch_basic_stats("Big 5 European Leagues Combined", SEASONS)
    big5_merged = merge_stat_types(big5_basic)
    all_frames.append(big5_merged)
    full = pd.concat(all_frames, ignore_index=True)
    full["competition_id"] = full["league"].map(LEAGUE_CODE_MAP)
    return full


def build_season_rosters(conn) -> pd.DataFrame:
    query = """
        SELECT DISTINCT a.player_id, g.season, a.player_club_id AS club_id, p.name AS player_name, c.name AS club_name
        FROM appearances a
        JOIN games g ON a.game_id = g.game_id
        JOIN players p ON a.player_id = p.player_id
        JOIN clubs c ON a.player_club_id = c.club_id
    """
    return pd.read_sql(query, conn)



def fbref_season_to_tm_year(season_str: str) -> int:
    start_two_digits = int(str(season_str)[:2])
    return 2000 + start_two_digits

def match_players(fbref_df: pd.DataFrame, conn: sqlite3.Connection) -> pd.DataFrame:
    roster = build_season_rosters(conn)
    roster["club_norm"] = roster["club_name"].apply(normalize_club_name).apply(resolve_club_alias)
    roster["name_norm"] = roster["player_name"].apply(normalize_name)

    matches = []
    unmatched_clubs = set()

    for (club, season), group in fbref_df.groupby(["team", "season"]):
        club_norm  = resolve_club_alias(normalize_club_name(club))
        tm_season = fbref_season_to_tm_year(season)
        candidates = roster[
            (roster["club_norm"] == club_norm) & (roster["season"] == tm_season)
        ]
        if candidates.empty:
            unmatched_clubs.add((club, season))
            continue

        candidate_names = candidates["name_norm"].to_list()
        for _, row in group.iterrows():
            name_norm = normalize_name(row["player"])
            best = process.extractOne(
                name_norm, candidate_names, scorer=fuzz.WRatio
            )
            if best and best[1] >= 85:
                matched_row = candidates.iloc[best[2]]
                matches.append({
                    "fbref_player": row["player"],
                    "fbref_team": row["team"],
                    "season": row["season"],
                    "player_id": matched_row["player_id"],
                    "match_score": best[1],
                })

    print(f"Nb saisons distinctes côté FBref : {fbref_df['season'].unique()}")
    print(f"Nb saisons distinctes côté roster (SQL) : {sorted(roster['season'].unique())}")
    if unmatched_clubs:
        print(f"Clubs with no correspondance: {sorted(unmatched_clubs)}")

    match_df = pd.DataFrame(matches)
    print(f"Matched : {len(match_df)} / {len(fbref_df)} lines FBref")
    if not match_df.empty:
        low_confidence = match_df[match_df["match_score"] < 90]
        print(f"{len(low_confidence)} low confidence matchs(score < 90)")
        low_confidence.to_csv(f"{OUT_DIR}/fbref_low_confidence_matches.csv", index=False)
    return match_df


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    fbref_df = fetch_fbref_all()
    fbref_df.to_csv(f"{OUT_DIR}/fbref_raw_stats.csv", index=False)
    print(f"Raw FBref exported : {fbref_df.shape}")

    match_df = match_players(fbref_df, conn)
    match_df.to_csv(f"{OUT_DIR}/player_id_mapping.csv", index=False)

    final = fbref_df.merge(
        match_df,
        left_on=["player", "team", "season"],
        right_on=["fbref_player", "fbref_team", "season"],
        how="inner"
    )
    final.to_csv(f"{OUT_DIR}/player_season_stats_enriched.csv", index=False)
    print(f"Final export: {len(final)} lines")

    conn.close()


if __name__ == "__main__":
    main()