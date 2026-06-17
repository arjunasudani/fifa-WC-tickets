from __future__ import annotations

from rich.console import Console
from rich.table import Table

from deal_hunter.models import OptimizationReport
from deal_hunter.planner import PlanningState


def render_report(console: Console, state: PlanningState, report: OptimizationReport) -> None:
    if report.status == "incomplete":
        console.print("[bold red]Trip data collection is incomplete.[/bold red]")
        if report.missing_buckets:
            console.print("Missing buckets:")
            for bucket in report.missing_buckets:
                console.print(f"  - {bucket}")
        for note in report.notes:
            console.print(note)
        return

    for itinerary in report.itineraries:
        console.rule(f"[bold]{itinerary.label}[/bold]")
        headroom = state.spec.budget - itinerary.total_cost
        status = "under" if headroom >= 0 else "over"
        console.print(
            f"Total: ${itinerary.total_cost:,.0f} vs ${state.spec.budget:,.0f} budget "
            f"({abs(headroom):,.0f} {status})"
        )

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Category")
        table.add_column("Name")
        table.add_column("Timing / Details")
        table.add_column("Price", justify="right")

        for match in state.spec.matches:
            ticket = itinerary.tickets[match.id]
            table.add_row(
                "Ticket",
                f"{match.event_name} ({ticket.source})",
                f"{ticket.tier} {ticket.section or ''}".strip(),
                f"${ticket.total_price:,.0f}",
            )

        route_plan = state.ensure_route_plan()
        for leg in route_plan.legs:
            flight = itinerary.flights[leg.id]
            table.add_row(
                "Flight",
                f"{leg.origin_label} -> {leg.destination_label} ({flight.carrier})",
                f"{flight.depart_at.strftime('%Y-%m-%d %H:%M')} to {flight.arrive_at.strftime('%Y-%m-%d %H:%M')}, {flight.layovers} layovers",
                f"${flight.total_price:,.0f}",
            )

        for stay in route_plan.stays:
            hotel = itinerary.hotels[stay.id]
            rating = f"{hotel.rating:.1f}" if hotel.rating is not None else "n/a"
            table.add_row(
                "Hotel",
                f"{hotel.name} ({hotel.source})",
                f"{stay.city}, {hotel.nights} nights, rating {rating}",
                f"${hotel.total_price:,.0f}",
            )

        console.print(table)
        console.print(itinerary.reasoning)

    if report.dropped_matches:
        pieces = []
        for dropped in report.dropped_matches:
            price = (
                f"${dropped.approximate_restore_cost:,.0f}"
                if dropped.approximate_restore_cost is not None
                else "unknown cost"
            )
            pieces.append(f"{dropped.event_name} (restore approx. {price})")
        console.print()
        console.print("Dropped matches: " + "; ".join(pieces))
    else:
        console.print()
        console.print("Dropped matches: none")
