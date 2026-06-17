from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from deal_hunter.models import CityStay, FlightLeg, MatchRequest
from deal_hunter.planner import PlanningState


def seed_demo_candidates(state: PlanningState) -> None:
    route_plan = state.ensure_route_plan()
    match_fixtures = {
        "lakers-knicks": [
            {
                "source": "StubHub",
                "url": "https://example.com/stubhub/lakers-knicks/lower",
                "total_price": 285,
                "currency": "USD",
                "tier": "lower_bowl",
                "section": "112",
                "fees_included": True,
                "notes": "Lowest lower-bowl listing with fees shown.",
            },
            {
                "source": "SeatGeek",
                "url": "https://example.com/seatgeek/lakers-knicks/upper",
                "total_price": 218,
                "currency": "USD",
                "tier": "upper_bowl",
                "section": "214",
                "fees_included": True,
                "notes": "Cheapest viable seat.",
            },
            {
                "source": "Vivid Seats",
                "url": "https://example.com/vivid/lakers-knicks/club",
                "total_price": 354,
                "currency": "USD",
                "tier": "club",
                "section": "VIP 7",
                "fees_included": False,
                "notes": "Base price plus noted fee uncertainty.",
            },
        ],
        "nets-heat": [
            {
                "source": "StubHub",
                "url": "https://example.com/stubhub/nets-heat/lower",
                "total_price": 246,
                "currency": "USD",
                "tier": "lower_bowl",
                "section": "23",
                "fees_included": True,
                "notes": "Best lower-bowl floor.",
            },
            {
                "source": "SeatGeek",
                "url": "https://example.com/seatgeek/nets-heat/upper",
                "total_price": 188,
                "currency": "USD",
                "tier": "upper_bowl",
                "section": "225",
                "fees_included": True,
                "notes": "Cheapest viable seat.",
            },
            {
                "source": "Viagogo",
                "url": "https://example.com/viagogo/nets-heat/club",
                "total_price": 312,
                "currency": "USD",
                "tier": "club",
                "section": "VIP 12",
                "fees_included": True,
                "notes": "Higher comfort option.",
            },
        ],
    }

    flight_price_map: dict[tuple[str, str], list[int]] = {
        ("San Francisco (SFO)", "Los Angeles"): [160, 205, 290],
        ("Los Angeles", "New York"): [245, 315, 435],
        ("New York", "San Francisco (SFO)"): [275, 330, 415],
        ("Los Angeles", "San Francisco (SFO)"): [165, 220, 305],
        ("San Francisco (SFO)", "New York"): [325, 390, 510],
    }

    hotel_price_map: dict[str, list[tuple[str, int, float, float]]] = {
        "Los Angeles": [
            ("citizenM Los Angeles", 248, 4.4, 2.4),
            ("Moxy Downtown LA", 292, 4.3, 1.8),
            ("JW Marriott LA Live", 418, 4.6, 0.4),
        ],
        "New York": [
            ("Hampton Inn Brooklyn", 318, 4.2, 2.1),
            ("Ace Hotel Brooklyn", 372, 4.4, 1.5),
            ("1 Hotel Brooklyn Bridge", 548, 4.7, 3.6),
        ],
        "Chicago": [
            ("Hyatt Place River North", 286, 4.2, 3.4),
            ("The Hoxton Chicago", 346, 4.5, 2.9),
            ("The Gwen Chicago", 462, 4.6, 1.8),
        ],
        "Las Vegas": [
            ("Park MGM Las Vegas", 238, 4.2, 1.4),
            ("Virgin Hotels Las Vegas", 312, 4.3, 2.7),
            ("Waldorf Astoria Las Vegas", 506, 4.7, 1.1),
        ],
        "London": [
            ("The Hoxton Southwark", 438, 4.5, 5.2),
            ("citizenM Tower of London", 386, 4.4, 7.8),
            ("Sea Containers London", 542, 4.6, 6.0),
        ],
        "Manchester": [
            ("Motel One Manchester", 248, 4.3, 4.1),
            ("Dakota Manchester", 354, 4.6, 3.4),
            ("The Lowry Hotel", 488, 4.7, 4.8),
        ],
        "Tokyo": [
            ("Hotel Metropolitan Tokyo", 326, 4.4, 7.8),
            ("Nohga Hotel Ueno Tokyo", 384, 4.5, 6.9),
            ("The Gate Hotel Tokyo", 528, 4.6, 8.4),
        ],
        "Osaka": [
            ("Hotel Hankyu Respire Osaka", 284, 4.3, 5.1),
            ("Cross Hotel Osaka", 338, 4.4, 4.3),
            ("Conrad Osaka", 562, 4.7, 6.5),
        ],
    }

    for match in state.spec.matches:
        state.save_ticket_candidates(
            match.id,
            match_fixtures.get(match.id) or build_ticket_candidates(match),
        )

    for leg in route_plan.legs:
        prices = flight_price_map.get(
            (leg.origin_label, leg.destination_label),
            build_flight_prices(leg),
        )
        candidates = []
        for index, price in enumerate(prices):
            depart_at = datetime.combine(leg.depart_on, datetime.min.time()).replace(
                hour=7 + (index * 3)
            )
            arrival_at = depart_at + timedelta(
                hours=flight_duration_hours(leg, index)
            )
            candidates.append(
                {
                    "source": ["Google Flights", "Skyscanner", "Kayak"][index],
                    "url": f"https://example.com/flights/{leg.id}/{index}",
                    "total_price": price,
                    "currency": "USD",
                    "carrier": ["Delta", "United", "JetBlue"][index],
                    "depart_at": depart_at.isoformat(),
                    "arrive_at": arrival_at.isoformat(),
                    "layovers": 0 if index == 0 else index - 1,
                    "duration_hours": round((arrival_at - depart_at).total_seconds() / 3600, 1),
                    "notes": "Seeded offline demo fare.",
                }
            )
        state.save_flight_candidates(leg.id, candidates)

    for stay in route_plan.stays:
        candidates = []
        hotel_options = hotel_price_map.get(stay.city) or build_hotel_options(stay)
        for index, (name, price, rating, distance_km) in enumerate(hotel_options):
            candidates.append(
                {
                    "source": ["Booking.com", "Hotels.com", "Booking.com"][index],
                    "url": f"https://example.com/hotels/{stay.id}/{index}",
                    "total_price": price,
                    "currency": "USD",
                    "name": name,
                    "nights": stay.nights,
                    "rating": rating,
                    "distance_km": distance_km,
                    "notes": "Seeded offline demo hotel.",
                }
            )
        state.save_hotel_candidates(stay.id, candidates)


