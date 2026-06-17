import json
import os
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = "https://api.football-data.org/v4"
TOKEN_ENV_VAR = "FOOTBALL_DATA_API_TOKEN"
DEFAULT_COMPETITION = "WC"
DEFAULT_LOOKAHEAD_DAYS = 90
COMPETITION_ENV_VAR = "FOOTBALL_DATA_COMPETITION"


class FootballDataError(Exception):
    pass


def token_is_configured():
    return bool(os.environ.get(TOKEN_ENV_VAR))


def request_json(path, params=None):
    token = os.environ.get(TOKEN_ENV_VAR)
    if not token:
        raise FootballDataError(f"Missing {TOKEN_ENV_VAR}")

    url = f"{API_BASE_URL}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"

    request = Request(url, headers={"X-Auth-Token": token})
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise FootballDataError(f"football-data.org HTTP {error.code}: {message}") from error
    except URLError as error:
        raise FootballDataError(f"football-data.org network error: {error.reason}") from error


def fetch_competition_team_ids(competition=DEFAULT_COMPETITION, season=None):
    params = {}
    if season:
        params["season"] = season

    payload = request_json(f"/competitions/{competition}/teams", params=params)
    teams = payload.get("teams", [])
    return {
        team["name"].strip().lower(): str(team["id"])
        for team in teams
        if team.get("name") and team.get("id")
    }


def fetch_team_matches(team_id, competition=DEFAULT_COMPETITION, days=DEFAULT_LOOKAHEAD_DAYS):
    today = date.today()
    params = {
        "status": "SCHEDULED",
        "dateFrom": today.isoformat(),
        "dateTo": (today + timedelta(days=days)).isoformat(),
        "limit": 10,
    }
    if competition:
        params["competitions"] = competition

    payload = request_json(f"/teams/{team_id}/matches", params=params)
    return payload.get("matches", [])


def match_to_fixture(team_name, match, venue_city_lookup):
    home_team = match.get("homeTeam", {}).get("name", "TBD")
    away_team = match.get("awayTeam", {}).get("name", "TBD")
    opponent = away_team if team_name.lower() == home_team.lower() else home_team
    venue = match.get("venue") or "TBD"

    return {
        "team": team_name,
        "opponent": opponent,
        "date": (match.get("utcDate") or "TBD").split("T")[0],
        "city": venue_city_lookup.get(venue.strip().lower(), "TBD"),
        "venue": venue,
        "competition": match.get("competition", {}).get("name", "TBD"),
        "home_away": "home" if team_name.lower() == home_team.lower() else "away",
        "source": "football-data.org",
    }


def fetch_fixtures_for_teams(team_names, venue_city_lookup, competition=DEFAULT_COMPETITION):
    competition = os.environ.get(COMPETITION_ENV_VAR, competition)
    season = os.environ.get("FOOTBALL_DATA_SEASON")
    team_ids = fetch_competition_team_ids(competition=competition, season=season)
    fixtures = []

    for team_name in sorted(set(team_names)):
        team_id = team_ids.get(team_name.strip().lower())
        if not team_id:
            continue

        matches = fetch_team_matches(team_id, competition=competition)
        fixtures.extend(
            match_to_fixture(team_name, match, venue_city_lookup)
            for match in matches
        )

    return fixtures
