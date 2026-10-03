# scripts/matching.py
"""Link FBref / Understat stat lines to Transfermarkt club and player ids."""
import unicodedata

import pandas as pd
from rapidfuzz import fuzz, process

from config import PROCESSED_DIR

CLUB_MIN_SCORE = 80
PLAYER_MIN_SCORE = 90       # accepted on the name alone
SURNAME_MIN_SCORE = 80      # accepted when the surnames also match
BIRTH_YEAR_MIN_SCORE = 75   # accepted when the birth years are identical
LOW_CONFIDENCE_SCORE = 90

STOPWORDS = {"de", "fc", "cf", "afc", "cd", "ud", "sc", "ac", "the", "club"}

# Normalized source club name -> Transfermarkt name, for names fuzzy matching gets wrong
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
    "cologne": "1.fc koln",
    "hertha berlin": "hertha bsc",
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
    "wolves": "wolverhampton wanderers",
}


def normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return name.lower().strip()


def normalize_club_name(name: str) -> str:
    tokens = [t for t in normalize_name(name).split() if t not in STOPWORDS]
    return " ".join(tokens)


def source_club_key(name: str) -> str:
    key = normalize_club_name(name)
    return normalize_club_name(CLUB_ALIASES.get(key, key))


def load_rosters(conn) -> pd.DataFrame:
    """Every (player, club, season) seen in the appearances table, plus the ones only seen
    in valuations: the Kaggle appearances miss some players (e.g. Gallagher at Palace in
    2021/22), but their valuations still record the club they were at."""
    query = """
        SELECT DISTINCT a.player_id, g.season, g.competition_id, a.player_club_id AS club_id,
               p.name AS player_name, p.date_of_birth, p.has_tm_profile, c.name AS club_name,
               'appearances' AS roster_source
        FROM appearances a
        JOIN games g ON a.game_id = g.game_id
        JOIN players p ON a.player_id = p.player_id
        JOIN clubs c ON a.player_club_id = c.club_id
        UNION
        SELECT DISTINCT v.player_id,
               CAST(strftime('%Y', v.date) AS INTEGER) - (strftime('%m', v.date) < '07') AS season,
               NULL, v.current_club_id, p.name, p.date_of_birth, p.has_tm_profile, c.name,
               'valuations'
        FROM player_valuations v
        JOIN players p ON v.player_id = p.player_id
        JOIN clubs c ON v.current_club_id = c.club_id
    """
    roster = (pd.read_sql(query, conn)
              .sort_values("roster_source")
              .drop_duplicates(["player_id", "club_id", "season"]))
    roster["name_norm"] = roster["player_name"].map(normalize_name)
    roster["club_norm"] = roster["club_name"].map(normalize_club_name)
    roster["birth_year"] = pd.to_datetime(roster["date_of_birth"]).dt.year
    return roster


def match_clubs(teams: pd.DataFrame, clubs: pd.DataFrame) -> pd.DataFrame:
    """One-to-one club matching within each (competition, season).

    teams: columns team, tm_season, competition_id.
    clubs: columns club_id, club_norm, season, competition_id.
    """
    results = []
    for (comp, season), group in teams.groupby(["competition_id", "tm_season"]):
        candidates = clubs[(clubs["competition_id"] == comp) & (clubs["season"] == season)]
        pairs = []
        for team in group["team"].unique():
            key = source_club_key(team)
            for club_id, club_norm in zip(candidates["club_id"], candidates["club_norm"]):
                score = 100 if key == club_norm else fuzz.WRatio(key, club_norm)
                pairs.append((score, team, club_id))

        # Greedy assignment, best scores first, so two teams never share a club
        assigned, used_clubs = {}, set()
        for score, team, club_id in sorted(pairs, key=lambda p: -p[0]):
            if score < CLUB_MIN_SCORE or team in assigned or club_id in used_clubs:
                continue
            assigned[team] = (club_id, score)
            used_clubs.add(club_id)

        for team in group["team"].unique():
            club_id, score = assigned.get(team, (None, None))
            results.append({"team": team, "tm_season": season, "competition_id": comp,
                            "club_id": club_id, "club_score": score})
    return pd.DataFrame(results)


def name_tokens(name: str) -> list:
    return name.replace("-", " ").split()


