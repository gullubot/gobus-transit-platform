/**
 * GoBus Demo Simulator — Mission Control Single Page Application
 * Pure Vanilla ES6 JavaScript (Zero dependencies, Zero CDN)
 */

(function () {
  "use strict";

  // Configuration
  const POLL_STATUS_INTERVAL_MS = 800;
  const POLL_HEALTH_INTERVAL_MS = 3000;

  // State cache
  let currentLifecycle = "IDLE";
  let scenariosCache = {};
  let selectedScenarioName = "full_demo";

  // DOM Elements
  const elBackendStatusPill = document.getElementById("backend-status-pill");
  const elBackendStatusText = document.getElementById("backend-status-text");
  const elBackendLatency = document.getElementById("backend-latency");

  const elLifecyclePill = document.getElementById("simulator-lifecycle-pill");
  const elLifecycleText = document.getElementById("simulator-lifecycle-text");
  const elSimClock = document.getElementById("sim-clock-display");

  const elScenarioSelect = document.getElementById("scenario-select");
  const elScenarioName = document.getElementById("scenario-name");
  const elScenarioDesc = document.getElementById("scenario-desc");
  const elScenarioBuses = document.getElementById("scenario-buses");
  const elScenarioDuration = document.getElementById("scenario-duration");
  const elValidationBanner = document.getElementById("validation-banner");
  const elValidationText = document.getElementById("validation-text");

  const elTimeMultiplier = document.getElementById("time-multiplier");
  const elTickInterval = document.getElementById("tick-interval");

  const elBtnStart = document.getElementById("btn-start");
  const elBtnPause = document.getElementById("btn-pause");
  const elBtnResume = document.getElementById("btn-resume");
  const elBtnStop = document.getElementById("btn-stop");
  const elBtnReset = document.getElementById("btn-reset");

  const elTimelineContainer = document.getElementById("timeline-container");
  const elFleetCount = document.getElementById("fleet-count");
  const elFleetGrid = document.getElementById("fleet-grid");
  const elEventLogContainer = document.getElementById("event-log-container");

  const elMetricPktsSent = document.getElementById("metric-pkts-sent");
  const elMetricPktsAck = document.getElementById("metric-pkts-ack");
  const elMetricPktsRej = document.getElementById("metric-pkts-rej");
  const elMetricHeartbeats = document.getElementById("metric-heartbeats");
  const elMetricCrowding = document.getElementById("metric-crowding");
  const elMetricTicks = document.getElementById("metric-ticks");

  const elResetModal = document.getElementById("reset-modal");
  const elModalCancelBtn = document.getElementById("modal-cancel-btn");
  const elModalConfirmBtn = document.getElementById("modal-confirm-btn");

  // --------------------------------------------------------------------------
  // API Fetch Helpers
  // --------------------------------------------------------------------------

  async function apiGet(endpoint) {
    try {
      const resp = await fetch(endpoint, { method: "GET" });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }
      return await resp.json();
    } catch (err) {
      console.warn(`API GET error on ${endpoint}:`, err);
      return null;
    }
  }

  async function apiPost(endpoint, body = {}) {
    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await resp.json().catch(() => ({}));
      return { ok: resp.ok, status: resp.status, data };
    } catch (err) {
      console.error(`API POST error on ${endpoint}:`, err);
      return { ok: false, status: 0, data: { error: err.message } };
    }
  }

  // --------------------------------------------------------------------------
  // Initialization
  // --------------------------------------------------------------------------

  async function init() {
    bindEvents();
    await loadScenarios();
    await pollHealth();
    await pollStatus();

    setInterval(pollStatus, POLL_STATUS_INTERVAL_MS);
    setInterval(pollHealth, POLL_HEALTH_INTERVAL_MS);
  }

  function bindEvents() {
    elScenarioSelect.addEventListener("change", onScenarioSelectChange);

    elBtnStart.addEventListener("click", onStartClick);
    elBtnPause.addEventListener("click", onPauseClick);
    elBtnResume.addEventListener("click", onResumeClick);
    elBtnStop.addEventListener("click", onStopClick);
    elBtnReset.addEventListener("click", onResetClick);

    elModalCancelBtn.addEventListener("click", () => {
      elResetModal.style.display = "none";
    });

    elModalConfirmBtn.addEventListener("click", async () => {
      elResetModal.style.display = "none";
      await executeReset(true);
    });
  }

  // --------------------------------------------------------------------------
  // Scenario Loading & Selection
  // --------------------------------------------------------------------------

  async function loadScenarios() {
    const list = await apiGet("/api/scenarios");
    if (!list || !Array.isArray(list)) return;

    elScenarioSelect.innerHTML = "";
    list.forEach((sc) => {
      scenariosCache[sc.name] = sc;
      const opt = document.createElement("option");
      opt.value = sc.name;
      opt.textContent = `${sc.name} (${sc.bus_count} bus${sc.bus_count > 1 ? "es" : ""}, ${sc.duration_s}s)`;
      if (sc.name === selectedScenarioName) {
        opt.selected = true;
      }
      elScenarioSelect.appendChild(opt);
    });

    await updateSelectedScenarioCard(elScenarioSelect.value);
  }

  async function onScenarioSelectChange(e) {
    selectedScenarioName = e.target.value;
    await updateSelectedScenarioCard(selectedScenarioName);
  }

  async function updateSelectedScenarioCard(name) {
    const sc = scenariosCache[name];
    if (sc) {
      elScenarioName.textContent = sc.name;
      elScenarioDesc.textContent = sc.description || "Deterministic transit demo scenario.";
      elScenarioBuses.textContent = sc.bus_count;
      elScenarioDuration.textContent = `${sc.duration_s}s`;
    }

    // Validate scenario offline
    const valResp = await apiPost("/api/scenarios/validate", { scenario: name });
    if (valResp.ok && valResp.data.valid) {
      elValidationBanner.className = "validation-banner";
      elValidationBanner.innerHTML = `<span class="valid-icon">&check;</span> Valid Scenario Configuration`;
    } else {
      elValidationBanner.className = "validation-banner invalid";
      const errStr = valResp.data && valResp.data.errors ? valResp.data.errors.join("; ") : "Invalid configuration";
      elValidationBanner.innerHTML = `<span class="valid-icon">&cross;</span> ${errStr}`;
    }

    // Load detailed timeline preview
    const detail = await apiGet(`/api/scenarios/${name}`);
    if (detail && detail.events) {
      renderTimelinePreview(detail.events);
    }
  }

  // --------------------------------------------------------------------------
  // Action Handlers
  // --------------------------------------------------------------------------

  async function onStartClick() {
    const scenario = elScenarioSelect.value;
    const timeMultiplier = parseFloat(elTimeMultiplier.value) || 1.0;
    const tickSeconds = parseFloat(elTickInterval.value) || 1.0;

    elBtnStart.disabled = true;
    const resp = await apiPost("/api/simulation/start", {
      scenario: scenario,
      time_multiplier: timeMultiplier,
      tick_seconds: tickSeconds,
    });

    if (!resp.ok) {
      alert(`Simulation failed to start: ${resp.data.error || "Conflict"}`);
      elBtnStart.disabled = false;
    }
    await pollStatus();
  }

  async function onPauseClick() {
    elBtnPause.disabled = true;
    const resp = await apiPost("/api/simulation/pause");
    if (!resp.ok) {
      alert(`Pause failed: ${resp.data.error}`);
    }
    await pollStatus();
  }

  async function onResumeClick() {
    elBtnResume.disabled = true;
    const resp = await apiPost("/api/simulation/resume");
    if (!resp.ok) {
      alert(`Resume failed: ${resp.data.error}`);
    }
    await pollStatus();
  }

  async function onStopClick() {
    elBtnStop.disabled = true;
    const resp = await apiPost("/api/simulation/stop");
    if (!resp.ok) {
      alert(`Stop failed: ${resp.data.error}`);
    }
    await pollStatus();
  }

  async function onResetClick() {
    if (currentLifecycle === "RUNNING" || currentLifecycle === "PAUSED") {
      // Require explicit confirmation modal for active simulations
      elResetModal.style.display = "flex";
    } else {
      // Clean local reset without modal
      await executeReset(false);
    }
  }

  async function executeReset(confirmCleanup) {
    elBtnReset.disabled = true;
    const resp = await apiPost("/api/simulation/reset", {
      confirm_backend_cleanup: confirmCleanup,
    });
    if (!resp.ok) {
      alert(`Reset failed: ${resp.data.error}`);
    }
    elBtnReset.disabled = false;
    await pollStatus();
  }

  // --------------------------------------------------------------------------
  // Periodic Pollers & UI Rendering
  // --------------------------------------------------------------------------

  async function pollHealth() {
    const data = await apiGet("/api/health");
    if (data && data.backend) {
      const b = data.backend;
      if (b.connected) {
        elBackendStatusPill.className = "status-pill status-connected";
        elBackendStatusText.textContent = "BACKEND CONNECTED";
        elBackendLatency.textContent = `${b.latency_ms} ms`;
      } else {
        elBackendStatusPill.className = "status-pill status-disconnected";
        elBackendStatusText.textContent = "BACKEND OFFLINE";
        elBackendLatency.textContent = "-- ms";
      }
    } else {
      elBackendStatusPill.className = "status-pill status-disconnected";
      elBackendStatusText.textContent = "SERVER UNREACHABLE";
      elBackendLatency.textContent = "-- ms";
    }
  }

  async function pollStatus() {
    const state = await apiGet("/api/status");
    if (!state) return;

    currentLifecycle = state.lifecycle || "IDLE";
    updateLifecycleBadge(currentLifecycle);
    updateClockDisplay(state.simulation_time_s || 0.0);
    updateActionButtons(currentLifecycle);
    updateFleetGrid(state.fleet || []);
    updateTimeline(state.timeline || []);
    updateMetrics(state.metrics || {}, state.tick_count || 0);
    updateEventLog(state.event_log || []);
  }

  function updateLifecycleBadge(lifecycle) {
    elLifecycleText.textContent = lifecycle;
    elLifecyclePill.className = "status-pill";

    if (lifecycle === "RUNNING") {
      elLifecyclePill.classList.add("status-running");
    } else if (lifecycle === "PAUSED") {
      elLifecyclePill.classList.add("status-paused");
    } else if (lifecycle === "STOPPED" || lifecycle === "IDLE") {
      elLifecyclePill.classList.add("status-idle");
    } else if (lifecycle === "ERROR") {
      elLifecyclePill.classList.add("status-disconnected");
    }
  }

  function updateClockDisplay(simSeconds) {
    const mins = Math.floor(simSeconds / 60);
    const secs = (simSeconds % 60).toFixed(1);
    const padM = String(mins).padStart(2, "0");
    const padS = String(secs).padStart(4, "0");
    elSimClock.textContent = `T+${padM}:${padS}s`;
  }

  function updateActionButtons(lifecycle) {
    if (lifecycle === "RUNNING") {
      elBtnStart.disabled = true;
      elBtnPause.style.display = "inline-flex";
      elBtnPause.disabled = false;
      elBtnResume.style.display = "none";
      elBtnStop.disabled = false;
      elScenarioSelect.disabled = true;
    } else if (lifecycle === "PAUSED") {
      elBtnStart.disabled = true;
      elBtnPause.style.display = "none";
      elBtnResume.style.display = "inline-flex";
      elBtnResume.disabled = false;
      elBtnStop.disabled = false;
      elScenarioSelect.disabled = true;
    } else {
      // IDLE or STOPPED
      elBtnStart.disabled = false;
      elBtnPause.style.display = "inline-flex";
      elBtnPause.disabled = true;
      elBtnResume.style.display = "none";
      elBtnStop.disabled = true;
      elScenarioSelect.disabled = false;
    }
  }

  function updateFleetGrid(buses) {
    elFleetCount.textContent = buses.length;

    if (!buses || buses.length === 0) {
      elFleetGrid.innerHTML = `
        <div class="fleet-empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <p>Fleet is currently idle. Select a scenario and press <strong>START</strong> to begin simulation.</p>
        </div>
      `;
      return;
    }

    let html = "";
    buses.forEach((b) => {
      const badgeClass = `badge-${(b.state || "stopped").toLowerCase()}`;
      const speedStr = `${b.speed_mps} m/s (${b.speed_kmh} km/h)`;
      const dwellStr = b.is_dwelling ? `DWELL (${b.dwell_remaining_s}s)` : "CRUISING";
      const crowdClass = b.crowding_state === "HIGH" || b.crowding_state === "FULL" ? "crowd-high" : "";

      html += `
        <div class="bus-card">
          <div class="bus-header">
            <div class="bus-identity">
              <span class="bus-id">${escapeHtml(b.bus_id)}</span>
              <span class="bus-service">${escapeHtml(b.service_code)} &bull; ${escapeHtml(b.route_name)}</span>
            </div>
            <span class="bus-badge ${badgeClass}">${escapeHtml(b.state)}</span>
          </div>

          <div class="progress-container">
            <div class="progress-labels">
              <span>${escapeHtml(b.current_stop)} &rarr; ${escapeHtml(b.next_stop)}</span>
              <span>${b.progress_percent}%</span>
            </div>
            <div class="progress-track">
              <div class="progress-bar" style="width: ${b.progress_percent}%"></div>
            </div>
          </div>

          <div class="bus-metrics-grid">
            <div class="bus-metric-cell">
              <span class="cell-label">SPEED</span>
              <span class="cell-value">${speedStr}</span>
            </div>
            <div class="bus-metric-cell">
              <span class="cell-label">MOTION</span>
              <span class="cell-value">${dwellStr}</span>
            </div>
            <div class="bus-metric-cell">
              <span class="cell-label">OPERATOR</span>
              <span class="cell-value">${escapeHtml(b.operator)}</span>
            </div>
            <div class="bus-metric-cell">
              <span class="cell-label">VEHICLE</span>
              <span class="cell-value">${escapeHtml(b.vehicle_id)}</span>
            </div>
          </div>

          <div class="bus-sensors">
            <span class="sensor-pill ${b.telemetry_enabled ? 'active' : 'disabled'}">
              TELEMETRY: ${b.telemetry_enabled ? 'ONLINE' : 'OFFLINE'}
            </span>
            <span class="sensor-pill ${b.heartbeat_enabled ? 'active' : 'disabled'}">
              HEARTBEAT: ${b.heartbeat_enabled ? 'ONLINE' : 'DISABLED'}
            </span>
            <span class="sensor-pill ${crowdClass}">
              CROWDING: ${escapeHtml(b.crowding_state)}
            </span>
            <span class="sensor-pill active">
              PACKETS: ${b.packets_sent} (${b.packets_accepted} ACK)
            </span>
          </div>
        </div>
      `;
    });

    elFleetGrid.innerHTML = html;
  }

  function renderTimelinePreview(events) {
    if (!events || events.length === 0) {
      elTimelineContainer.innerHTML = `<div class="timeline-empty">No scheduled events.</div>`;
      return;
    }

    let html = "";
    events.forEach((ev) => {
      const timeStr = `T+${ev.time_s.toFixed(1)}s`;
      html += `
        <div class="timeline-item upcoming">
          <span class="timeline-icon">&cir;</span>
          <span class="timeline-time">${timeStr}</span>
          <span class="timeline-title">${escapeHtml(ev.event_type)}</span>
          <span class="timeline-target">${escapeHtml(ev.target_bus_id)}</span>
        </div>
      `;
    });
    elTimelineContainer.innerHTML = html;
  }

  function updateTimeline(timeline) {
    if (!timeline || timeline.length === 0) return;

    let html = "";
    timeline.forEach((item) => {
      const timeStr = `T+${item.time_s.toFixed(1)}s`;
      let statusClass = "upcoming";
      let icon = "&cir;";

      if (item.status === "COMPLETED") {
        statusClass = "completed";
        icon = "&check;";
      } else if (item.status === "ACTIVE") {
        statusClass = "active";
        icon = "&bull;";
      }

      html += `
        <div class="timeline-item ${statusClass}">
          <span class="timeline-icon">${icon}</span>
          <span class="timeline-time">${timeStr}</span>
          <span class="timeline-title">${escapeHtml(item.event_type)}</span>
          <span class="timeline-target">${escapeHtml(item.target_bus_id)}</span>
        </div>
      `;
    });

    elTimelineContainer.innerHTML = html;
  }

  function updateMetrics(m, tickCount) {
    elMetricPktsSent.textContent = m.packets_generated || 0;
    elMetricPktsAck.textContent = m.packets_accepted || 0;
    elMetricPktsRej.textContent = m.packets_rejected || 0;
    elMetricHeartbeats.textContent = m.heartbeats_sent || 0;
    elMetricCrowding.textContent = m.crowding_reports_sent || 0;
    elMetricTicks.textContent = tickCount || 0;
  }

  function updateEventLog(logs) {
    if (!logs || logs.length === 0) return;

    let html = "";
    logs.forEach((item) => {
      const lvl = item.level || "INFO";
      html += `
        <div class="log-entry log-${lvl}">
          <span class="log-time">[${escapeHtml(item.timestamp)}]</span>
          <span class="log-msg">${escapeHtml(item.message)}</span>
        </div>
      `;
    });

    elEventLogContainer.innerHTML = html;
    elEventLogContainer.scrollTop = elEventLogContainer.scrollHeight;
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Run on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
