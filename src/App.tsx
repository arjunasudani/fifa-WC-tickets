import { useEffect, useMemo, useState } from "react";

import { PromptInputBox } from "./components/ui/ai-prompt-box";

type Country = {
  code: string;
  name: string;
  group?: string;
  is_all?: boolean;
};

type Match = {
  id: string;
  match_number: number;
  event_name: string;
  team: string;
  opponent: string;
  home_team: string;
  away_team: string;
  city: string;
  venue: string;
  date: string;
  group: string;
  competition: string;
  source: string;
  priority: number;
};

type ScoutingReport = {
  name: string;
  age: number | null;
  club: string;
  country: string;
  position: string;
  emergence_score: number | null;
  book_flight_to: string;
  travel_date: string | null;
  watch_team: string;
  next_opponent: string;
  next_game_venue: string;
  competition: string;
  fixture_source: string;
  why_emerging: string;
  risk_factors: string;
  watch_next: string;
  source: string;
};

type SchedulePayload = {
  country: Country;
  matches: Match[];
  scouting: ScoutingReport[];
};

type Itinerary = {
  label: string;
  total_cost: number;
  reasoning: string;
  tickets: Record<string, { source: string; total_price: number; tier: string; section?: string }>;
  flights: Record<
    string,
    {
      carrier: string;
      total_price: number;
      depart_at: string;
      arrive_at: string;
      layovers: number;
    }
  >;
  hotels: Record<
    string,
    { name: string; source: string; total_price: number; nights: number; rating?: number }
  >;
};

