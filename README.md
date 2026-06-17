# FIFA World Cup 2026 Ticket and Travel Deal Hunter

This repository contains an MVP for planning FIFA World Cup 2026 travel around match schedules, venue cities, emerging-player scouting context, ticket estimates, flights, and hotels.

The app has two layers:

- A Python backend that builds and serves a small SQLite database, creates route plans, seeds demo ticket/flight/hotel candidates, and optimizes itineraries.
- A React + Vite frontend that uses the prompt-box UI, lets users search teams, players, venues, or cities, and shows match dates, opponents, venues, scouting cards, and travel-plan estimates.

## Current MVP Status

- Search works for all 48 FIFA World Cup 2026 group-stage teams.
- The local database contains 72 group-stage fixtures.
- The app imports the provided `fifasprint.zip` scraped data.
- The app imports the emerging-player scouting report.
- Searches do not dead-end. If a query is not a participating team, the backend falls back to matching fixtures, city/venue results, scouting rows, or the full schedule.
- The browser demo is served locally through Vite at `http://127.0.0.1:5173`.
- The Python API is served locally at `http://127.0.0.1:8765`.

## Repository Contents

| Path | Description |
| --- | --- |
| `main.py` | CLI entrypoint for offline demo, live agent mode, custom JSON specs, and the local web API. |
| `deal_hunter/models.py` | Dataclasses for trip specs, matches, route legs, stays, candidates, itineraries, and optimization reports. |
| `deal_hunter/planner.py` | Route builder and itinerary optimizer. It groups matches by city/date, builds flight and hotel legs, ranks candidate combinations, and recommends subsets when a full trip exceeds budget. |
| `deal_hunter/fixtures.py` | Seeded demo candidate generator for tickets, flights, and hotels. This keeps the MVP usable without live ticket, flight, or hotel APIs. |
| `deal_hunter/worldcup_db.py` | SQLite database builder and search layer. It imports the source ZIP, imports the scouting report, seeds all FIFA 2026 group-stage teams and fixtures, resolves aliases, and returns fixture/scouting payloads. |
| `deal_hunter/web_demo.py` | Local HTTP API server for `/api/countries`, `/api/schedule`, `/api/plan`, and the legacy static demo. |
| `deal_hunter/agent.py` | Live agent orchestration for Bright Data and model-assisted candidate gathering. |
| `deal_hunter/brightdata.py` | Bright Data MCP client helpers. |
| `deal_hunter/cache.py` | Simple file-backed cache used by the agent/demo flow. |
| `deal_hunter/renderer.py` | Text rendering helpers for CLI reports. |
| `deal_hunter/specs.py` | Trip-spec loading and subset trimming helpers. |
| `src/App.tsx` | Main React app. It calls the API, renders team chips, match rows, scouting cards, and itinerary summary cards. |
| `src/components/ui/ai-prompt-box.tsx` | Prompt-box UI cloned from the supplied design context and adapted for FIFA 2026 search. |
| `src/index.css` | Tailwind base styles. |
| `src/main.tsx` | React bootstrapping. |
| `web/` | Legacy no-build static HTML/CSS/JS demo served directly by the Python server. |
| `data/fifa2026.db` | Small generated SQLite database committed for immediate local use. |
| `data/fifasprint.zip` | Provided scraped source bundle used by the importer. |
| `data/emerging_players_scouting_report.md` | Normalized pasted scouting report with player scores, watch teams, travel cities, dates, and scouting notes. |
| `data/demo_trip_spec.json` | Example trip specification for CLI and live-agent runs. |
| `pyproject.toml` and `uv.lock` | Python package metadata and lockfile. |
| `package.json` and `package-lock.json` | Frontend dependencies and scripts. |
| `vite.config.ts` | Vite setup, including `/api` proxying to the Python server. |
| `tailwind.config.ts`, `postcss.config.js`, `tsconfig*.json` | Frontend build configuration. |

## Data Sources

### `data/fifasprint.zip`

The source ZIP contains:

- `fixtures.csv`: scraped fixture fallback data with team, opponent, date, city, venue, competition, home/away, and source columns.
- `venues.csv`: venue-to-city mapping for FIFA 2026 host stadiums.
- `players.csv`: emerging-player input data.
- `DATA_SOURCES.md`: notes about live fixture API options and fallback strategy.
- `emerging_players_report.md`: generated report from the scraped-player workflow.

The importer keeps the raw scraped fixture rows in `scraped_fixtures` and marks matching full-schedule rows with `scraped_source = 1`.

### `data/emerging_players_scouting_report.md`

This report adds richer scouting context for 12 players:

