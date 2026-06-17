# Football Fixture Data Sources

FIFA.com has an official scores and fixtures page, but it is a web product rather than a clearly documented public API. Use it as the canonical human reference for FIFA tournaments, not as the first integration target.

Selected option:

1. football-data.org as the primary live provider.
   - Best current fit for this app because we mostly need team fixtures.
   - Useful endpoint shape: `/v4/teams/{id}/matches`.
   - Returns match date, teams, competition, and venue.
   - The agent uses `FOOTBALL_DATA_API_TOKEN` to enable this provider.

Fallback/supporting data:

1. `fixtures.csv` for the offline prototype and fallback.
   - Small, reliable, easy to inspect.
   - Columns match what the travel app needs: `team`, `opponent`, `date`, `city`, `venue`, and `competition`.

2. `venues.csv` for venue-to-city mapping.
   - Needed because football APIs often return stadium names without a separate city field.
   - The travel app needs the city.

Other options considered:

1. API-Football/API-Sports for broader paid coverage.
   - Better if we need player squads, lineups, injuries, league fixtures, and richer venue metadata.

2. TheSportsDB for a lightweight/free option.
   - Useful for early experiments and broad event/team lookups.
   - Verify coverage before relying on it for World Cup travel planning.

The next implementation step is to add player-to-national-team validation from a richer squad source. For now, the agent assumes the `country` field in `players.csv` is the watch team for FIFA tournament travel.
