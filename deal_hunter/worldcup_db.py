from __future__ import annotations

import csv
import io
import os
import re
import sqlite3
import unicodedata
import zipfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "fifa2026.db"
DEFAULT_SCRAPED_ZIP = PROJECT_ROOT / "data" / "fifasprint.zip"
DEFAULT_SCOUTING_REPORT = PROJECT_ROOT / "data" / "emerging_players_scouting_report.md"
SCHEMA_VERSION = "2026-06-17-worldcup-v2"
COMPETITION = "FIFA World Cup 2026"

GROUPS: dict[str, list[str]] = {
    "A": ["Mexico", "South Africa", "Korea Republic", "Czechia"],
    "B": ["Canada", "Switzerland", "Qatar", "Bosnia and Herzegovina"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Türkiye"],
    "E": ["Germany", "Curaçao", "Côte d'Ivoire", "Ecuador"],
    "F": ["Netherlands", "Japan", "Tunisia", "Sweden"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cabo Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Norway", "Iraq"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "Uzbekistan", "Colombia", "Congo DR"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

TEAM_ALIASES: dict[str, list[str]] = {
    "Bosnia and Herzegovina": ["Bosnia", "Bosnia Herzegovina", "Bosnia-Herzegovina"],
    "Cabo Verde": ["Cape Verde"],
    "Congo DR": ["DR Congo", "Democratic Republic of Congo", "Congo Democratic Republic"],
    "Côte d'Ivoire": ["Cote d'Ivoire", "Cote dIvoire", "Ivory Coast"],
    "Curaçao": ["Curacao"],
    "Iran": ["IR Iran", "Islamic Republic of Iran"],
    "Korea Republic": ["South Korea", "Republic of Korea", "Korea", "KOR"],
    "Türkiye": ["Turkey", "Turkiye"],
    "United States": ["USA", "US", "U.S.", "United States of America", "America"],
}

VENUE_CITY: dict[str, str] = {
    "Atlanta Stadium": "Atlanta",
    "BC Place Vancouver": "Vancouver",
    "Boston Stadium": "Boston",
    "Dallas Stadium": "Dallas",
    "Estadio Guadalajara": "Guadalajara",
    "Estadio Monterrey": "Monterrey",
    "Houston Stadium": "Houston",
    "Kansas City Stadium": "Kansas City",
    "Los Angeles Stadium": "Los Angeles",
    "Mexico City Stadium": "Mexico City",
    "Miami Stadium": "Miami",
    "New York New Jersey Stadium": "New York/New Jersey",
    "Philadelphia Stadium": "Philadelphia",
    "San Francisco Bay Area Stadium": "San Francisco Bay Area",
    "Seattle Stadium": "Seattle",
    "Toronto Stadium": "Toronto",
}

FIXTURES: list[tuple[int, str, str, str, str, str, str, str]] = [
    (1, "2026-06-11", "13:00", "Mexico", "South Africa", "A", "Mexico City Stadium", "Mexico City"),
    (2, "2026-06-11", "20:00", "Korea Republic", "Czechia", "A", "Estadio Guadalajara", "Guadalajara"),
    (3, "2026-06-12", "15:00", "Canada", "Bosnia and Herzegovina", "B", "Toronto Stadium", "Toronto"),
    (4, "2026-06-12", "18:00", "United States", "Paraguay", "D", "Los Angeles Stadium", "Los Angeles"),
    (5, "2026-06-13", "21:00", "Haiti", "Scotland", "C", "Boston Stadium", "Boston"),
    (6, "2026-06-13", "21:00", "Australia", "Türkiye", "D", "BC Place Vancouver", "Vancouver"),
    (7, "2026-06-13", "18:00", "Brazil", "Morocco", "C", "New York New Jersey Stadium", "New York/New Jersey"),
    (8, "2026-06-13", "12:00", "Qatar", "Switzerland", "B", "San Francisco Bay Area Stadium", "San Francisco Bay Area"),
    (9, "2026-06-14", "19:00", "Côte d'Ivoire", "Ecuador", "E", "Philadelphia Stadium", "Philadelphia"),
    (10, "2026-06-14", "12:00", "Germany", "Curaçao", "E", "Houston Stadium", "Houston"),
    (11, "2026-06-14", "15:00", "Netherlands", "Japan", "F", "Dallas Stadium", "Dallas"),
    (12, "2026-06-14", "20:00", "Sweden", "Tunisia", "F", "Estadio Monterrey", "Monterrey"),
    (13, "2026-06-15", "18:00", "Saudi Arabia", "Uruguay", "H", "Miami Stadium", "Miami"),
    (14, "2026-06-15", "12:00", "Spain", "Cabo Verde", "H", "Atlanta Stadium", "Atlanta"),
    (15, "2026-06-15", "18:00", "Iran", "New Zealand", "G", "Los Angeles Stadium", "Los Angeles"),
    (16, "2026-06-15", "12:00", "Belgium", "Egypt", "G", "Seattle Stadium", "Seattle"),
    (17, "2026-06-16", "15:00", "France", "Senegal", "I", "New York New Jersey Stadium", "New York/New Jersey"),
    (18, "2026-06-16", "18:00", "Iraq", "Norway", "I", "Boston Stadium", "Boston"),
    (19, "2026-06-16", "20:00", "Argentina", "Algeria", "J", "Kansas City Stadium", "Kansas City"),
    (20, "2026-06-16", "21:00", "Austria", "Jordan", "J", "San Francisco Bay Area Stadium", "San Francisco Bay Area"),
    (21, "2026-06-17", "19:00", "Ghana", "Panama", "L", "Toronto Stadium", "Toronto"),
    (22, "2026-06-17", "15:00", "England", "Croatia", "L", "Dallas Stadium", "Dallas"),
    (23, "2026-06-17", "12:00", "Portugal", "Congo DR", "K", "Houston Stadium", "Houston"),
    (24, "2026-06-17", "20:00", "Uzbekistan", "Colombia", "K", "Mexico City Stadium", "Mexico City"),
    (25, "2026-06-18", "12:00", "Czechia", "South Africa", "A", "Atlanta Stadium", "Atlanta"),
    (26, "2026-06-18", "12:00", "Switzerland", "Bosnia and Herzegovina", "B", "Los Angeles Stadium", "Los Angeles"),
    (27, "2026-06-18", "15:00", "Canada", "Qatar", "B", "BC Place Vancouver", "Vancouver"),
    (28, "2026-06-18", "19:00", "Mexico", "Korea Republic", "A", "Estadio Guadalajara", "Guadalajara"),
    (29, "2026-06-19", "21:00", "Brazil", "Haiti", "C", "Philadelphia Stadium", "Philadelphia"),
    (30, "2026-06-19", "18:00", "Scotland", "Morocco", "C", "Boston Stadium", "Boston"),
    (31, "2026-06-19", "20:00", "Türkiye", "Paraguay", "D", "San Francisco Bay Area Stadium", "San Francisco Bay Area"),
    (32, "2026-06-19", "12:00", "United States", "Australia", "D", "Seattle Stadium", "Seattle"),
    (33, "2026-06-20", "16:00", "Germany", "Côte d'Ivoire", "E", "Toronto Stadium", "Toronto"),
    (34, "2026-06-20", "19:00", "Ecuador", "Curaçao", "E", "Kansas City Stadium", "Kansas City"),
    (35, "2026-06-20", "12:00", "Netherlands", "Sweden", "F", "Houston Stadium", "Houston"),
    (36, "2026-06-20", "22:00", "Tunisia", "Japan", "F", "Estadio Monterrey", "Monterrey"),
    (37, "2026-06-21", "18:00", "Uruguay", "Cabo Verde", "H", "Miami Stadium", "Miami"),
    (38, "2026-06-21", "12:00", "Spain", "Saudi Arabia", "H", "Atlanta Stadium", "Atlanta"),
    (39, "2026-06-21", "12:00", "Belgium", "Iran", "G", "Los Angeles Stadium", "Los Angeles"),
    (40, "2026-06-21", "18:00", "New Zealand", "Egypt", "G", "BC Place Vancouver", "Vancouver"),
    (41, "2026-06-22", "20:00", "Norway", "Senegal", "I", "New York New Jersey Stadium", "New York/New Jersey"),
    (42, "2026-06-22", "17:00", "France", "Iraq", "I", "Philadelphia Stadium", "Philadelphia"),
    (43, "2026-06-22", "12:00", "Argentina", "Austria", "J", "Dallas Stadium", "Dallas"),
    (44, "2026-06-22", "20:00", "Jordan", "Algeria", "J", "San Francisco Bay Area Stadium", "San Francisco Bay Area"),
    (45, "2026-06-23", "16:00", "England", "Ghana", "L", "Boston Stadium", "Boston"),
    (46, "2026-06-23", "19:00", "Panama", "Croatia", "L", "Toronto Stadium", "Toronto"),
    (47, "2026-06-23", "12:00", "Portugal", "Uzbekistan", "K", "Houston Stadium", "Houston"),
    (48, "2026-06-23", "20:00", "Colombia", "Congo DR", "K", "Estadio Guadalajara", "Guadalajara"),
    (49, "2026-06-24", "18:00", "Scotland", "Brazil", "C", "Miami Stadium", "Miami"),
    (50, "2026-06-24", "18:00", "Morocco", "Haiti", "C", "Atlanta Stadium", "Atlanta"),
    (51, "2026-06-24", "12:00", "Switzerland", "Canada", "B", "BC Place Vancouver", "Vancouver"),
    (52, "2026-06-24", "12:00", "Bosnia and Herzegovina", "Qatar", "B", "Seattle Stadium", "Seattle"),
    (53, "2026-06-24", "19:00", "Czechia", "Mexico", "A", "Mexico City Stadium", "Mexico City"),
    (54, "2026-06-24", "19:00", "South Africa", "Korea Republic", "A", "Estadio Monterrey", "Monterrey"),
    (55, "2026-06-25", "16:00", "Curaçao", "Côte d'Ivoire", "E", "Philadelphia Stadium", "Philadelphia"),
    (56, "2026-06-25", "16:00", "Ecuador", "Germany", "E", "New York New Jersey Stadium", "New York/New Jersey"),
    (57, "2026-06-25", "18:00", "Japan", "Sweden", "F", "Dallas Stadium", "Dallas"),
    (58, "2026-06-25", "18:00", "Tunisia", "Netherlands", "F", "Kansas City Stadium", "Kansas City"),
    (59, "2026-06-25", "19:00", "Türkiye", "United States", "D", "Los Angeles Stadium", "Los Angeles"),
    (60, "2026-06-25", "19:00", "Paraguay", "Australia", "D", "San Francisco Bay Area Stadium", "San Francisco Bay Area"),
    (61, "2026-06-26", "15:00", "Norway", "France", "I", "Boston Stadium", "Boston"),
    (62, "2026-06-26", "15:00", "Senegal", "Iraq", "I", "Toronto Stadium", "Toronto"),
    (63, "2026-06-26", "20:00", "Egypt", "Iran", "G", "Seattle Stadium", "Seattle"),
    (64, "2026-06-26", "20:00", "New Zealand", "Belgium", "G", "BC Place Vancouver", "Vancouver"),
    (65, "2026-06-26", "19:00", "Cabo Verde", "Saudi Arabia", "H", "Houston Stadium", "Houston"),
    (66, "2026-06-26", "18:00", "Uruguay", "Spain", "H", "Estadio Guadalajara", "Guadalajara"),
    (67, "2026-06-27", "17:00", "Panama", "England", "L", "New York New Jersey Stadium", "New York/New Jersey"),
    (68, "2026-06-27", "17:00", "Croatia", "Ghana", "L", "Philadelphia Stadium", "Philadelphia"),
    (69, "2026-06-27", "21:00", "Algeria", "Austria", "J", "Kansas City Stadium", "Kansas City"),
    (70, "2026-06-27", "21:00", "Jordan", "Argentina", "J", "Dallas Stadium", "Dallas"),
    (71, "2026-06-27", "19:30", "Colombia", "Portugal", "K", "Miami Stadium", "Miami"),
    (72, "2026-06-27", "19:30", "Congo DR", "Uzbekistan", "K", "Atlanta Stadium", "Atlanta"),
]


def ensure_world_cup_database() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        if is_current(conn):
            return DB_PATH
        rebuild(conn)
    return DB_PATH


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_teams() -> list[dict[str, Any]]:
    ensure_world_cup_database()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, group_name
            FROM teams
            ORDER BY group_name, name
            """
        ).fetchall()
    return [
        {"code": row["id"], "name": row["name"], "group": row["group_name"]}
        for row in rows
    ]


def build_schedule_payload(query: str | None, *, limit: int | None = None) -> dict[str, Any]:
    ensure_world_cup_database()
    with connect() as conn:
        team = resolve_team(conn, query or "United States")
        player_matches = search_scouting_identity_reports(conn, query or "")
        if team is None and player_matches:
            player_team = player_matches[0]["watch_team"]
            if player_team and player_team.upper() != "TBD":
                team = resolve_team(conn, player_team)
        if team:
            fixtures = fixture_rows_for_team(conn, team["id"])
            return {
                "country": {
                    "code": team["id"],
                    "name": team["name"],
                    "group": team["group_name"],
                    "is_all": False,
                },
                "matches": [serialize_fixture(row, team_id=team["id"], priority=5 - index) for index, row in enumerate(fixtures)],
                "scouting": scouting_for_response(
                    conn,
                    query=query or team["name"],
                    team_id=team["id"],
                ),
                "source": source_payload(),
            }

        fixture_query = "" if is_general_query(query) else query or ""
        fixtures = search_fixture_rows(conn, fixture_query, limit=limit or len(FIXTURES))
        if not fixtures:
            fixtures = search_fixture_rows(conn, "", limit=limit or len(FIXTURES))
        return {
            "country": {
                "code": "all",
                "name": "All FIFA World Cup 2026 teams",
                "group": "All groups",
                "is_all": True,
            },
            "matches": [serialize_fixture(row, priority=3) for row in fixtures],
            "scouting": scouting_for_response(conn, query=query or ""),
            "source": source_payload(),
        }


def get_plan_matches(query: str, match_ids: list[str], *, max_matches: int = 4) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = build_schedule_payload(query, limit=len(FIXTURES))
    matches = payload["matches"]
    if match_ids:
        requested = set(match_ids)
        selected = [match for match in matches if match["id"] in requested]
    else:
        selected = matches
    if payload["country"]["code"] == "all" and not match_ids:
        selected = selected[:3]
    return payload["country"], selected[:max_matches] or matches[: min(3, len(matches))]


def source_payload() -> dict[str, str]:
    return {
        "database": str(DB_PATH),
        "scraped_zip": str(scraped_zip_path()),
        "scouting_report": str(DEFAULT_SCOUTING_REPORT),
        "complete_schedule": "FIFA World Cup 2026 group-stage schedule snapshot",
    }


def is_current(conn: sqlite3.Connection) -> bool:
    try:
        version = conn.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
        fixtures = conn.execute("SELECT COUNT(*) AS count FROM fixtures").fetchone()
        teams = conn.execute("SELECT COUNT(*) AS count FROM teams").fetchone()
        reports = conn.execute("SELECT COUNT(*) AS count FROM scouting_reports").fetchone()
    except sqlite3.Error:
        return False
    return (
        version is not None
        and version["value"] == SCHEMA_VERSION
        and fixtures is not None
        and fixtures["count"] == len(FIXTURES)
        and teams is not None
        and teams["count"] == sum(len(teams) for teams in GROUPS.values())
        and reports is not None
        and reports["count"] >= 12
    )


def rebuild(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS metadata;
        DROP TABLE IF EXISTS aliases;
        DROP TABLE IF EXISTS scouting_reports;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS scraped_fixtures;
        DROP TABLE IF EXISTS fixtures;
        DROP TABLE IF EXISTS teams;
        DROP TABLE IF EXISTS venues;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            normalized_name TEXT NOT NULL,
            group_name TEXT NOT NULL
        );

        CREATE TABLE aliases (
            alias TEXT PRIMARY KEY,
            team_id TEXT NOT NULL REFERENCES teams(id)
        );

        CREATE TABLE venues (
            venue TEXT PRIMARY KEY,
            city TEXT NOT NULL,
            source TEXT NOT NULL
        );

        CREATE TABLE fixtures (
            id TEXT PRIMARY KEY,
            match_number INTEGER NOT NULL UNIQUE,
            match_date TEXT NOT NULL,
            local_time TEXT NOT NULL,
            team_a_id TEXT NOT NULL REFERENCES teams(id),
            team_b_id TEXT NOT NULL REFERENCES teams(id),
            group_name TEXT NOT NULL,
            venue TEXT NOT NULL,
            city TEXT NOT NULL,
            competition TEXT NOT NULL,
            source TEXT NOT NULL,
            scraped_source INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE scraped_fixtures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team TEXT NOT NULL,
            opponent TEXT NOT NULL,
            match_date TEXT NOT NULL,
            city TEXT NOT NULL,
            venue TEXT NOT NULL,
            competition TEXT NOT NULL,
            home_away TEXT,
            source TEXT
        );

        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            club TEXT,
            country TEXT,
            position TEXT,
            minutes_trend REAL,
            goals_per_90 REAL,
            assists_per_90 REAL,
            prog_actions_per_90 REAL,
            national_team_exposure TEXT,
            tournament_visibility TEXT,
            contract_months_left INTEGER,
            next_game_date TEXT,
            next_game_city TEXT
        );

        CREATE TABLE scouting_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            age INTEGER,
            club TEXT,
            country TEXT,
            position TEXT,
            emergence_score INTEGER,
            book_flight_to TEXT,
            travel_date TEXT,
            watch_team TEXT,
            watch_team_id TEXT,
            next_opponent TEXT,
            next_game_venue TEXT,
            competition TEXT,
            fixture_source TEXT,
            why_emerging TEXT,
            risk_factors TEXT,
            watch_next TEXT,
            source TEXT NOT NULL
        );

        CREATE INDEX idx_aliases_team ON aliases(team_id);
        CREATE INDEX idx_fixtures_team_a ON fixtures(team_a_id);
        CREATE INDEX idx_fixtures_team_b ON fixtures(team_b_id);
        CREATE INDEX idx_fixtures_date ON fixtures(match_date, local_time);
        CREATE INDEX idx_scouting_watch_team ON scouting_reports(watch_team_id);
        CREATE INDEX idx_scouting_score ON scouting_reports(emergence_score DESC);
        """
    )
    seed_metadata(conn)
    seed_teams(conn)
    seed_venues(conn)
    seed_fixtures(conn)
    import_scraped_zip(conn, scraped_zip_path())
    import_scouting_report(conn, DEFAULT_SCOUTING_REPORT)
    conn.commit()


def seed_metadata(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        ("schema_version", SCHEMA_VERSION),
    )
    conn.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        ("scraped_zip", str(scraped_zip_path())),
    )
    conn.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        ("scouting_report", str(DEFAULT_SCOUTING_REPORT)),
    )