- Jamal Musiala
- Kylian Mbappé
- Jude Bellingham
- Nuno Mendes
- Phil Foden
- Alejandro Garnacho
- Pedri
- Xavi Simons
- Gavi
- Sandro Tonali
- William Saliba
- Ryan Gravenberch

The importer stores these rows in `scouting_reports` and links each player to a World Cup team when the report provides a valid watch team.

### Full FIFA 2026 Group-Stage Snapshot

The backend seeds a complete 48-team and 72-fixture group-stage snapshot so every participating country can return matches. This is what makes searches work beyond the small scraped CSV sample.

## SQLite Database

The database is stored at:

```text
data/fifa2026.db
```

It is small enough to commit directly. Current verified row counts:

| Table | Rows | Purpose |
| --- | ---: | --- |
| `teams` | 48 | FIFA 2026 participating teams and groups. |
| `aliases` | 67+ | Search aliases such as `USA`, `South Korea`, `Ivory Coast`, and `Turkey`. |
| `fixtures` | 72 | Full group-stage fixture table. |
| `venues` | 16 | Venue-to-city mapping. |
| `scraped_fixtures` | 7 | Raw fixture rows imported from `fifasprint.zip`. |
| `players` | 12 | Raw player rows imported from `players.csv`. |
| `scouting_reports` | 12 | Rich scouting report rows imported from markdown. |
| `metadata` | varies | Import status and schema version. |

The DB is automatically rebuilt when `SCHEMA_VERSION` in `deal_hunter/worldcup_db.py` changes.

## Search Behavior

The search API accepts team names, aliases, players, clubs, venues, cities, and broad terms.

Examples:

| Query | Expected behavior |
| --- | --- |
| `USA` | Resolves to United States and returns its three Group D matches. |
| `South Korea` | Resolves to Korea Republic and returns its three Group A matches. |
| `Cote dIvoire` | Resolves to Côte d'Ivoire and returns its three Group E matches. |
| `Jamal Musiala` | Resolves through the scouting report to Germany fixtures and shows Jamal's scouting card. |
| `Dallas` | Returns the Dallas venue matches and Dallas-related scouting cards. |
| `Italy` | Italy is not in this dataset as a participating team, so the app returns all fixtures plus Sandro Tonali's scouting card noting no FIFA 2026 fixture. |
| `World Cup` | Returns the full 72-match group-stage table. |

## API Routes

Start the Python API first:

```bash
uv run python main.py --web-demo --port 8765
```

### `GET /api/countries`

Returns the 48 teams used for the chip selector.

```bash
curl http://127.0.0.1:8765/api/countries
```

### `GET /api/schedule?country=<query>`

Returns fixture rows and scouting cards for a query.

```bash
curl "http://127.0.0.1:8765/api/schedule?country=Jamal%20Musiala"
curl "http://127.0.0.1:8765/api/schedule?country=Dallas"
curl "http://127.0.0.1:8765/api/schedule?country=USA"
```

Response shape:

```json
{
  "country": {
    "code": "germany",
    "name": "Germany",
    "group": "E",
    "is_all": false
  },
  "matches": [],
  "scouting": [],
  "source": {
    "database": "data/fifa2026.db",
    "scraped_zip": "data/fifasprint.zip",
    "scouting_report": "data/emerging_players_scouting_report.md",
    "complete_schedule": "FIFA World Cup 2026 group-stage schedule snapshot"
  }
}
```

### `GET /api/plan?country=<query>&match_id=<id>`

Builds a seeded travel plan for selected matches.

```bash
curl "http://127.0.0.1:8765/api/plan?country=Germany&match_id=m010&match_id=m033"
```

The travel planner returns:

- selected matches
- route legs
- hotel stays
- seeded ticket candidates
- seeded flight candidates
- seeded hotel candidates
- ranked itinerary estimates
- dropped-match tradeoffs when the budget is exceeded

## Setup

### 1. Install system tools

Install:

- Python 3.14 or a compatible Python 3.x version supported by `uv`
- Node.js 22 or newer
- `uv`
- `npm`

Check versions:

```bash
python3 --version
node --version
npm --version
uv --version
```

### 2. Install Python dependencies

```bash
uv sync
```

### 3. Install frontend dependencies

```bash
npm install
```

### 4. Optional live-mode credentials

The FIFA 2026 search MVP does not require live credentials. Live agent mode can use Anthropic and Bright Data:

```bash
export ANTHROPIC_API_KEY="..."
export BRIGHTDATA_API_TOKEN="..."
```

Optional overrides:

```bash
export ANTHROPIC_MODEL="claude-sonnet-4-6"
export BRIGHTDATA_RATE_LIMIT="100/1h"
export FIFASPRINT_ZIP="/absolute/path/to/fifasprint.zip"
```

