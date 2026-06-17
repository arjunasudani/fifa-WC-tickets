# Emerging Players Agent

A minimal Python command-line agent that ranks emerging football/soccer players under age 23 using sample data from `players.csv`.

## Setup

1. Install Python 3.8 or newer.
2. Open a terminal in the project folder.

## Usage

Run the script:

```bash
python3 emerging_players_agent.py
```

That command will:
- read `players.csv`
- compute an emergence score for each player
- load fixtures from `fixtures.csv`, or from football-data.org when configured
- print a ranked table to the terminal
- generate `emerging_players_report.md`

To view the report in your browser, start the local server:

```bash
python3 serve_report.py
```

Then open:

```text
http://127.0.0.1:8000/emerging_players_report.md
```

## Player images

Fetch player images from Wikipedia/Wikimedia into `player_images/`:

```bash
python3 fetch_player_images.py
```

That creates:

- `player_images/*.jpg` or `*.png`
- `player_images/manifest.csv`
- `player_images/manifest.json`
- `player_images/index.md`

## Data

The `players.csv` file contains sample player records with attributes used for scoring.

`fixtures.csv` is the offline fixture fallback. It maps teams to upcoming games, cities, venues, and competitions for the travel app.

`venues.csv` maps stadium names to travel cities. This is needed because fixture APIs often return a venue name but not a separate city field.

## Live fixture API

The project is wired for football-data.org because its team matches endpoint fits the app flow: identify the player's team, then fetch that team's upcoming games.

Set an API token before running the agent:

```bash
export FOOTBALL_DATA_API_TOKEN="your-token"
python3 emerging_players_agent.py
```

Optional settings:

```bash
export FOOTBALL_DATA_COMPETITION="WC"
export FOOTBALL_DATA_SEASON="2026"
```

When live fixtures are available, they are written to `fixtures_live.csv`. The agent still keeps `fixtures.csv` as a fallback for teams the API does not return.

## Notes

- The scoring model rewards younger players, rising minutes, strong per-90 production, national team exposure, tournament visibility, and contract opportunity.
- The project uses only Python standard libraries.