type PlanPayload = {
  generated_at: string;
  original_spec: {
    budget: number;
    origin: string;
    matches: Array<{
      id: string;
      event_name: string;
      city: string;
      venue: string;
      kickoff_at: string;
      priority: number;
    }>;
  };
  selected_spec: {
    matches: Array<{ id: string; event_name: string }>;
  };
  selected_match_ids: string[];
  route_plan: {
    legs: Array<{
      id: string;
      origin_label: string;
      destination_label: string;
      depart_on: string;
    }>;
    stays: Array<{
      id: string;
      city: string;
      venue: string;
      check_in: string;
      check_out: string;
    }>;
  };
  report: {
    itineraries: Itinerary[];
    dropped_matches: Array<{
      event_name: string;
      approximate_restore_cost: number;
    }>;
  };
};

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function App() {
  const [countries, setCountries] = useState<Country[]>([]);
  const [activeCountry, setActiveCountry] = useState("united-states");
  const [schedule, setSchedule] = useState<SchedulePayload | null>(null);
  const [plan, setPlan] = useState<PlanPayload | null>(null);
  const [activeItineraryIndex, setActiveItineraryIndex] = useState(0);
  const [selectedMatchIds, setSelectedMatchIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadCountries();
  }, []);

  useEffect(() => {
    if (countries.length > 0 && !schedule) void loadSchedule(activeCountry);
  }, [countries.length, schedule]);

  async function loadCountries() {
    const response = await fetch("/api/countries");
    const payload = (await response.json()) as { countries: Country[] };
    setCountries(payload.countries);
  }

  async function loadSchedule(query: string) {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/schedule?country=${encodeURIComponent(query)}`);
      const payload = (await response.json()) as SchedulePayload;
      setSchedule(payload);
      setActiveCountry(payload.country.code);
      const defaultMatchCount = payload.country.is_all ? 3 : payload.matches.length;
      const nextIds = payload.matches.slice(0, defaultMatchCount).map((match) => match.id);
      setSelectedMatchIds(nextIds);
      await loadPlan(payload.country.code, nextIds);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Search failed");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadPlan(countryCode: string, matchIds: string[]) {
    const params = new URLSearchParams({ country: countryCode });
    for (const id of matchIds) params.append("match_id", id);
    const response = await fetch(`/api/plan?${params.toString()}`);
    const payload = (await response.json()) as PlanPayload;
    setPlan(payload);
    setActiveItineraryIndex(0);
  }

  async function handlePrompt(message: string) {
    await loadSchedule(cleanPromptMessage(message));
  }

  async function handlePlanSelected() {
    if (!schedule) return;
    setIsLoading(true);
    setError(null);
    try {
      await loadPlan(
        schedule.country.code,
        selectedMatchIds.length ? selectedMatchIds : schedule.matches.slice(0, 3).map((m) => m.id),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Planning failed");
    } finally {
      setIsLoading(false);
    }
  }

  const selectedIds = useMemo(() => new Set(plan?.selected_match_ids ?? []), [plan]);
  const itinerary = plan?.report.itineraries[activeItineraryIndex];
  const best = plan?.report.itineraries[0];
  const headroom = plan && best ? plan.original_spec.budget - best.total_cost : 0;

  return (
    <main className="min-h-screen overflow-hidden bg-[radial-gradient(125%_125%_at_50%_101%,rgba(245,87,2,1)_10.5%,rgba(245,120,2,1)_16%,rgba(245,140,2,1)_17.5%,rgba(245,170,100,1)_25%,rgba(238,174,202,1)_40%,rgba(202,179,214,1)_65%,rgba(148,201,233,1)_100%)] px-4 py-8 text-white">
      <section className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-6xl flex-col items-center justify-center gap-6">
        <div className="w-full max-w-[500px]">
          <PromptInputBox
            isLoading={isLoading}
            placeholder="Search any FIFA 2026 team..."
            onSend={handlePrompt}
          />
        </div>

        <div className="flex max-h-36 max-w-5xl flex-wrap items-center justify-center gap-2 overflow-y-auto rounded-3xl border border-white/15 bg-[#1F2023]/35 p-3">
          {countries.map((country) => (
            <button
              key={country.code}
              onClick={() => void loadSchedule(country.code)}
              className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${
                country.code === activeCountry
                  ? "border-white bg-white text-[#1F2023]"
                  : "border-white/25 bg-[#1F2023]/35 text-white hover:bg-[#1F2023]/55"
              }`}
              type="button"
            >
              {country.name}
              {country.group && <span className="ml-1 text-xs opacity-60">G{country.group}</span>}
            </button>
          ))}
        </div>

        <section className="grid w-full gap-4 rounded-[28px] border border-white/20 bg-[#1F2023]/88 p-4 shadow-[0_24px_80px_rgba(0,0,0,0.3)] backdrop-blur-xl lg:grid-cols-[1.05fr_0.95fr]">
          <div className="min-w-0">
            <div className="mb-3 flex items-end justify-between gap-3">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">
                  {schedule?.country.name ?? "Country"} matches
                </h1>
                <p className="mt-1 text-sm text-white/55">
                  {schedule
                    ? `${schedule.matches.length} FIFA 2026 group-stage result${schedule.matches.length === 1 ? "" : "s"}`
                    : "Loading schedule"}
                </p>
              </div>
              <button
                type="button"
                onClick={handlePlanSelected}
                disabled={isLoading}
                className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-[#1F2023] transition hover:bg-white/85 disabled:opacity-60"
              >
                Plan selected
              </button>
            </div>

            {schedule?.scouting && schedule.scouting.length > 0 && (
              <div className="mb-4 grid gap-2 md:grid-cols-2">
                {schedule.scouting.slice(0, 4).map((report) => (
                  <article
                    key={report.name}
                    className="rounded-2xl border border-amber-200/20 bg-amber-200/[0.08] p-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h2 className="font-semibold text-white">{report.name}</h2>
                        <p className="text-xs text-white/55">
                          {report.position} · {report.club} · {report.country}
                        </p>
                      </div>
                      <strong className="rounded-full bg-white px-2 py-1 text-xs text-[#1F2023]">
                        {report.emergence_score ?? "n/a"}
                      </strong>
                    </div>
                    <p className="mt-2 text-sm leading-5 text-white/70">{report.watch_next}</p>
                    <p className="mt-2 text-xs text-white/45">
                      Travel: {report.book_flight_to || "TBD"}
                      {report.travel_date ? ` · ${formatDate(report.travel_date)}` : ""}
                    </p>
                  </article>
                ))}
              </div>
            )}

            <div className="overflow-x-auto rounded-2xl border border-white/10">
              <table className="w-full min-w-[720px] border-collapse text-left text-sm">
                <thead className="bg-white/[0.06] text-xs uppercase tracking-[0.14em] text-white/50">
                  <tr>
                    <th className="w-14 px-4 py-3">Pick</th>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Match</th>
                    <th className="px-4 py-3">Where</th>
                    <th className="px-4 py-3">Group</th>
                  </tr>
                </thead>
                <tbody>
                  {schedule?.matches.map((match) => (
                    <tr key={match.id} className="border-t border-white/10">
                      <td className="px-4 py-3">
                        <input
                          className="h-4 w-4 accent-white"
                          type="checkbox"
                          checked={selectedMatchIds.includes(match.id)}
                          onChange={(event) => {
                            setSelectedMatchIds((current) =>
                              event.target.checked
                                ? [...current, match.id]
                                : current.filter((id) => id !== match.id),
                            );
                          }}
                        />
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-white/80">
                        {formatDateTime(match.date)}
                      </td>
                      <td className="px-4 py-3">
                        <strong className="block text-white">{match.event_name}</strong>
                        <span className="text-white/50">Match {match.match_number}</span>
                      </td>
                      <td className="px-4 py-3">
                        <strong className="block text-white/85">{match.venue}</strong>
                        <span className="text-white/50">{match.city}</span>
                      </td>
                      <td className="px-4 py-3 text-white/70">
                        Group {match.group}
                        <span className="block text-xs text-white/40">{match.source}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="min-w-0 rounded-2xl border border-white/10 bg-black/15 p-4">
            <div className="grid grid-cols-3 gap-2">
              <Metric label="Budget" value={plan ? money.format(plan.original_spec.budget) : "..."} />
              <Metric label="Best" value={best ? money.format(best.total_cost) : "..."} />
              <Metric label="Headroom" value={plan ? money.format(headroom) : "..."} />
            </div>

            {plan && itinerary && (
              <>
                <div className="mt-4 flex flex-wrap gap-2">
                  {plan.report.itineraries.map((item, index) => (
                    <button
                      key={item.label}
                      type="button"
                      onClick={() => setActiveItineraryIndex(index)}
                      className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${
                        index === activeItineraryIndex
                          ? "border-white bg-white text-[#1F2023]"
                          : "border-white/15 text-white/70"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>

                <div className="mt-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-xl font-semibold">{itinerary.label}</h2>
                      <p className="mt-1 text-sm leading-6 text-white/58">{itinerary.reasoning}</p>
                    </div>
                    <strong className="text-3xl">{money.format(itinerary.total_cost)}</strong>
                  </div>

                  <div className="mt-4 space-y-2 text-sm">
                    {plan.original_spec.matches.map((match) => (
                      <div
                        key={match.id}
                        className={`rounded-xl border px-3 py-2 ${
                          selectedIds.has(match.id)
                            ? "border-emerald-300/30 bg-emerald-300/10"
                            : "border-red-300/25 bg-red-300/10"
                        }`}
                      >
                        <div className="flex justify-between gap-3">
                          <span>{match.event_name}</span>
                          <span className="text-white/55">
                            {selectedIds.has(match.id) ? "Kept" : "Dropped"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.04] p-3 text-sm leading-6 text-white/65">
                    {plan.report.dropped_matches.length > 0
                      ? plan.report.dropped_matches
                          .map(
                            (match) =>
                              `${match.event_name} restore cost: ${money.format(match.approximate_restore_cost)}.`,
                          )
                          .join(" ")
                      : "No matches dropped for this run."}
                  </div>
                </div>
              </>
            )}

            {error && <p className="mt-3 text-sm text-red-200">{error}</p>}
          </div>
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-3">
      <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-white/45">
        {label}
      </span>
      <strong className="mt-1 block text-lg">{value}</strong>
    </div>
  );
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function cleanPromptMessage(message: string) {
  const match = message.match(/^\[(Search|Think|Canvas):\s*(.*)\]$/);
  return match ? match[2] : message;
}

export default App;