def seed_teams(conn: sqlite3.Connection) -> None:
    for group_name, teams in GROUPS.items():
        for team in teams:
            team_id = slug(team)
            conn.execute(
                """
                INSERT INTO teams (id, name, normalized_name, group_name)
                VALUES (?, ?, ?, ?)
                """,
                (team_id, team, normalize_text(team), group_name),
            )
            aliases = {team, team_id, normalize_text(team), *TEAM_ALIASES.get(team, [])}
            for alias in aliases:
                normalized = normalize_text(alias)
                if normalized:
                    conn.execute(
                        "INSERT OR REPLACE INTO aliases (alias, team_id) VALUES (?, ?)",
                        (normalized, team_id),
                    )


def seed_venues(conn: sqlite3.Connection) -> None:
    for venue, city in VENUE_CITY.items():
        conn.execute(
            "INSERT INTO venues (venue, city, source) VALUES (?, ?, ?)",
            (venue, city, "complete_schedule"),
        )


def seed_fixtures(conn: sqlite3.Connection) -> None:
    for match_number, match_date, local_time, team_a, team_b, group_name, venue, city in FIXTURES:
        conn.execute(
            """
            INSERT INTO fixtures (
                id, match_number, match_date, local_time, team_a_id, team_b_id,
                group_name, venue, city, competition, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"m{match_number:03d}",
                match_number,
                match_date,
                local_time,
                slug(team_a),
                slug(team_b),
                group_name,
                venue,
                city,
                COMPETITION,
                "complete_schedule",
            ),
        )


def import_scraped_zip(conn: sqlite3.Connection, zip_path: Path) -> None:
    if not zip_path.exists():
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            ("scraped_zip_status", "missing"),
        )
        return

    with zipfile.ZipFile(zip_path) as archive:
        import_scraped_venues(conn, archive)
        import_scraped_fixtures(conn, archive)
        import_scraped_players(conn, archive)

    conn.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        ("scraped_zip_status", "imported"),
    )


def import_scraped_venues(conn: sqlite3.Connection, archive: zipfile.ZipFile) -> None:
    for row in read_csv_from_zip(archive, "fifasprint/venues.csv"):
        venue = row.get("venue", "").strip()
        city = row.get("city", "").strip()
        if not venue or not city:
            continue
        conn.execute(
            """
            INSERT INTO venues (venue, city, source)
            VALUES (?, ?, ?)
            ON CONFLICT(venue) DO UPDATE SET city = excluded.city, source = 'fifasprint.zip'
            """,
            (venue, city, "fifasprint.zip"),
        )


def import_scraped_fixtures(conn: sqlite3.Connection, archive: zipfile.ZipFile) -> None:
    for row in read_csv_from_zip(archive, "fifasprint/fixtures.csv"):
        team = row.get("team", "").strip()
        opponent = row.get("opponent", "").strip()
        match_date = row.get("date", "").strip()
        if not team or not opponent or not match_date:
            continue
        conn.execute(
            """
            INSERT INTO scraped_fixtures (
                team, opponent, match_date, city, venue, competition, home_away, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                team,
                opponent,
                match_date,
                row.get("city", "").strip(),
                row.get("venue", "").strip(),
                row.get("competition", "").strip(),
                row.get("home_away", "").strip(),
                row.get("source", "").strip(),
            ),
        )
        team_id = team_id_from_name(team)
        opponent_id = team_id_from_name(opponent)
        if team_id and opponent_id:
            conn.execute(
                """
                UPDATE fixtures
                SET scraped_source = 1
                WHERE match_date = ?
                  AND (
                    (team_a_id = ? AND team_b_id = ?)
                    OR (team_a_id = ? AND team_b_id = ?)
                  )
                """,
                (match_date, team_id, opponent_id, opponent_id, team_id),
            )


