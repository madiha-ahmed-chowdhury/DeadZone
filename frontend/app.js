// DeadZone coordinator dashboard — plain JS, no build step.
// Talks to the FastAPI backend over HTTP (polling) with an optional
// WebSocket upgrade to /ws/pulses when the backend has Supabase Realtime
// configured. Falls back to polling automatically otherwise.

const DEFAULTS = {
  apiUrl: window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : "",
  apiKey: "",
};

const POLL_MS = 5000;
const DEAD_ZONE_MS = 60 * 60 * 1000;   // 60 min silence = dead zone
const STALE_MS = 15 * 60 * 1000;       // 15 min silence = stale

// ---------- Config (persisted locally in the browser only) ----------

function loadConfig() {
  return {
    apiUrl: localStorage.getItem("deadzone.apiUrl") || DEFAULTS.apiUrl,
    apiKey: localStorage.getItem("deadzone.apiKey") || DEFAULTS.apiKey,
  };
}
function saveConfig(cfg) {
  localStorage.setItem("deadzone.apiUrl", cfg.apiUrl);
  localStorage.setItem("deadzone.apiKey", cfg.apiKey);
}

let config = loadConfig();

// ---------- Settings panel ----------

const settingsPanel = document.getElementById("settings-panel");
const settingsBtn = document.getElementById("settings-btn");
document.getElementById("cfg-api-url").value = config.apiUrl;
document.getElementById("cfg-api-key").value = config.apiKey;

settingsBtn.addEventListener("click", () => {
  document.getElementById("cfg-api-url").value = config.apiUrl;
  document.getElementById("cfg-api-key").value = config.apiKey;
  settingsPanel.classList.remove("hidden");
});
document.getElementById("cfg-cancel").addEventListener("click", () => {
  settingsPanel.classList.add("hidden");
});
document.getElementById("cfg-save").addEventListener("click", () => {
  config.apiUrl = document.getElementById("cfg-api-url").value.trim().replace(/\/$/, "");
  config.apiKey = document.getElementById("cfg-api-key").value.trim();
  saveConfig(config);
  settingsPanel.classList.add("hidden");
  refreshAll();
});

if (!config.apiUrl) {
  settingsPanel.classList.remove("hidden");
}

// ---------- Map setup ----------

const map = L.map("map", { zoomControl: true, attributionControl: false }).setView([23.7, 90.35], 7);
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  subdomains: "abcd",
  maxZoom: 18,
}).addTo(map);

let hexLayer = L.layerGroup().addTo(map);
let pulseLayer = L.layerGroup().addTo(map);

function colorForAge(ageMs) {
  if (ageMs > DEAD_ZONE_MS) return "#f1495a";
  if (ageMs > STALE_MS) return "#fdba45";
  return "#3ddc84";
}

function renderHexes(hexes) {
  hexLayer.clearLayers();
  const now = Date.now();
  let deadCount = 0;

  hexes.forEach((h) => {
    const ageMs = now - new Date(h.last_pulse_at).getTime();
    const color = colorForAge(ageMs);
    if (ageMs > DEAD_ZONE_MS) deadCount += 1;

    let boundary;
    try {
      boundary = h3.cellToBoundary(h.h3_cell, true); // [lng, lat] pairs, geoJson order
    } catch (e) {
      return; // unknown cell id shape — skip rather than crash the map
    }
    const latlngs = boundary.map(([lng, lat]) => [lat, lng]);

    L.polygon(latlngs, {
      color,
      weight: 1,
      fillColor: color,
      fillOpacity: ageMs > DEAD_ZONE_MS ? 0.35 : 0.22,
    })
      .bindPopup(
        `<strong>${h.pulse_count}</strong> pulse(s)<br/>Last signal: ${new Date(
          h.last_pulse_at
        ).toLocaleString()}`
      )
      .addTo(hexLayer);
  });

  document.getElementById("stat-dead-zones").textContent = deadCount;
}

function renderPulses(pulses) {
  pulseLayer.clearLayers();
  pulses.slice(0, 200).forEach((p) => {
    if (p.lat == null || p.lng == null) return;
    L.circleMarker([p.lat, p.lng], {
      radius: 3,
      color: "#3ddc84",
      fillColor: "#3ddc84",
      fillOpacity: 0.9,
      weight: 0,
    })
      .bindPopup(
        `<strong>${p.place_text || "Unknown location"}</strong><br/>${new Date(
          p.created_at
        ).toLocaleString()}`
      )
      .addTo(pulseLayer);
  });
  document.getElementById("stat-pulses").textContent = pulses.length;
}

// ---------- Needs queue ----------

const needsList = document.getElementById("needs-list");
const filterCategory = document.getElementById("filter-category");
const filterStatus = document.getElementById("filter-status");

const STATUS_FLOW = ["open", "acknowledged", "dispatched", "fulfilled"];
const STATUS_LABEL = {
  open: "Open",
  acknowledged: "Ack",
  dispatched: "Dispatch",
  fulfilled: "Fulfilled",
};

