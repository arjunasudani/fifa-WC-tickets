import csv
from datetime import date
from datetime import datetime
from math import floor
from pathlib import Path

from football_data_client import FootballDataError
from football_data_client import fetch_fixtures_for_teams
from football_data_client import token_is_configured

INPUT_FILE = Path("players.csv")
FIXTURES_FILE = Path("fixtures.csv")
LIVE_FIXTURES_FILE = Path("fixtures_live.csv")
VENUES_FILE = Path("venues.csv")
REPORT_FILE = Path("emerging_players_report.md")

EXPOSURE_SCORE = {
    "None": 0,
    "U21": 10,
    "Senior": 20,
}

VISIBILITY_SCORE = {
    "None": 0,
    "Youth": 5,
    "Euro": 15,
    "WorldCup": 20,
    "Copa": 15,
}


def parse_float(value, default=0.0):
    try:
        return float(value)
    except ValueError:
        return default


def parse_int(value, default=0):
    try:
        return int(value)
    except ValueError:
        return default


def normalize(value, min_value, max_value):
    if value <= min_value:
        return 0.0
    if value >= max_value:
        return 1.0
    return (value - min_value) / (max_value - min_value)


def score_player(player):
    age = parse_int(player["age"])
    minutes_trend = parse_float(player["minutes_trend"])
    goals = parse_float(player["goals_per_90"])
    assists = parse_float(player["assists_per_90"])
    prog_actions = parse_float(player["prog_actions_per_90"])
    exposure = EXPOSURE_SCORE.get(player["national_team_exposure"], 0)
    visibility = VISIBILITY_SCORE.get(player["tournament_visibility"], 0)
    months_left = parse_int(player["contract_months_left"])

    age_score = max(0, min(25, 24 - age)) * 2
    minutes_score = normalize(minutes_trend, -5.0, 30.0) * 18
    goals_score = normalize(goals, 0.0, 0.6) * 20
    assists_score = normalize(assists, 0.0, 0.4) * 15
    prog_score = normalize(prog_actions, 0.5, 3.5) * 15
    exposure_score = min(exposure, 20)
    visibility_score = min(visibility, 20)
    contract_score = 10 if months_left <= 24 else 0

    raw_score = (
        age_score
        + minutes_score
        + goals_score
        + assists_score
        + prog_score
        + exposure_score
        + visibility_score
        + contract_score
    )

    score = min(100, max(0, floor(raw_score)))
    return score


def load_players(filepath):
    with open(filepath, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        return [row for row in reader]


def load_fixtures(filepath):
    if not filepath.exists():
        return []

    with open(filepath, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        return [row for row in reader]


def load_venue_city_lookup(filepath):
    if not filepath.exists():
        return {}

    with open(filepath, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        return {
            row["venue"].strip().lower(): row["city"].strip()
            for row in reader
            if row.get("venue") and row.get("city")
        }


def save_fixtures(fixtures, filepath):
    fieldnames = [
        "team",
        "opponent",
        "date",
        "city",
        "venue",
        "competition",
        "home_away",
        "source",
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for fixture in fixtures:
            writer.writerow({field: fixture.get(field, "") for field in fieldnames})


def merge_live_and_fallback_fixtures(live_fixtures, fallback_fixtures):
    live_teams = {
        fixture["team"].strip().lower()
        for fixture in live_fixtures
        if fixture.get("team")
    }
    fallback_for_missing_teams = [
        fixture
        for fixture in fallback_fixtures
        if fixture.get("team", "").strip().lower() not in live_teams
    ]
    return live_fixtures + fallback_for_missing_teams


def fixture_sort_date(fixture):
    try:
        return datetime.strptime(fixture["date"], "%Y-%m-%d").date()
    except (KeyError, TypeError, ValueError):
        return date.max


def is_upcoming_fixture(fixture):
    fixture_date = fixture_sort_date(fixture)
    return fixture_date >= date.today()


def load_best_available_fixtures(players):
    venue_city_lookup = load_venue_city_lookup(VENUES_FILE)
    team_names = [player["country"] for player in players]
    fallback_fixtures = load_fixtures(FIXTURES_FILE)

    if token_is_configured():
        try:
            live_fixtures = fetch_fixtures_for_teams(team_names, venue_city_lookup)
            if live_fixtures:
                save_fixtures(live_fixtures, LIVE_FIXTURES_FILE)
                fixtures = merge_live_and_fallback_fixtures(live_fixtures, fallback_fixtures)
                return fixtures, "football-data.org + fixtures.csv fallback"
            print("football-data.org returned no fixtures; using fixtures.csv fallback.")
        except FootballDataError as error:
            print(f"Could not load football-data.org fixtures: {error}")
            print("Using fixtures.csv fallback.")

    return fallback_fixtures, "fixtures.csv"


def find_next_fixture(player, fixtures):
    team_names = [player["country"], player["club"]]

    for team_name in team_names:
        team_fixtures = [
            fixture
            for fixture in fixtures
            if fixture["team"].strip().lower() == team_name.strip().lower()
            and is_upcoming_fixture(fixture)
        ]
        if team_fixtures:
            return sorted(team_fixtures, key=fixture_sort_date)[0]

    return None


def attach_next_fixtures(players, fixtures):
    for player in players:
        fixture = find_next_fixture(player, fixtures)
        if fixture:
            player["next_game_date"] = fixture["date"]
            player["next_game_city"] = fixture["city"]
            player["next_game_venue"] = fixture["venue"]
            player["next_game_opponent"] = fixture["opponent"]
            player["next_game_competition"] = fixture["competition"]
            player["next_game_team"] = fixture["team"]
            player["next_game_source"] = fixture.get("source", "fixtures.csv")
        else:
            player["next_game_date"] = "TBD"
            player["next_game_city"] = "TBD"
            player["next_game_venue"] = "TBD"
            player["next_game_opponent"] = "TBD"
            player["next_game_competition"] = "TBD"
            player["next_game_team"] = "TBD"
            player["next_game_source"] = "none"


def render_table(players):
    headers = ["Rank", "Player", "Age", "Book Flight To", "Game Date", "Team", "Score"]
    rows = []
    for index, player in enumerate(players, start=1):
        rows.append(
            [
                str(index),
                player["name"],
                player["age"],
                player["next_game_city"],
                player["next_game_date"],
                player["next_game_team"],
                str(player["score"]),
            ]
        )

    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)]
    lines = []
    lines.append(" | ".join(header.ljust(widths[i]) for i, header in enumerate(headers)))
    lines.append("-|-".join("-" * width for width in widths))
    for row in rows:
        lines.append(" | ".join(row[i].ljust(widths[i]) for i in range(len(row))))
    return "\n".join(lines)


def generate_report(players, filepath):
    lines = ["# Emerging Players Scouting Report\n"]
    for player in players:
        lines.extend(
            [
                f"## {player['name']}",
                f"- Age: {player['age']}",
                f"- Club: {player['club']}",
                f"- Country: {player['country']}",
                f"- Position: {player['position']}",
                f"- Emergence score: {player['score']}",
                f"- Book flight to: {player.get('next_game_city', 'TBD')}",
                f"- Travel date: {player.get('next_game_date', 'TBD')}",
                f"- Watch team: {player['next_game_team']}",
                f"- Next opponent: {player['next_game_opponent']}",
                f"- Next game venue: {player.get('next_game_venue', 'TBD')}",
                f"- Competition: {player.get('next_game_competition', 'TBD')}",
                f"- Fixture source: {player.get('next_game_source', 'TBD')}",
                "- Why emerging:",
                f"  - Consistent minutes growth and strong progressions make {player['name']} a rising talent.",
                "- Risk factors:",
                f"  - Age, contract timing, and competition for first-team spots should be monitored.",
                "- Watch next:",
                f"  - Book toward {player.get('next_game_city', 'TBD')} for {player['next_game_team']} vs {player['next_game_opponent']}.\n",
            ]
        )
    content = "\n".join(lines)
    filepath.write_text(content, encoding="utf-8")


def main():
    if not INPUT_FILE.exists():
        print(f"Missing input file: {INPUT_FILE}")
        return

    players = load_players(INPUT_FILE)
    fixtures, fixture_source = load_best_available_fixtures(players)
    for player in players:
        player["score"] = score_player(player)

    attach_next_fixtures(players, fixtures)
    players.sort(key=lambda item: item["score"], reverse=True)

    print("Emerging Players Rankings")
    print("=========================")
    print(f"Fixture source: {fixture_source}\n")
    print(render_table(players))
    print(f"\nGenerating report: {REPORT_FILE}\n")
    generate_report(players, REPORT_FILE)


if __name__ == "__main__":
    main()
