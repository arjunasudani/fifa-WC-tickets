const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

let demoData;
let countriesData;
let scheduleData;
let activeCountry = "US";
let activeIndex = 0;

const $ = (selector) => document.querySelector(selector);

async function loadDemo() {
  const countriesResponse = await fetch("/api/countries");
  countriesData = await countriesResponse.json();
  renderCountries();
  await loadSchedule(activeCountry);
  await planSelectedMatches();
}

function renderCountries() {
  $("#country-select").innerHTML = countriesData.countries
    .map(
      (country) => `
        <option value="${escapeHtml(country.code)}" ${country.code === activeCountry ? "selected" : ""}>
          ${escapeHtml(country.name)}
        </option>
      `,
    )
    .join("");
  $("#country-select").addEventListener("change", async (event) => {
    activeCountry = event.target.value;
    await loadSchedule(activeCountry);
    await planSelectedMatches();
  });
  $("#plan-selected").addEventListener("click", planSelectedMatches);
}

async function loadSchedule(countryCode) {
  const response = await fetch(`/api/schedule?country=${encodeURIComponent(countryCode)}`);
  scheduleData = await response.json();
  renderSchedule();
}

function renderSchedule() {
  $("#schedule-count").textContent = `${scheduleData.matches.length} matches in ${scheduleData.country.name}`;
  $("#schedule-results").innerHTML = scheduleData.matches
    .map(
      (match) => `
        <tr>
          <td>
            <input type="checkbox" data-match-id="${escapeHtml(match.id)}" checked aria-label="Select ${escapeHtml(match.event_name)}" />
          </td>
          <td>${formatDateTime(match.date)}</td>
          <td>
            <strong>${escapeHtml(match.away_team)}</strong>
            <span>at ${escapeHtml(match.home_team)}</span>
          </td>
          <td>${escapeHtml(match.venue)}<br /><span>${escapeHtml(match.city)}</span></td>
          <td>${match.priority}</td>
        </tr>
      `,
    )
    .join("");
}

async function planSelectedMatches() {
  const selectedIds = Array.from(document.querySelectorAll("[data-match-id]:checked"))
    .map((input) => input.dataset.matchId)
    .filter(Boolean);
  const ids = selectedIds.length ? selectedIds : scheduleData.matches.map((match) => match.id);
  const params = new URLSearchParams({ country: activeCountry });
  for (const id of ids) {
    params.append("match_id", id);
  }
  $("#plan-selected").disabled = true;
  $("#run-status").textContent = "Planning itinerary";
  const response = await fetch(`/api/plan?${params.toString()}`);
  demoData = await response.json();
  activeIndex = 0;
  renderShell();
  renderTabs();
  renderItinerary(0);
  renderRoute();
  renderTradeoffs();
  $("#plan-selected").disabled = false;
}

function renderShell() {
  const spec = demoData.original_spec;
  const selectedIds = new Set(demoData.selected_match_ids);
  const best = demoData.report.itineraries[0];
  const dropped = demoData.report.dropped_matches;
  const headroom = spec.budget - best.total_cost;

  $("#run-status").textContent = `Planned ${new Date(demoData.generated_at).toLocaleTimeString()}`;
  $("#mode-pill").textContent = demoData.mode.replace("_", " ");
  $("#budget").textContent = money.format(spec.budget);
  $("#best-total").textContent = money.format(best.total_cost);
  $("#headroom").textContent = money.format(headroom);
  $("#dropped-count").textContent = String(dropped.length);
  $("#origin").textContent = spec.origin;
  $("#travelers").textContent = String(spec.constraints.travelers_count);
  $("#constraints").textContent = [
    `${spec.constraints.max_layovers ?? "any"} max layovers`,
    `${spec.constraints.min_hotel_rating ?? "any"}+ hotel rating`,
    `${spec.constraints.ticket_tier_preference} seats`,
  ].join(" / ");

  $("#match-list").innerHTML = spec.matches
    .map((match) => {
      const isSelected = selectedIds.has(match.id);
      return `
        <article class="match-item ${isSelected ? "" : "dropped"}">
          <div class="match-title">
            <span>${escapeHtml(match.event_name)}</span>
            <span class="tag ${isSelected ? "" : "dropped"}">${isSelected ? "Kept" : "Dropped"}</span>
          </div>
          <div class="match-meta">
            ${escapeHtml(match.venue)}, ${escapeHtml(match.city)}<br />
            ${formatDateTime(match.kickoff_at)} / priority ${match.priority}
          </div>
        </article>
      `;
    })
    .join("");
}