def share_surname(a: str, b: str) -> bool:
    """The last name of one appears in the other ("Mat Ryan" / "Mathew Ryan")."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    return (any(fuzz.ratio(ta[-1], t) >= 80 for t in tb)
            or any(fuzz.ratio(tb[-1], t) >= 80 for t in ta))


def is_same_player(name: str, cand_name: str, score: float, same_birth_year: bool) -> bool:
    if score >= PLAYER_MIN_SCORE:
        return True
    surname = share_surname(name, cand_name)
    if surname and score >= SURNAME_MIN_SCORE:
        return True
    # Nicknames and short forms ("Kostas Manolas" / "Konstantinos Manolas")
    return same_birth_year and (surname or score >= BIRTH_YEAR_MIN_SCORE)


def match_players(source: pd.DataFrame, roster: pd.DataFrame) -> pd.DataFrame:
    """Best roster player for each source row, among the clubs it was matched to.

    source: columns player, club_ids (list), tm_season, birth_year (may be NaN).
    """
    by_club_season = {key: group for key, group in roster.groupby(["club_id", "season"])}
    rows = []
    for idx, row in source.iterrows():
        candidates = pd.concat(
            [by_club_season[(c, row["tm_season"])] for c in row["club_ids"]
             if (c, row["tm_season"]) in by_club_season]
        ) if row["club_ids"] else pd.DataFrame()
        if candidates.empty:
            rows.append({"idx": idx, "status": "no_club"})
            continue

        # A birth year more than a year apart rules a candidate out
        if pd.notna(row["birth_year"]):
            gap = (candidates["birth_year"] - row["birth_year"]).abs()
            candidates = candidates[gap.isna() | (gap <= 1)]
        if candidates.empty:
            rows.append({"idx": idx, "status": "no_name_match"})
            continue

        name = normalize_name(row["player"])
        ranked = process.extract(name, candidates["name_norm"].tolist(), scorer=fuzz.WRatio,
                                 limit=None)
        match, score = candidates.iloc[ranked[0][2]], ranked[0][1]
        accepted = False
        for cand_name, cand_score, pos in ranked:
            cand = candidates.iloc[pos]
            if is_same_player(name, cand_name, cand_score, cand["birth_year"] == row["birth_year"]):
                match, score, accepted = cand, cand_score, True
                break
        rows.append({
            "idx": idx,
            "status": "ok" if accepted else "no_name_match",
            "player_id": match["player_id"],
            "club_id": match["club_id"],
            "tm_name": match["player_name"],
            "has_tm_profile": match["has_tm_profile"],
            "roster_source": match["roster_source"],
            "match_score": round(score, 1),
        })
    result = pd.DataFrame(rows).set_index("idx")

    # Two source rows on the same Transfermarkt player-club-season: keep the best one
    ok = result[result["status"] == "ok"].copy()
    ok["tm_season"] = source.loc[ok.index, "tm_season"]
    ok = ok.sort_values("match_score", ascending=False)
    losers = ok.index[ok.duplicated(["player_id", "club_id", "tm_season"])]
    result.loc[losers, "status"] = "duplicate"
    return result


def attach_tm_ids(source: pd.DataFrame, conn, label: str) -> pd.DataFrame:
    """Add player_id, club_id, match_score and status columns to source.

    source: columns player, teams (list of club names), tm_season, competition_id, birth_year.
    Writes {label}_unmatched_clubs.csv and {label}_review.csv to data/processed.
    """
    roster = load_rosters(conn)
    clubs = (roster.loc[roster["roster_source"] == "appearances",
                        ["club_id", "club_name", "club_norm", "season", "competition_id"]]
             .drop_duplicates())

    teams = (source[["teams", "tm_season", "competition_id"]].explode("teams")
             .rename(columns={"teams": "team"}).drop_duplicates())
    club_map = match_clubs(teams, clubs)
    club_map = club_map.merge(clubs[["club_id", "season", "club_name"]].drop_duplicates(),
                              left_on=["club_id", "tm_season"], right_on=["club_id", "season"], how="left")

    unmatched_clubs = club_map[club_map["club_id"].isna()]
    unmatched_clubs[["team", "tm_season", "competition_id"]].to_csv(
        PROCESSED_DIR / f"{label}_unmatched_clubs.csv", index=False)
    if not unmatched_clubs.empty:
        print(f"Clubs with no match ({len(unmatched_clubs)}), see {label}_unmatched_clubs.csv:")
        print(unmatched_clubs[["team", "tm_season", "competition_id"]].to_string(index=False))
    fuzzy = club_map[club_map["club_score"] < 100].drop_duplicates(["team", "club_name"])
    if not fuzzy.empty:
        print("Club matches that were not exact (check them):")
        for _, r in fuzzy.iterrows():
            print(f"   {r['team']!r} -> {r['club_name']!r} ({r['club_score']:.0f})")

    lookup = {(r["team"], r["tm_season"], r["competition_id"]): r["club_id"]
              for _, r in club_map.dropna(subset=["club_id"]).iterrows()}
    source = source.copy()
    source["club_ids"] = [
        [lookup[(t, s, c)] for t in teams if (t, s, c) in lookup]
        for teams, s, c in zip(source["teams"], source["tm_season"], source["competition_id"])
    ]
    matched = source.join(match_players(source, roster))

    review = matched[(matched["status"] != "ok") | (matched["match_score"] < LOW_CONFIDENCE_SCORE)]
    review[["player", "teams", "tm_season", "status", "tm_name", "player_id", "roster_source",
            "match_score"]].to_csv(
        PROCESSED_DIR / f"{label}_review.csv", index=False)

    ok = matched["status"] == "ok"
    print(f"\n{label}: matched {ok.sum()} / {len(matched)} rows ({ok.mean():.1%})")
    print(matched.groupby("tm_season")["status"].value_counts().unstack(fill_value=0).to_string())
    print(f"Matched rows whose player has a Transfermarkt profile (valuations): "
          f"{matched.loc[ok, 'has_tm_profile'].mean():.1%}")
    print(f"Matched through valuations only (missing from appearances): "
          f"{(matched.loc[ok, 'roster_source'] == 'valuations').sum()}")
    print(f"{(matched.loc[ok, 'match_score'] < LOW_CONFIDENCE_SCORE).sum()} low-confidence matches "
          f"(score < {LOW_CONFIDENCE_SCORE}), see {label}_review.csv")
    return matched


def snake_case(columns) -> list:
    out = []
    for c in columns:
        c = normalize_name(c).replace("%", "pct").replace("+/-", "plus_minus").replace("/", "_per_")
        c = "".join(ch if ch.isalnum() else "_" for ch in c)
        out.append("_".join(p for p in c.split("_") if p))
    return out


def write_stats_table(conn, table: str, df: pd.DataFrame):
    df.to_sql(table, conn, if_exists="replace", index=False)
    conn.execute(f"CREATE INDEX idx_{table}_player_season ON {table} (player_id, season)")
    conn.commit()
    print(f"{table}: {len(df)} rows written to the database")
