from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from deal_hunter.models import (
    CityStay,
    DroppedMatch,
    FlightCandidate,
    FlightLeg,
    HotelCandidate,
    Itinerary,
    MatchRequest,
    OptimizationReport,
    RoutePlan,
    TicketCandidate,
    TripSpec,
    dataclass_to_dict,
)


TIER_SCORES = {
    "any": 1.0,
    "upper_deck": 1.0,
    "upper_bowl": 1.5,
    "lower_bowl": 3.0,
    "club": 4.0,
    "vip": 5.0,
}


@dataclass(slots=True)
class PlanningState:
    spec: TripSpec
    route_plan: RoutePlan | None = None
    ticket_candidates: dict[str, list[TicketCandidate]] = field(default_factory=dict)
    flight_candidates: dict[str, list[FlightCandidate]] = field(default_factory=dict)
    hotel_candidates: dict[str, list[HotelCandidate]] = field(default_factory=dict)

    def ensure_route_plan(self) -> RoutePlan:
        if self.route_plan is None:
            self.route_plan = build_route_plan(self.spec)
        return self.route_plan

    def save_ticket_candidates(
        self, match_id: str, candidates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        match = self.match_by_id(match_id)
        saved: list[TicketCandidate] = []
        for payload in candidates:
            candidate = TicketCandidate(
                source=payload["source"],
                url=payload["url"],
                total_price=float(payload["total_price"]),
                currency=payload.get("currency", "USD"),
                tier=payload.get("tier", "any"),
                section=payload.get("section"),
                fees_included=payload.get("fees_included"),
                notes=payload.get("notes", ""),
            )
            if candidate.total_price <= 0:
                continue
            saved.append(candidate)
        self.ticket_candidates[match.id] = sorted(saved, key=lambda item: item.total_price)[:3]
        return {
            "match_id": match_id,
            "saved_count": len(self.ticket_candidates.get(match_id, [])),
        }

    def save_flight_candidates(
        self, leg_id: str, candidates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        leg = self.leg_by_id(leg_id)
        saved: list[FlightCandidate] = []
        for payload in candidates:
            candidate = FlightCandidate(
                source=payload["source"],
                url=payload["url"],
                total_price=float(payload["total_price"]),
                currency=payload.get("currency", "USD"),
                carrier=payload["carrier"],
                depart_at=parse_dt(payload["depart_at"]),
                arrive_at=parse_dt(payload["arrive_at"]),
                layovers=int(payload.get("layovers", 0)),
                duration_hours=float(payload["duration_hours"])
                if payload.get("duration_hours") is not None
                else None,
                notes=payload.get("notes", ""),
            )
            if is_viable_flight(self.spec, leg, candidate):
                saved.append(candidate)
        self.flight_candidates[leg.id] = sorted(saved, key=lambda item: item.total_price)[:3]
        return {"leg_id": leg_id, "saved_count": len(self.flight_candidates.get(leg_id, []))}

    def save_hotel_candidates(
        self, stay_id: str, candidates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        stay = self.stay_by_id(stay_id)
        saved: list[HotelCandidate] = []
        for payload in candidates:
            candidate = HotelCandidate(
                source=payload["source"],
                url=payload["url"],
                total_price=float(payload["total_price"]),
                currency=payload.get("currency", "USD"),
                name=payload["name"],
                nights=int(payload["nights"]),
                rating=float(payload["rating"])
                if payload.get("rating") is not None
                else None,
                distance_km=float(payload["distance_km"])
                if payload.get("distance_km") is not None
                else None,
                notes=payload.get("notes", ""),
            )
            if is_viable_hotel(self.spec, stay, candidate):
                saved.append(candidate)
        self.hotel_candidates[stay.id] = sorted(saved, key=lambda item: item.total_price)[:3]
        return {"stay_id": stay_id, "saved_count": len(self.hotel_candidates.get(stay_id, []))}

    def bucket_status(self) -> dict[str, Any]:
        route_plan = self.ensure_route_plan()
        return {
            "tickets": [
                {
                    "match_id": match.id,
                    "event_name": match.event_name,
                    "saved": len(self.ticket_candidates.get(match.id, [])),
                    "cheapest": cheapest_price(self.ticket_candidates.get(match.id, [])),
                }
                for match in self.spec.matches
            ],
            "flights": [
                {
                    "leg_id": leg.id,
                    "from": leg.origin_label,
                    "to": leg.destination_label,
                    "saved": len(self.flight_candidates.get(leg.id, [])),
                    "cheapest": cheapest_price(self.flight_candidates.get(leg.id, [])),
                }
                for leg in route_plan.legs
            ],
            "hotels": [
                {
                    "stay_id": stay.id,
                    "city": stay.city,
                    "saved": len(self.hotel_candidates.get(stay.id, [])),
                    "cheapest": cheapest_price(self.hotel_candidates.get(stay.id, [])),
                }
                for stay in route_plan.stays
            ],
        }

    def as_trip_context(self) -> dict[str, Any]:
        return {
            "trip_spec": dataclass_to_dict(self.spec),
            "route_plan": dataclass_to_dict(self.ensure_route_plan()),
            "bucket_status": self.bucket_status(),
        }

    def match_by_id(self, match_id: str) -> MatchRequest:
        for match in self.spec.matches:
            if match.id == match_id:
                return match
        raise KeyError(f"Unknown match id: {match_id}")

    def stay_by_id(self, stay_id: str) -> CityStay:
        for stay in self.ensure_route_plan().stays:
            if stay.id == stay_id:
                return stay
        raise KeyError(f"Unknown stay id: {stay_id}")

    def leg_by_id(self, leg_id: str) -> FlightLeg:
        for leg in self.ensure_route_plan().legs:
            if leg.id == leg_id:
                return leg
        raise KeyError(f"Unknown leg id: {leg_id}")


def build_route_plan(spec: TripSpec) -> RoutePlan:
    matches = sorted(spec.matches, key=lambda item: item.kickoff_at)
    grouped: list[list[MatchRequest]] = []
    for match in matches:
        if grouped and grouped[-1][0].city == match.city:
            grouped[-1].append(match)
        else:
            grouped.append([match])

    stays: list[CityStay] = []
    for group in grouped:
        first = group[0]
        last = group[-1]
        check_in = first.kickoff_at.date() - timedelta(days=1)
        check_out = last.kickoff_at.date() + timedelta(days=1)
        stays.append(
            CityStay(
                id=f"stay-{first.city.lower().replace(' ', '-')}-{check_in.isoformat()}",
                city=first.city,
                venue=first.venue,
                check_in=check_in,
                check_out=check_out,
                match_ids=[match.id for match in group],
                kickoff_at=first.kickoff_at,
            )
        )

    legs: list[FlightLeg] = []
    if not stays:
        return RoutePlan(stays=[], legs=[])

    first_stay = stays[0]
    legs.append(
        FlightLeg(
            id=f"leg-origin-to-{slug(first_stay.city)}",
            origin_label=spec.origin,
            destination_label=first_stay.city,
            depart_on=first_stay.check_in,
            arrive_by=first_stay.kickoff_at - timedelta(hours=4),
            match_ids=list(first_stay.match_ids),
        )
    )

    for index, (current_stay, next_stay) in enumerate(zip(stays, stays[1:]), start=1):
        travel_date = max(current_stay.check_out, next_stay.check_in)
        legs.append(
            FlightLeg(
                id=f"leg-{index}-{slug(current_stay.city)}-to-{slug(next_stay.city)}",
                origin_label=current_stay.city,
                destination_label=next_stay.city,
                depart_on=travel_date,
                arrive_by=next_stay.kickoff_at - timedelta(hours=4),
                match_ids=list(next_stay.match_ids),
            )
        )

    last_stay = stays[-1]
    legs.append(
        FlightLeg(
            id=f"leg-{slug(last_stay.city)}-to-origin",
            origin_label=last_stay.city,
            destination_label=spec.origin,
            depart_on=last_stay.check_out,
            arrive_by=None,
            match_ids=list(last_stay.match_ids),
        )
    )

    return RoutePlan(stays=stays, legs=legs)


def optimize_state(state: PlanningState) -> OptimizationReport:
    route_plan = state.ensure_route_plan()
    missing = list_missing_buckets(state, route_plan)
    if missing:
        return OptimizationReport(
            status="incomplete",
            itineraries=[],
            route_plan=route_plan,
            missing_buckets=missing,
            notes=["Some candidate buckets are still empty."],
        )

    match_buckets = [state.ticket_candidates[match.id] for match in state.spec.matches]
    flight_buckets = [state.flight_candidates[leg.id] for leg in route_plan.legs]
    hotel_buckets = [state.hotel_candidates[stay.id] for stay in route_plan.stays]
    combinations = itertools.product(*match_buckets, *flight_buckets, *hotel_buckets)

    match_count = len(state.spec.matches)
    leg_count = len(route_plan.legs)
    all_itineraries: list[Itinerary] = []
    for combination in combinations:
        ticket_slice = combination[:match_count]
        flight_slice = combination[match_count : match_count + leg_count]
        hotel_slice = combination[match_count + leg_count :]
        tickets = {
            match.id: candidate
            for match, candidate in zip(state.spec.matches, ticket_slice, strict=True)
        }
        flights = {
            leg.id: candidate
            for leg, candidate in zip(route_plan.legs, flight_slice, strict=True)
        }
        hotels = {
            stay.id: candidate
            for stay, candidate in zip(route_plan.stays, hotel_slice, strict=True)
        }
        total_cost = (
            sum(candidate.total_price for candidate in tickets.values())
            + sum(candidate.total_price for candidate in flights.values())
            + sum(candidate.total_price for candidate in hotels.values())
        )
        comfort = score_comfort(list(tickets.values()), list(flights.values()), list(hotels.values()))
        all_itineraries.append(
            Itinerary(
                label="candidate",
                match_ids=[match.id for match in state.spec.matches],
                tickets=tickets,
                flights=flights,
                hotels=hotels,
                total_cost=round(total_cost, 2),
                comfort_score=comfort,
                value_score=0.0,
                within_budget=total_cost <= state.spec.budget,
            )
        )

    if not all_itineraries:
        return OptimizationReport(
            status="incomplete",
            itineraries=[],
            route_plan=route_plan,
            notes=["No complete itinerary combinations could be formed."],
        )

    cheapest_cost = min(item.total_cost for item in all_itineraries)
    for itinerary in all_itineraries:
        itinerary.value_score = itinerary.comfort_score - ((itinerary.total_cost - cheapest_cost) * 0.015)

    within_budget = [item for item in all_itineraries if item.within_budget]
    if not within_budget:
        subset = choose_subset_under_budget(state, route_plan)
        return OptimizationReport(
            status="subset_recommended",
            itineraries=sorted(all_itineraries, key=lambda item: item.total_cost)[:1],
            route_plan=route_plan,
            suggested_subset_match_ids=subset[0],
            dropped_matches=subset[1],
            notes=["The full trip is over budget. Re-price the recommended subset route."],
        )

    cheapest = min(within_budget, key=lambda item: item.total_cost)
    best_value = max(within_budget, key=lambda item: (item.value_score, -item.total_cost))
    most_comfortable = max(
        within_budget, key=lambda item: (item.comfort_score, item.value_score, -item.total_cost)
    )

    ranked = dedupe_ranked(
        [
            label_itinerary("Cheapest", cheapest, state.spec.budget),
            label_itinerary("Best Value", best_value, state.spec.budget),
            label_itinerary("Most Comfortable", most_comfortable, state.spec.budget),
        ]
    )
    return OptimizationReport(status="ok", itineraries=ranked, route_plan=route_plan)


def choose_subset_under_budget(
    state: PlanningState, route_plan: RoutePlan
) -> tuple[list[str], list[DroppedMatch]]:
    item_costs = approximate_match_costs(state, route_plan)
    matches = state.spec.matches
    best_match_ids: list[str] = []
    best_score: tuple[int, int, float] | None = None
    for subset_bits in range(1, 1 << len(matches)):
        subset_matches = [matches[index] for index in range(len(matches)) if subset_bits & (1 << index)]
        total_cost = sum(item_costs[match.id] for match in subset_matches)
        if total_cost > state.spec.budget:
            continue
        priority_total = sum(match.priority for match in subset_matches)
        score = (priority_total, len(subset_matches), -total_cost)
        if best_score is None or score > best_score:
            best_score = score
            best_match_ids = [match.id for match in subset_matches]

    if not best_match_ids:
        cheapest_match = min(matches, key=lambda item: item.priority)
        best_match_ids = [cheapest_match.id]

    kept = set(best_match_ids)
    dropped = [
        DroppedMatch(
            match_id=match.id,
            event_name=match.event_name,
            priority=match.priority,
            approximate_restore_cost=round(item_costs[match.id], 2),
        )
        for match in matches
        if match.id not in kept
    ]
    return best_match_ids, dropped


def approximate_match_costs(state: PlanningState, route_plan: RoutePlan) -> dict[str, float]:
    costs = {
        match.id: min(candidate.total_price for candidate in state.ticket_candidates[match.id])
        for match in state.spec.matches
    }

    for stay in route_plan.stays:
        share = min(candidate.total_price for candidate in state.hotel_candidates[stay.id]) / max(
            1, len(stay.match_ids)
        )
        for match_id in stay.match_ids:
            costs[match_id] += share

    for index, leg in enumerate(route_plan.legs):
        price = min(candidate.total_price for candidate in state.flight_candidates[leg.id])
        target_match_ids = leg.match_ids or route_plan.stays[min(index, len(route_plan.stays) - 1)].match_ids
        share = price / max(1, len(target_match_ids))
        for match_id in target_match_ids:
            costs[match_id] += share

    return costs


def list_missing_buckets(state: PlanningState, route_plan: RoutePlan) -> list[str]:
    missing: list[str] = []
    for match in state.spec.matches:
        if not state.ticket_candidates.get(match.id):
            missing.append(f"ticket:{match.id}")
    for leg in route_plan.legs:
        if not state.flight_candidates.get(leg.id):
            missing.append(f"flight:{leg.id}")
    for stay in route_plan.stays:
        if not state.hotel_candidates.get(stay.id):
            missing.append(f"hotel:{stay.id}")
    return missing


def is_viable_flight(spec: TripSpec, leg: FlightLeg, candidate: FlightCandidate) -> bool:
    if candidate.total_price <= 0:
        return False
    max_layovers = spec.constraints.max_layovers
    if max_layovers is not None and candidate.layovers > max_layovers:
        return False
    if spec.constraints.earliest_depart and leg.origin_label == spec.origin:
        if candidate.depart_at.date() < spec.constraints.earliest_depart:
            return False
    if spec.constraints.latest_return and leg.destination_label == spec.origin:
        if candidate.arrive_at.date() > spec.constraints.latest_return:
            return False
    if leg.arrive_by is not None and candidate.arrive_at > leg.arrive_by:
        return False
    return True


def is_viable_hotel(spec: TripSpec, stay: CityStay, candidate: HotelCandidate) -> bool:
    if candidate.total_price <= 0:
        return False
    if candidate.nights < stay.nights:
        return False
    min_rating = spec.constraints.min_hotel_rating
    if min_rating is not None and candidate.rating is not None and candidate.rating < min_rating:
        return False
    if candidate.distance_km is not None and candidate.distance_km > 25:
        return False
    return True


def score_comfort(
    tickets: list[TicketCandidate],
    flights: list[FlightCandidate],
    hotels: list[HotelCandidate],
) -> float:
    seat_score = sum(TIER_SCORES.get(ticket.tier, 1.0) for ticket in tickets) * 2.0
    flight_score = 0.0
    for flight in flights:
        duration_bonus = 10.0 - (flight.duration_hours or 6.0)
        flight_score += max(0.0, duration_bonus) - (flight.layovers * 2.5)
    hotel_score = 0.0
    for hotel in hotels:
        hotel_score += (hotel.rating or 3.5) * 2.5
        if hotel.distance_km is not None:
            hotel_score -= hotel.distance_km * 0.15
    return round(seat_score + flight_score + hotel_score, 3)


def label_itinerary(label: str, itinerary: Itinerary, budget: float) -> Itinerary:
    itinerary.label = label
    itinerary.reasoning = build_reasoning(label, itinerary, budget)
    return itinerary


def build_reasoning(label: str, itinerary: Itinerary, budget: float) -> str:
    headroom = budget - itinerary.total_cost
    if label == "Cheapest":
        return (
            f"This is the lowest all-in price at ${itinerary.total_cost:,.0f}, "
            f"leaving ${headroom:,.0f} of headroom. It accepts the leanest mix of seats, "
            "hotel quality, and flight comfort that still satisfies the viability rules."
        )
    if label == "Best Value":
        return (
            f"This keeps the trip under budget at ${itinerary.total_cost:,.0f} while avoiding the "
            "roughest tradeoffs on layovers, hotel rating, and seat tier. It gives up some savings "
            "to improve the overall experience where the cost delta is still reasonable."
        )
    return (
        f"This is the most comfortable itinerary that still fits the ${budget:,.0f} budget, "
        f"landing at ${itinerary.total_cost:,.0f}. It prioritizes better seats, stronger hotel options, "
        "and simpler flight legs over absolute minimum spend."
    )


def dedupe_ranked(itineraries: list[Itinerary]) -> list[Itinerary]:
    seen: set[tuple[str, ...]] = set()
    output: list[Itinerary] = []
    for itinerary in itineraries:
        signature = itinerary_signature(itinerary)
        if signature in seen:
            continue
        seen.add(signature)
        output.append(itinerary)
    return output


def itinerary_signature(itinerary: Itinerary) -> tuple[str, ...]:
    values: list[str] = []
    values.extend(sorted(ticket.url for ticket in itinerary.tickets.values()))
    values.extend(sorted(flight.url for flight in itinerary.flights.values()))
    values.extend(sorted(hotel.url for hotel in itinerary.hotels.values()))
    return tuple(values)


def cheapest_price(candidates: list[Any] | None) -> float | None:
    if not candidates:
        return None
    return min(candidate.total_price for candidate in candidates)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def slug(value: str) -> str:
    return value.lower().replace(" ", "-").replace("/", "-")