function renderTabs() {
  $("#itinerary-tabs").innerHTML = demoData.report.itineraries
    .map(
      (itinerary, index) => `
        <button class="${index === activeIndex ? "active" : ""}" data-index="${index}" type="button">
          ${escapeHtml(itinerary.label)}
        </button>
      `,
    )
    .join("");
  for (const button of document.querySelectorAll("#itinerary-tabs button")) {
    button.addEventListener("click", () => renderItinerary(Number(button.dataset.index)));
  }
}

function renderItinerary(index) {
  activeIndex = index;
  renderTabs();
  const itinerary = demoData.report.itineraries[index];
  const rows = [
    ...ticketRows(itinerary),
    ...flightRows(itinerary),
    ...hotelRows(itinerary),
  ];
  $("#itinerary-detail").innerHTML = `
    <div class="itinerary-heading">
      <div>
        <h3>${escapeHtml(itinerary.label)}</h3>
        <p class="reasoning">${escapeHtml(itinerary.reasoning)}</p>
      </div>
      <strong>${money.format(itinerary.total_cost)}</strong>
    </div>
    <table class="breakdown">
      <thead>
        <tr>
          <th>Type</th>
          <th>Option</th>
          <th>Details</th>
          <th>Price</th>
        </tr>
      </thead>
      <tbody>
        ${rows.join("")}
      </tbody>
    </table>
  `;
}

function ticketRows(itinerary) {
  return demoData.selected_spec.matches.map((match) => {
    const ticket = itinerary.tickets[match.id];
    return row(
      "Ticket",
      `${match.event_name} (${ticket.source})`,
      `${ticket.tier} ${ticket.section ?? ""}`.trim(),
      ticket.total_price,
    );
  });
}

function flightRows(itinerary) {
  return demoData.route_plan.legs.map((leg) => {
    const flight = itinerary.flights[leg.id];
    return row(
      "Flight",
      `${leg.origin_label} to ${leg.destination_label} (${flight.carrier})`,
      `${formatDateTime(flight.depart_at)} to ${formatDateTime(flight.arrive_at)}, ${flight.layovers} layovers`,
      flight.total_price,
    );
  });
}

function hotelRows(itinerary) {
  return demoData.route_plan.stays.map((stay) => {
    const hotel = itinerary.hotels[stay.id];
    return row(
      "Hotel",
      `${hotel.name} (${hotel.source})`,
      `${stay.city}, ${hotel.nights} nights, rating ${hotel.rating ?? "n/a"}`,
      hotel.total_price,
    );
  });
}

function row(type, name, details, price) {
  return `
    <tr>
      <td>${escapeHtml(type)}</td>
      <td>${escapeHtml(name)}</td>
      <td>${escapeHtml(details)}</td>
      <td>${money.format(price)}</td>
    </tr>
  `;
}

function renderRoute() {
  const legs = demoData.route_plan.legs.map((leg) => `
    <div class="timeline-item">
      <div class="timeline-label">Flight</div>
      <div class="timeline-body">
        <strong>${escapeHtml(leg.origin_label)} to ${escapeHtml(leg.destination_label)}</strong>
        <span>${formatDate(leg.depart_on)}</span>
      </div>
    </div>
  `);
  const stays = demoData.route_plan.stays.map((stay) => `
    <div class="timeline-item">
      <div class="timeline-label">Stay</div>
      <div class="timeline-body">
        <strong>${escapeHtml(stay.city)}</strong>
        <span>${formatDate(stay.check_in)} to ${formatDate(stay.check_out)} near ${escapeHtml(stay.venue)}</span>
      </div>
    </div>
  `);
  $("#route-timeline").innerHTML = [...legs, ...stays].join("");
}

function renderTradeoffs() {
  const dropped = demoData.report.dropped_matches;
  const paragraphs = demoData.report.itineraries.map((itinerary) => `
    <div class="tradeoff-item">
      <strong>${escapeHtml(itinerary.label)}:</strong>
      ${escapeHtml(itinerary.reasoning)}
    </div>
  `);
  const droppedText = dropped.length
    ? dropped
        .map((match) => `${match.event_name} can be restored for about ${money.format(match.approximate_restore_cost)}.`)
        .join(" ")
    : "No matches were dropped for this run.";
  $("#tradeoffs").innerHTML = `${paragraphs.join("")}<p>${escapeHtml(droppedText)}</p>`;
}

function formatDate(value) {
  return new Date(`${value}T12:00:00`).toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatDateTime(value) {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadDemo().catch((error) => {
  $("#run-status").textContent = "Demo failed";
  $("#itinerary-detail").innerHTML = `<p class="reasoning">${escapeHtml(error.message)}</p>`;
});