def import_scraped_players(conn: sqlite3.Connection, archive: zipfile.ZipFile) -> None:
    for row in read_csv_from_zip(archive, "fifasprint/players.csv"):
        name = row.get("name", "").strip()
        if not name:
            continue
        conn.execute(
            """
            INSERT INTO players (
                name, age, club, country, position, minutes_trend, goals_per_90,
                assists_per_90, prog_actions_per_90, national_team_exposure,
                tournament_visibility, contract_months_left, next_game_date, next_game_city
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                int_or_none(row.get("age")),
                row.get("club", "").strip(),
                row.get("country", "").strip(),
                row.get("position", "").strip(),
                float_or_none(row.get("minutes_trend")),
                float_or_none(row.get("goals_per_90")),
                float_or_none(row.get("assists_per_90")),
                float_or_none(row.get("prog_actions_per_90")),
                row.get("national_team_exposure", "").strip(),
                row.get("tournament_visibility", "").strip(),
                int_or_none(row.get("contract_months_left")),
                row.get("next_game_date", "").strip(),
                row.get("next_game_city", "").strip(),
            ),
        )


def import_scouting_report(conn: sqlite3.Connection, report_path: Path) -> None:
    if not report_path.exists():
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            ("scouting_report_status", "missing"),
        )
        return

    reports = parse_scouting_report(report_path.read_text(encoding="utf-8"))
    for report in reports:
        name = report.get("name", "")
        if not name:
            continue
        watch_team = report.get("Watch team", "")
        conn.execute(
            """
            INSERT INTO scouting_reports (
                name, normalized_name, age, club, country, position, emergence_score,
                book_flight_to, travel_date, watch_team, watch_team_id, next_opponent,
                next_game_venue, competition, fixture_source, why_emerging, risk_factors,
                watch_next, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                normalize_text(name),
                int_or_none(report.get("Age")),
                report.get("Club", ""),
                report.get("Country", ""),
                report.get("Position", ""),
                int_or_none(report.get("Emergence score")),
                report.get("Book flight to", ""),
                empty_tbd_to_none(report.get("Travel date")),
                watch_team,
                team_id_from_name(watch_team) or "",
                report.get("Next opponent", ""),
                report.get("Next game venue", ""),
                report.get("Competition", ""),
                report.get("Fixture source", ""),
                report.get("Why emerging", ""),
                report.get("Risk factors", ""),
                report.get("Watch next", ""),
                "emerging_players_scouting_report.md",
            ),
        )

    conn.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        ("scouting_report_status", "imported"),
    )


