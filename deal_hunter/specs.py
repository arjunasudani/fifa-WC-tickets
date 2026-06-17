from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from deal_hunter.models import MatchRequest, TripConstraints, TripSpec


DEFAULT_MATCH_TIME = time(hour=19, minute=30)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def parse_match_datetime(value: str) -> datetime:
    if "T" in value:
        return datetime.fromisoformat(value)
    return datetime.combine(date.fromisoformat(value), DEFAULT_MATCH_TIME)


def parse_trip_spec(payload: dict[str, Any]) -> TripSpec:
    constraints_payload = payload.get("constraints", {})
    constraints = TripConstraints(
        max_layovers=constraints_payload.get("max_layovers"),
        earliest_depart=_parse_date(constraints_payload.get("earliest_depart")),
        latest_return=_parse_date(constraints_payload.get("latest_return")),
        min_hotel_rating=constraints_payload.get("min_hotel_rating"),
        ticket_tier_preference=constraints_payload.get(
            "ticket_tier_preference", "any"
        ),
        travelers_count=constraints_payload.get("travelers_count", 1),
    )

    matches = [
        MatchRequest(
            id=match.get("id") or slugify(match["event_name"]),
            event_name=match["event_name"],
            city=match["city"],
            venue=match["venue"],
            kickoff_at=parse_match_datetime(match["date"]),
            priority=match.get("priority", 3),
        )
        for match in payload["matches"]
    ]

    return TripSpec(
        origin=payload["origin"],
        budget=float(payload["budget"]),
        matches=matches,
        constraints=constraints,
    )


def load_trip_spec(spec_file: Path | None, demo: bool) -> TripSpec:
    if demo:
        spec_file = Path("data/demo_trip_spec.json")
    if spec_file is None:
        raise ValueError("Pass --spec-file or --demo/--offline-demo.")
    payload = json.loads(spec_file.read_text())
    return parse_trip_spec(payload)


def trim_trip_spec(spec: TripSpec, match_ids: list[str]) -> TripSpec:
    selected = [match for match in spec.matches if match.id in set(match_ids)]
    return TripSpec(
        origin=spec.origin,
        budget=spec.budget,
        matches=selected,
        constraints=spec.constraints,
    )


def slugify(value: str) -> str:
    return (
        value.lower()
        .replace("&", "and")
        .replace("/", "-")
        .replace(" ", "-")
        .replace(".", "")
    )
