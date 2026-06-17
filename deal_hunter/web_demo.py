from __future__ import annotations

import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from deal_hunter.fixtures import seed_demo_candidates
from deal_hunter.models import MatchRequest, TripSpec, dataclass_to_dict
from deal_hunter.planner import PlanningState, optimize_state
from deal_hunter.specs import trim_trip_spec
from deal_hunter.worldcup_db import (
    build_schedule_payload as build_world_cup_schedule_payload,
    ensure_world_cup_database,
    get_plan_matches,
    list_teams,
)


STATIC_DIR = Path(__file__).resolve().parents[1] / "web"
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}

def build_demo_payload(spec: TripSpec) -> dict[str, Any]:
    state = PlanningState(spec)
    seed_demo_candidates(state)
    report = optimize_state(state)
    selected_match_ids: list[str] | None = None

    if report.status == "subset_recommended":
        dropped_matches = report.dropped_matches
        selected_match_ids = report.suggested_subset_match_ids
        state = PlanningState(trim_trip_spec(spec, selected_match_ids))
        seed_demo_candidates(state)
        report = optimize_state(state)
        report.dropped_matches = dropped_matches

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "offline_seeded",
        "original_spec": dataclass_to_dict(spec),
        "selected_match_ids": selected_match_ids
        or [match.id for match in state.spec.matches],
        "selected_spec": dataclass_to_dict(state.spec),
        "route_plan": dataclass_to_dict(state.ensure_route_plan()),
        "report": dataclass_to_dict(report),
    }


def run_web_demo(spec: TripSpec, host: str = "127.0.0.1", port: int = 8765) -> None:
    ensure_world_cup_database()
    payload = build_demo_payload(spec)
    handler = make_handler(payload, spec)
    server = bind_server(handler, host, port)
    actual_host, actual_port = server.server_address[:2]
    print(f"Web demo running at http://{actual_host}:{actual_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def bind_server(
    handler: type[BaseHTTPRequestHandler],
    host: str,
    port: int,
) -> ThreadingHTTPServer:
    for candidate_port in range(port, port + 20):
        try:
            return ThreadingHTTPServer((host, candidate_port), handler)
        except OSError as exc:
            if candidate_port == port + 19:
                raise RuntimeError("Could not bind a local web demo port.") from exc
    raise RuntimeError("Could not bind a local web demo port.")


def make_handler(
    payload: dict[str, Any],
    base_spec: TripSpec,
) -> type[BaseHTTPRequestHandler]:
    class DemoHandler(BaseHTTPRequestHandler):
        def do_HEAD(self) -> None:
            self._handle(send_body=False)

        def do_GET(self) -> None:
            self._handle(send_body=True)

        def _handle(self, *, send_body: bool) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send_file(STATIC_DIR / "index.html", send_body=send_body)
                return
            if parsed.path == "/styles.css":
                self._send_file(STATIC_DIR / "styles.css", send_body=send_body)
                return
            if parsed.path == "/app.js":
                self._send_file(STATIC_DIR / "app.js", send_body=send_body)
                return
            if parsed.path == "/api/demo":
                self._send_json(payload, send_body=send_body)
                return
            if parsed.path == "/api/countries":
                self._send_json(build_countries_payload(), send_body=send_body)
                return
            if parsed.path == "/api/schedule":
                country = first_query_value(parsed.query, "country") or "US"
                self._send_json(build_schedule_payload(country), send_body=send_body)
                return
            if parsed.path == "/api/plan":
                query = parse_qs(parsed.query)
                country = first_from_query(query, "country") or "US"
                match_ids = query.get("match_id") or query.get("match_ids") or []
                if len(match_ids) == 1 and "," in match_ids[0]:
                    match_ids = [item for item in match_ids[0].split(",") if item]
                self._send_json(
                    build_country_plan_payload(base_spec, country, match_ids),
                    send_body=send_body,
                )
                return
            self.send_error(404, "Not found")

        def _send_file(self, path: Path, *, send_body: bool = True) -> None:
            if not path.exists():
                self.send_error(404, "Not found")
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", MIME_TYPES.get(path.suffix, "text/plain"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if send_body:
                self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(
            self,
            value: dict[str, Any],
            *,
            send_body: bool = True,
        ) -> None:
            body = json.dumps(value, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if send_body:
                self.wfile.write(body)

    return DemoHandler


def build_countries_payload() -> dict[str, Any]:
    return {"countries": list_teams()}


def build_schedule_payload(country: str) -> dict[str, Any]:
    return build_world_cup_schedule_payload(country)


def build_country_plan_payload(
    base_spec: TripSpec,
    country: str,
    match_ids: list[str],
) -> dict[str, Any]:
    country_payload, selected_matches = get_plan_matches(country, match_ids)
    spec = TripSpec(
        origin=base_spec.origin,
        budget=base_spec.budget,
        matches=[
            MatchRequest(
                id=match["id"],
                event_name=match["event_name"],
                city=match["city"],
                venue=match["venue"],
                kickoff_at=datetime.fromisoformat(match["date"]),
                priority=int(match.get("priority", 3)),
            )
            for match in selected_matches
        ],
        constraints=base_spec.constraints,
    )
    payload = build_demo_payload(spec)
    payload["search"] = {
        "country": country_payload,
        "requested_match_ids": [match["id"] for match in selected_matches],
    }
    return payload


def first_query_value(query: str, key: str) -> str | None:
    return first_from_query(parse_qs(query), key)


def first_from_query(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0]