def parse_scouting_report(text: str) -> list[dict[str, str]]:
    reports: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    active_list_key: str | None = None
    list_values: dict[str, list[str]] = {}
    list_keys = {"Why emerging", "Risk factors", "Watch next"}

    def flush() -> None:
        nonlocal current, list_values, active_list_key
        if current is None:
            return
        for key, values in list_values.items():
            current[key] = " ".join(values).strip()
        reports.append(current)
        current = None
        active_list_key = None
        list_values = {}

    for raw_line in text.splitlines():
        line = repair_text(raw_line).strip()
        if not line:
            continue
        if line.startswith("## "):
            flush()
            current = {"name": line[3:].strip()}
            continue
        if current is None:
            continue
        if line.endswith(":") and line[:-1] in list_keys:
            active_list_key = line[:-1]
            list_values.setdefault(active_list_key, [])
            continue
        if active_list_key and line.startswith("- "):
            list_values.setdefault(active_list_key, []).append(line[2:].strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current[key.strip()] = value.strip()
            active_list_key = None

    flush()
    return reports


def read_csv_from_zip(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    try:
        with archive.open(name) as file:
            text = io.TextIOWrapper(file, encoding="utf-8-sig")
            return list(csv.DictReader(text))
    except KeyError:
        return []


def resolve_team(conn: sqlite3.Connection, query: str | None) -> sqlite3.Row | None:
    normalized = normalize_text(query or "")
    if not normalized or is_general_query(query):
        return None

    aliases = conn.execute(
        """
        SELECT aliases.alias, teams.id, teams.name, teams.group_name
        FROM aliases
        JOIN teams ON teams.id = aliases.team_id
        ORDER BY LENGTH(aliases.alias) DESC
        """
    ).fetchall()
    padded = f" {normalized} "
    for row in aliases:
        alias = row["alias"]
        if normalized == alias or f" {alias} " in padded or (len(alias) > 3 and alias in normalized):
            return row

    best = fuzzy_alias(normalized, [row["alias"] for row in aliases])
    if best:
        for row in aliases:
            if row["alias"] == best:
                return row
    return None


def fixture_rows_for_team(conn: sqlite3.Connection, team_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT fixtures.*, ta.name AS team_a, tb.name AS team_b
        FROM fixtures
        JOIN teams ta ON ta.id = fixtures.team_a_id
        JOIN teams tb ON tb.id = fixtures.team_b_id
        WHERE team_a_id = ? OR team_b_id = ?
        ORDER BY match_number
        """,
        (team_id, team_id),
    ).fetchall()


def search_fixture_rows(conn: sqlite3.Connection, query: str, *, limit: int) -> list[sqlite3.Row]:
    normalized = normalize_text(query)
    rows = conn.execute(
        """
        SELECT fixtures.*, ta.name AS team_a, tb.name AS team_b
        FROM fixtures
        JOIN teams ta ON ta.id = fixtures.team_a_id
        JOIN teams tb ON tb.id = fixtures.team_b_id
        ORDER BY match_number
        """
    ).fetchall()
    if not normalized:
        return rows[:limit]
    terms = normalized.split()
    matched = [
        row
        for row in rows
        if all(term in fixture_search_text(row) for term in terms)
    ]
    return matched[:limit]


def scouting_for_response(
    conn: sqlite3.Connection,
    *,
    query: str,
    team_id: str | None = None,
) -> list[dict[str, Any]]:
    reports = search_scouting_reports(conn, query, team_id=team_id)
    if team_id and not reports:
        reports = search_scouting_reports(conn, "", team_id=team_id)
    return [serialize_scouting_report(row) for row in reports[:6]]


def search_scouting_reports(
    conn: sqlite3.Connection,
    query: str,
    *,
    team_id: str | None = None,
    limit: int = 12,
) -> list[sqlite3.Row]:
    normalized = normalize_text(query)
    rows = conn.execute(
        """
        SELECT *
        FROM scouting_reports
        ORDER BY emergence_score DESC, name
        """
    ).fetchall()
    if team_id:
        rows = [row for row in rows if row["watch_team_id"] == team_id]
    if not normalized or is_general_query(query):
        return rows[:limit]

    terms = normalized.split()
    matched = [
        row
        for row in rows
        if all(term in scouting_search_text(row) for term in terms)
    ]
    return matched[:limit]


def search_scouting_identity_reports(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 6,
) -> list[sqlite3.Row]:
    normalized = normalize_text(query)
    if not normalized or is_general_query(query):
        return []
    rows = conn.execute(
        """
        SELECT *
        FROM scouting_reports
        ORDER BY emergence_score DESC, name
        """
    ).fetchall()
    terms = normalized.split()
    return [
        row
        for row in rows
        if all(term in scouting_identity_text(row) for term in terms)
    ][:limit]


def serialize_fixture(
    row: sqlite3.Row,
    *,
    team_id: str | None = None,
    priority: int = 3,
) -> dict[str, Any]:
    team_a = row["team_a"]
    team_b = row["team_b"]
    selected_team = None
    opponent = None
    if team_id:
        if row["team_a_id"] == team_id:
            selected_team, opponent = team_a, team_b
        elif row["team_b_id"] == team_id:
            selected_team, opponent = team_b, team_a
    return {
        "id": row["id"],
        "match_number": row["match_number"],
        "event_name": f"{team_a} vs {team_b}",
        "team": selected_team or team_a,
        "opponent": opponent or team_b,
        "home_team": team_a,
        "away_team": team_b,
        "city": row["city"],
        "venue": row["venue"],
        "date": f"{row['match_date']}T{row['local_time']}:00",
        "local_time": row["local_time"],
        "group": row["group_name"],
        "competition": row["competition"],
        "priority": max(1, priority),
        "source": "fifasprint.zip" if row["scraped_source"] else row["source"],
    }


def serialize_scouting_report(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "name": row["name"],
        "age": row["age"],
        "club": row["club"],
        "country": row["country"],
        "position": row["position"],
        "emergence_score": row["emergence_score"],
        "book_flight_to": row["book_flight_to"],
        "travel_date": row["travel_date"],
        "watch_team": row["watch_team"],
        "watch_team_id": row["watch_team_id"],
        "next_opponent": row["next_opponent"],
        "next_game_venue": row["next_game_venue"],
        "competition": row["competition"],
        "fixture_source": row["fixture_source"],
        "why_emerging": row["why_emerging"],
        "risk_factors": row["risk_factors"],
        "watch_next": row["watch_next"],
        "source": row["source"],
    }


def fixture_search_text(row: sqlite3.Row) -> str:
    return normalize_text(
        " ".join(
            [
                row["team_a"],
                row["team_b"],
                row["city"],
                row["venue"],
                row["group_name"],
                row["competition"],
            ]
        )
    )


def scouting_search_text(row: sqlite3.Row) -> str:
    return normalize_text(
        " ".join(
            [
                row["name"] or "",
                row["club"] or "",
                row["country"] or "",
                row["position"] or "",
                row["book_flight_to"] or "",
                row["watch_team"] or "",
                row["next_opponent"] or "",
                row["next_game_venue"] or "",
                row["competition"] or "",
                row["why_emerging"] or "",
                row["watch_next"] or "",
            ]
        )
    )


def scouting_identity_text(row: sqlite3.Row) -> str:
    return normalize_text(
        " ".join(
            [
                row["name"] or "",
                row["club"] or "",
                row["country"] or "",
                row["position"] or "",
                row["watch_team"] or "",
            ]
        )
    )


def team_id_from_name(name: str) -> str | None:
    normalized = normalize_text(name)
    for teams in GROUPS.values():
        for team in teams:
            candidates = {normalize_text(team), *[normalize_text(alias) for alias in TEAM_ALIASES.get(team, [])]}
            if normalized in candidates:
                return slug(team)
    return None


def fuzzy_alias(query: str, aliases: list[str]) -> str | None:
    if len(query) < 4:
        return None
    best_alias = None
    best_score = 0.0
    query_tokens = set(query.split())
    for alias in aliases:
        alias_tokens = set(alias.split())
        overlap = len(query_tokens & alias_tokens)
        denominator = max(len(query_tokens | alias_tokens), 1)
        score = overlap / denominator
        if score > best_score:
            best_score = score
            best_alias = alias
    return best_alias if best_score >= 0.5 else None


def scraped_zip_path() -> Path:
    return Path(os.environ.get("FIFASPRINT_ZIP", str(DEFAULT_SCRAPED_ZIP)))


def is_general_query(query: str | None) -> bool:
    normalized = normalize_text(query or "")
    return normalized in {"all", "world cup", "fifa", "fifa 2026", "all teams"}


def normalize_text(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


def repair_text(value: str) -> str:
    if "Ã" not in value and "Â" not in value:
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value


def empty_tbd_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return None if not stripped or stripped.upper() == "TBD" else stripped


def slug(value: str) -> str:
    return normalize_text(value).replace(" ", "-")


def int_or_none(value: str | None) -> int | None:
    if value in {None, ""}:
        return None
    return int(float(value))


def float_or_none(value: str | None) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)
