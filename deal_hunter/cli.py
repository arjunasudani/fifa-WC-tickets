from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich.console import Console

from deal_hunter.agent import AnthropicTravelAgent
from deal_hunter.brightdata import BrightDataMCPClient
from deal_hunter.cache import JsonFileCache
from deal_hunter.fixtures import seed_demo_candidates
from deal_hunter.planner import PlanningState, optimize_state
from deal_hunter.renderer import render_report
from deal_hunter.specs import load_trip_spec, trim_trip_spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ticket / Travel Deal Hunter Agent")
    parser.add_argument("--spec-file", type=Path, default=None)
    parser.add_argument("--demo", action="store_true", help="Use the bundled demo trip spec.")
    parser.add_argument(
        "--offline-demo",
        action="store_true",
        help="Use seeded offline data instead of live Anthropic + Bright Data calls.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".cache"),
        help="Directory used for Bright Data tool-result caching.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=20,
        help="Maximum Anthropic tool-use turns for live data collection.",
    )
    parser.add_argument(
        "--web-demo",
        action="store_true",
        help="Start a local browser demo using seeded offline data.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Web demo bind host.")
    parser.add_argument("--port", type=int, default=8765, help="Web demo start port.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    console = Console()
    use_demo_spec = args.demo or args.offline_demo or (
        args.web_demo and args.spec_file is None
    )
    spec = load_trip_spec(args.spec_file, demo=use_demo_spec)
    if args.web_demo:
        from deal_hunter.web_demo import run_web_demo

        run_web_demo(spec, host=args.host, port=args.port)
        return
    asyncio.run(
        run(
            console,
            spec=spec,
            offline_demo=args.offline_demo,
            cache_dir=args.cache_dir,
            max_turns=args.max_turns,
        )
    )


async def run(
    console: Console,
    *,
    spec,
    offline_demo: bool,
    cache_dir: Path,
    max_turns: int,
) -> None:
    report = None
    if offline_demo:
        state = PlanningState(spec)
        seed_demo_candidates(state)
        report = optimize_state(state)
        if report.status == "subset_recommended":
            dropped_matches = report.dropped_matches
            subset_spec = trim_trip_spec(spec, report.suggested_subset_match_ids)
            state = PlanningState(subset_spec)
            seed_demo_candidates(state)
            report = optimize_state(state)
            report.dropped_matches = dropped_matches
        render_report(console, state, report)
        return

    cache = JsonFileCache(cache_dir)
    agent = AnthropicTravelAgent(max_turns=max_turns)
    async with BrightDataMCPClient(cache=cache) as brightdata_client:
        state = PlanningState(spec)
        await agent.collect_trip_data(state, brightdata_client)
        report = optimize_state(state)
        dropped_matches = report.dropped_matches
        if report.status == "subset_recommended":
            subset_spec = trim_trip_spec(spec, report.suggested_subset_match_ids)
            state = PlanningState(subset_spec)
            await agent.collect_trip_data(state, brightdata_client)
            report = optimize_state(state)
            report.dropped_matches = dropped_matches

    render_report(console, state, report)
