from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal


TicketTier = Literal[
    "any",
    "upper_deck",
    "upper_bowl",
    "lower_bowl",
    "club",
    "vip",
]


@dataclass(slots=True)
class TripConstraints:
    max_layovers: int | None = None
    earliest_depart: date | None = None
    latest_return: date | None = None
    min_hotel_rating: float | None = None
    ticket_tier_preference: TicketTier = "any"
    travelers_count: int = 1


@dataclass(slots=True)
class MatchRequest:
    id: str
    event_name: str
    city: str
    venue: str
    kickoff_at: datetime
    priority: int = 3


@dataclass(slots=True)
class TripSpec:
    origin: str
    budget: float
    matches: list[MatchRequest]
    constraints: TripConstraints = field(default_factory=TripConstraints)


@dataclass(slots=True)
class CityStay:
    id: str
    city: str
    venue: str
    check_in: date
    check_out: date
    match_ids: list[str]
    kickoff_at: datetime

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days


@dataclass(slots=True)
class FlightLeg:
    id: str
    origin_label: str
    destination_label: str
    depart_on: date
    arrive_by: datetime | None
    match_ids: list[str]


@dataclass(slots=True)
class RoutePlan:
    stays: list[CityStay]
    legs: list[FlightLeg]


@dataclass(slots=True)
class TicketCandidate:
    source: str
    url: str
    total_price: float
    currency: str
    tier: str
    section: str | None
    fees_included: bool | None
    notes: str = ""


@dataclass(slots=True)
class FlightCandidate:
    source: str
    url: str
    total_price: float
    currency: str
    carrier: str
    depart_at: datetime
    arrive_at: datetime
    layovers: int
    duration_hours: float | None
    notes: str = ""


@dataclass(slots=True)
class HotelCandidate:
    source: str
    url: str
    total_price: float
    currency: str
    name: str
    nights: int
    rating: float | None
    distance_km: float | None
    notes: str = ""


@dataclass(slots=True)
class Itinerary:
    label: str
    match_ids: list[str]
    tickets: dict[str, TicketCandidate]
    flights: dict[str, FlightCandidate]
    hotels: dict[str, HotelCandidate]
    total_cost: float
    comfort_score: float
    value_score: float
    within_budget: bool
    reasoning: str = ""


@dataclass(slots=True)
class DroppedMatch:
    match_id: str
    event_name: str
    priority: int
    approximate_restore_cost: float | None


@dataclass(slots=True)
class OptimizationReport:
    status: Literal["ok", "subset_recommended", "incomplete"]
    itineraries: list[Itinerary]
    route_plan: RoutePlan
    missing_buckets: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    suggested_subset_match_ids: list[str] = field(default_factory=list)
    dropped_matches: list[DroppedMatch] = field(default_factory=list)


def dataclass_to_dict(value: Any) -> Any:
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: dataclass_to_dict(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {
            key: dataclass_to_dict(getattr(value, key))
            for key in value.__dataclass_fields__
        }
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