function needCard(n) {
  const card = document.createElement("div");
  card.className = `need-card priority-${n.priority} category-${n.category}${
    n.urgent ? " urgent" : ""
  }`;

  const actionsDisabled = !config.apiKey;
  const actionsHtml = STATUS_FLOW.map((s) => {
    const isActive = n.status === s;
    return `<button data-need="${n.id}" data-status="${s}" class="${
      isActive ? "active" : ""
    }" ${actionsDisabled ? "disabled" : ""} title="${
      actionsDisabled ? "Set a coordinator key in settings to update status" : ""
    }">${STATUS_LABEL[s]}</button>`;
  }).join("");

  card.innerHTML = `
    <div class="need-top">
      <span class="need-category">${n.category}</span>
      <span class="need-priority">P${n.priority}</span>
    </div>
    <div class="need-text">${escapeHtml(n.need_text)}</div>
    <div class="need-place">${escapeHtml(n.place_text || "Unknown location")} · ${new Date(
    n.created_at
  ).toLocaleTimeString()}</div>
    ${n.urgent ? `<span class="need-urgent-tag">URGENT</span>` : ""}
    <div class="need-actions">${actionsHtml}</div>
  `;
  return card;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function renderNeeds(needs) {
  needsList.innerHTML = "";
  if (needs.length === 0) {
    needsList.innerHTML = `<div class="empty-state">No matching reports yet.</div>`;
    return;
  }
  needs.forEach((n) => needsList.appendChild(needCard(n)));

  needsList.querySelectorAll("button[data-need]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.need;
      const status = btn.dataset.status;
      try {
        await api(`/api/v1/needs/${id}/status`, {
          method: "PATCH",
          body: JSON.stringify({ status }),
        });
        fetchNeeds();
      } catch (e) {
        alert(`Couldn't update status: ${e.message}`);
      }
    });
  });
}

// ---------- API helpers ----------

async function api(path, opts = {}) {
  if (!config.apiUrl) throw new Error("Set the API base URL in settings first.");
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (config.apiKey) headers["X-API-Key"] = config.apiKey;

  const res = await fetch(config.apiUrl + path, { ...opts, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch (_) {}
    throw new Error(`${res.status} ${detail}`);
  }
  return res.status === 204 ? null : res.json();
}

async function fetchPulsesAndHexes() {
  const [pulses, hexes] = await Promise.all([
    api("/api/v1/pulses?limit=500"),
    api("/api/v1/hexes"),
  ]);
  renderPulses(pulses);
  renderHexes(hexes);
}

async function fetchNeeds() {
  const params = new URLSearchParams();
  if (filterCategory.value) params.set("category", filterCategory.value);
  if (filterStatus.value) params.set("status", filterStatus.value);
  params.set("limit", "200");

  const needs = await api(`/api/v1/needs?${params.toString()}`);
  renderNeeds(needs);

  const openCount = filterStatus.value
    ? needs.length
    : needs.filter((n) => n.status === "open").length;
  document.getElementById("stat-open-needs").textContent = openCount;
}

async function refreshAll() {
  try {
    await Promise.all([fetchPulsesAndHexes(), fetchNeeds()]);
    setConnState(wsConnected ? "live" : "polling");
  } catch (e) {
    setConnState("down", e.message);
  }
}

filterCategory.addEventListener("change", fetchNeeds);
filterStatus.addEventListener("change", fetchNeeds);

// ---------- Connection status + optional realtime upgrade ----------

const connDot = document.getElementById("conn-dot");
const connLabel = document.getElementById("conn-label");
let wsConnected = false;

function setConnState(state, detail) {
  connDot.className = "dot " + (state === "live" ? "live" : state === "down" ? "down" : "polling");
  connLabel.textContent =
    state === "live" ? "live" : state === "down" ? `offline${detail ? " — " + detail : ""}` : "polling";
}

function tryWebSocket() {
  if (!config.apiUrl) return;
  let wsUrl;
  try {
    wsUrl = config.apiUrl.replace(/^http/, "ws") + "/ws/pulses";
  } catch (e) {
    return;
  }
  let ws;
  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    return;
  }
  ws.onopen = () => {
    wsConnected = true;
    setConnState("live");
  };
  ws.onmessage = (evt) => {
    // Any pulse.created event is a cue to re-pull the map layers immediately
    // rather than parsing the payload ourselves — keeps this client simple
    // and correct even if the event shape changes upstream.
    try {
      const msg = JSON.parse(evt.data);
      if (msg.type === "pulse.created") fetchPulsesAndHexes();
    } catch (_) {}
  };
  ws.onclose = () => {
    wsConnected = false;
    setConnState("polling");
    setTimeout(tryWebSocket, 8000); // retry later; polling covers us meanwhile
  };
  ws.onerror = () => ws.close();
}

// ---------- Boot ----------

refreshAll();
tryWebSocket();
setInterval(refreshAll, POLL_MS);