`FIFASPRINT_ZIP` is only needed if you want to import a different ZIP. By default, the app uses `data/fifasprint.zip`.

## Run The MVP

### 1. Start the Python API

```bash
uv run python main.py --web-demo --port 8765
```

Expected output:

```text
Web demo running at http://127.0.0.1:8765
```

### 2. Start the React UI

In a second terminal:

```bash
npm run dev -- --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

Vite proxies `/api/*` to `http://127.0.0.1:8765`.

### 3. Try searches

Use the prompt box or team chips.

Recommended test searches:

```text
Jamal Musiala
Germany
Dallas
South Korea
Cote dIvoire
Italy
World Cup
```

## Rebuild The Database

The DB is committed, but it can be regenerated at any time.

```bash
python3 - <<'PY'
from pathlib import Path
from deal_hunter.worldcup_db import DB_PATH, ensure_world_cup_database

if DB_PATH.exists():
    DB_PATH.unlink()

print(ensure_world_cup_database())
PY
```

Verify row counts:

```bash
python3 - <<'PY'
import sqlite3

conn = sqlite3.connect("data/fifa2026.db")
for table in ["teams", "fixtures", "venues", "scraped_fixtures", "players", "scouting_reports"]:
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table}: {count}")
PY
```

Expected counts:

```text
teams: 48
fixtures: 72
venues: 16
scraped_fixtures: 7
players: 12
scouting_reports: 12
```

## Validation

Run backend compile checks:

```bash
python3 -m compileall main.py deal_hunter
```

Run frontend production build:

```bash
npm run build
```

Run npm audit:

```bash
npm audit --audit-level=high
```

Run API smoke checks:

```bash
python3 - <<'PY'
from urllib.parse import urlencode
from urllib.request import urlopen
import json

for query in ["Jamal Musiala", "Dallas", "Italy", "USA", "South Korea"]:
    payload = json.load(urlopen("http://127.0.0.1:8765/api/schedule?" + urlencode({"country": query})))
    print(query, "=>", payload["country"]["name"], len(payload["matches"]), "matches", len(payload["scouting"]), "scouting")
    print("first match:", payload["matches"][0]["event_name"], payload["matches"][0]["city"])
    if payload["scouting"]:
        print("first scouting:", payload["scouting"][0]["name"], payload["scouting"][0]["emergence_score"])
PY
```

## CLI Usage

Offline seeded demo:

```bash
uv run python main.py --offline-demo
```

Browser API/static demo:

```bash
uv run python main.py --web-demo
```

Live model/agent demo:

```bash
uv run python main.py --demo
```

Custom trip spec:

```bash
uv run python main.py --spec-file data/demo_trip_spec.json
```

## Trip Spec Shape

```json
{
  "origin": "San Francisco (SFO)",
  "budget": 1250,
  "matches": [
    {
      "id": "m033",
      "event_name": "Germany vs Côte d'Ivoire",
      "city": "Toronto",
      "venue": "Toronto Stadium",
      "date": "2026-06-20T16:00:00",
      "priority": 5
    }
  ],
  "constraints": {
    "max_layovers": 1,
    "min_hotel_rating": 4.0,
    "ticket_tier_preference": "lower_bowl",
    "travelers_count": 1
  }
}
```

## How The Planner Works

1. The frontend sends a search query to `/api/schedule`.
2. The backend resolves the query against aliases, teams, scouting reports, fixtures, venues, and cities.
3. The user selects one or more matches.
4. The frontend calls `/api/plan`.
5. The planner groups selected matches by date and city.
6. The planner creates required flight legs and hotel stays.
7. Seeded demo ticket, flight, and hotel candidates are generated.
8. The optimizer evaluates combinations and ranks viable itineraries.
9. If the selected trip exceeds budget, the optimizer recommends a subset and reports restore-cost estimates.

## Known MVP Boundaries

- Ticket, flight, and hotel prices are seeded estimates for demo purposes unless live Bright Data mode is wired with credentials.
- The committed schedule is a snapshot. If FIFA changes fixtures, update `FIXTURES` in `deal_hunter/worldcup_db.py` and rebuild the DB.
- The frontend focuses on search, fixture discovery, scouting context, and itinerary summaries. It does not yet support booking links, payments, user accounts, or saved trips.
- The static `web/` demo is kept for no-build fallback. The main user-facing UI is the React app in `src/`.

## Contribution Notes

This contribution adds:

- A self-contained FIFA 2026 search database.
- Import support for the supplied scraped ZIP.
- Import support for the supplied emerging-player scouting report.
- Full participating-team search coverage.
- Player-aware search, including scouting cards.
- City and venue search.
- Prompt-box UI integration.
- Itinerary planning and seeded travel-pricing integration.
- Detailed setup and validation instructions.