def build_ticket_candidates(match: MatchRequest) -> list[dict[str, object]]:
    base = 156 + stable_amount(match.id, 58)
    return [
        {
            "source": "SeatGeek",
            "url": f"https://example.com/seatgeek/{match.id}/upper",
            "total_price": base,
            "currency": "USD",
            "tier": "upper_bowl",
            "section": f"{200 + stable_amount(match.city, 38)}",
            "fees_included": True,
            "notes": "Seeded schedule-search ticket floor.",
        },
        {
            "source": "StubHub",
            "url": f"https://example.com/stubhub/{match.id}/lower",
            "total_price": base + 72,
            "currency": "USD",
            "tier": "lower_bowl",
            "section": f"{100 + stable_amount(match.venue, 42)}",
            "fees_included": True,
            "notes": "Seeded lower-bowl comparison listing.",
        },
        {
            "source": "Vivid Seats",
            "url": f"https://example.com/vivid/{match.id}/club",
            "total_price": base + 138,
            "currency": "USD",
            "tier": "club",
            "section": f"Club {1 + stable_amount(match.event_name, 18)}",
            "fees_included": False,
            "notes": "Seeded premium listing with fee uncertainty.",
        },
    ]


def build_flight_prices(leg: FlightLeg) -> list[int]:
    base = 145 + stable_amount(f"{leg.origin_label}:{leg.destination_label}", 180)
    if is_international_leg(leg):
        base += 360
    return [base, base + 82, base + 174]


def flight_duration_hours(leg: FlightLeg, index: int) -> float:
    if is_international_leg(leg):
        return 9.2 + (index * 1.4)
    if leg.origin_label == leg.destination_label:
        return 1.0
    return 1.8 + (index * 1.7)


def build_hotel_options(stay: CityStay) -> list[tuple[str, int, float, float]]:
    base = (108 + stable_amount(stay.city, 82)) * max(1, stay.nights)
    return [
        (f"{stay.city} Central Hotel", base, 4.1, 4.8),
        (f"{stay.city} Matchday House", base + 74, 4.3, 2.6),
        (f"{stay.city} Grand", base + 188, 4.6, 1.4),
    ]


def is_international_leg(leg: FlightLeg) -> bool:
    labels = f"{leg.origin_label} {leg.destination_label}"
    international_host_cities = (
        "Mexico City",
        "Guadalajara",
        "Monterrey",
        "Toronto",
        "Vancouver",
    )
    return any(city in labels for city in international_host_cities)


def stable_amount(value: str, modulo: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo
