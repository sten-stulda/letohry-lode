const canvas = document.getElementById("raceCanvas");
const context = canvas?.getContext("2d") ?? null;
const appShell = document.querySelector(".app-shell");
const scoreboard = document.getElementById("scoreboard");
const leaderboard = document.getElementById("leaderboard");
const history = document.getElementById("history");
const diagnostics = document.getElementById("diagnostics");
const countdown = document.getElementById("countdown");
const eventLabel = document.getElementById("eventLabel");
const overlayCard = document.getElementById("overlayCard");
const exportCsvButton = document.getElementById("exportCsvButton");
const exportLeaderboardCsvButton = document.getElementById("exportLeaderboardCsvButton");
const exportDiagnosticsButton = document.getElementById("exportDiagnosticsButton");
const clearHistoryButton = document.getElementById("clearHistoryButton");
const searchParams = new URLSearchParams(location.search);

function resolvePerformanceMode() {
  const explicitMode = searchParams.get("performance");
  if (explicitMode === "lite" || explicitMode === "full") {
    return explicitMode;
  }

  const cpuCount = navigator.hardwareConcurrency || 4;
  const raspberryLike = /arm|aarch64|raspberry/i.test(navigator.userAgent);
  return cpuCount <= 4 || raspberryLike ? "lite" : "full";
}

const performanceMode = resolvePerformanceMode();
const isLiteMode = performanceMode === "lite";
const isKioskPage = appShell?.classList.contains("kiosk-shell") ?? false;
const renderSettings = {
  waterBands: isLiteMode ? 7 : 18,
  waterStepX: isLiteMode ? 72 : 40,
  waterStepY: isLiteMode ? 56 : 36,
  waterAmplitude: isLiteMode ? 2.5 : 4,
  targetFps: isLiteMode ? 24 : 60,
  resolutionScale: isLiteMode ? 0.72 : 1,
};

const form = {
  player1: document.getElementById("player1"),
  player2: document.getElementById("player2"),
  distance: document.getElementById("distance"),
  mode: document.getElementById("mode"),
  ghostSource: document.getElementById("ghostSource"),
  theme: document.getElementById("theme"),
  intervalPreset: document.getElementById("intervalPreset"),
  serialPort1: document.getElementById("serialPort1"),
  serialPort2: document.getElementById("serialPort2"),
  useMock: document.getElementById("useMock"),
  startButton: document.getElementById("startButton"),
  resetButton: document.getElementById("resetButton"),
};

let snapshot = {
  status: "idle",
  distance_m: 1000,
  elapsed_s: 0,
  countdown_s: 3,
  lanes: [],
  theme: "river",
  event: "Pripraveno",
  ghost_lane: null,
};

let socket;
let audioContext;
let splashBuffer;
let lastSoundCue = "";
let lastFrameTime = 0;
let lastWaterTick = 0;
let waterPhase = 0;

function populateSerialPortOptions(statusPayload) {
  if (!form.serialPort1 || !form.serialPort2) {
    return;
  }

  const discoveredPorts = statusPayload.discovered_serial_ports || [];
  const configuredPorts = statusPayload.configured_serial_ports || [];
  const selectedPorts = discoveredPorts.length ? discoveredPorts : configuredPorts;
  const options = ['<option value="">Automaticky</option>']
    .concat(selectedPorts.map((port) => `<option value="${port}">${port}</option>`))
    .join("");

  form.serialPort1.innerHTML = options;
  form.serialPort2.innerHTML = options;

  if (configuredPorts[0]) {
    form.serialPort1.value = configuredPorts[0];
  }
  if (configuredPorts[1]) {
    form.serialPort2.value = configuredPorts[1];
  }
}

function syncUsbControls() {
  if (!form.serialPort1 || !form.serialPort2 || !form.useMock) {
    return;
  }

  const disabled = form.useMock.checked;
  form.serialPort1.disabled = disabled;
  form.serialPort2.disabled = disabled;
}

appShell.classList.add(`performance-${performanceMode}`);

function resizeCanvas() {
  if (!canvas) {
    return;
  }
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(320, Math.round(rect.width * renderSettings.resolutionScale));
  const height = Math.max(180, Math.round(rect.height * renderSettings.resolutionScale));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
    drawScene();
  }
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) {
    return "0:00.0";
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds - minutes * 60;
  return `${minutes}:${remainder.toFixed(1).padStart(4, "0")}`;
}

function formatPace(seconds) {
  return `${formatTime(seconds)}/500m`;
}

function formatWatts(watts) {
  return `${Math.round(watts || 0)} W`;
}

function renderPowerMeter(watts) {
  const normalizedWatts = Math.max(0, Math.min(Number(watts) || 0, 500));
  const activeBars = Math.max(1, Math.ceil(normalizedWatts / 62.5));

  return Array.from({ length: 8 }, (_, index) => {
    const activeClass = index < activeBars ? " is-active" : "";
    return `<span class="power-bar${activeClass}" style="--bar-index:${index + 1}"></span>`;
  }).join("");
}

function setTheme(theme) {
  if (!appShell) {
    return;
  }
  appShell.classList.remove("theme-river", "theme-lake", "theme-night");
  appShell.classList.add(`theme-${theme}`);
  appShell.dataset.theme = theme;
}

function renderScoreboard(currentSnapshot = snapshot) {
  if (!scoreboard) {
    return;
  }

  scoreboard.innerHTML = currentSnapshot.lanes
    .map((lane, index) => {
      const gapLabel = lane.rank === 1 ? "Náskok" : "Ztráta";
      const gapValue = `${Math.abs(lane.lead_m).toFixed(1)} m`;
      const boatBadge = `<span class="rank-pill">Kocábka ${index + 1}</span>`;

      return `
        <article class="score-card">
          <div class="score-card-head">
            <h2>${lane.name}</h2>
            ${boatBadge}
          </div>
          <div class="metric-row">
            <div class="metric"><span>Metry</span><strong>${lane.distance_m.toFixed(0)}</strong></div>
            <div class="metric"><span>Tempo</span><strong>${formatPace(lane.pace_per_500_s)}</strong></div>
            <div class="metric"><span>SPM</span><strong>${lane.stroke_rate || 0}</strong></div>
          </div>
          <div class="metric-row">
            <div class="metric"><span>Cas</span><strong>${formatTime(lane.elapsed_s)}</strong></div>
            <div class="metric"><span>${gapLabel}</span><strong>${gapValue}</strong></div>
            <div class="metric"><span>Výkon</span><strong>${formatWatts(lane.watts)}</strong></div>
          </div>
          <div class="power-meter" aria-hidden="true">${renderPowerMeter(lane.watts)}</div>
        </article>
      `;
    })
    .join("");
}

function renderList(element, items, formatter) {
  if (!element) {
    return;
  }
  element.className = "list-card";
  element.innerHTML = items.length
    ? items.map(formatter).join("")
    : '<div class="list-row"><span>Zatim bez dat</span></div>';
}

function drawScene() {
  if (!canvas || !context) {
    return;
  }
  const width = canvas.width;
  const height = canvas.height;
  context.clearRect(0, 0, width, height);

  drawWater(width, height);
  drawTrack(width, height);
  snapshot.lanes.forEach((lane, index) => drawBoat(lane, index, false));
  if (snapshot.ghost_lane) {
    drawBoat(snapshot.ghost_lane, 2, true);
  }
}

function getRenderedLaneCount() {
  return snapshot.ghost_lane ? 3 : Math.max(snapshot.lanes.length, 2);
}

function drawWater(width, height) {
  for (let index = 0; index < renderSettings.waterBands; index += 1) {
    const y = 80 + index * renderSettings.waterStepY;
    context.strokeStyle = `rgba(255,255,255,${0.05 + index * 0.005})`;
    context.lineWidth = isLiteMode ? 1.5 : 2;
    context.beginPath();
    context.moveTo(0, y);
    for (let x = 0; x <= width; x += renderSettings.waterStepX) {
      context.lineTo(
        x,
        y + Math.sin((x + waterPhase + index * 25) / (isLiteMode ? 72 : 60)) * renderSettings.waterAmplitude,
      );
    }
    context.stroke();
  }
}

function drawTrack(width, height) {
  const laneCount = getRenderedLaneCount();
  const laneHeight = height / laneCount;
  for (let laneIndex = 0; laneIndex < laneCount; laneIndex += 1) {
    const top = laneIndex * laneHeight;
    context.strokeStyle = "rgba(255,255,255,0.18)";
    context.setLineDash([12, 10]);
    context.beginPath();
    context.moveTo(50, top + laneHeight - 30);
    context.lineTo(width - 80, top + laneHeight - 30);
    context.stroke();
  }

  context.setLineDash([]);
  context.strokeStyle = "rgba(255,255,255,0.95)";
  context.lineWidth = 6;
  context.beginPath();
  context.moveTo(width - 90, 50);
  context.lineTo(width - 90, height - 50);
  context.stroke();
}

function drawBoat(lane, index, ghost) {
  const width = canvas.width;
  const height = canvas.height;
  const laneCount = getRenderedLaneCount();
  const laneHeight = height / laneCount;
  const centerY = laneHeight * index + laneHeight * 0.58;
  const x = 90 + lane.progress * (width - 220);
  const hullColor = ghost ? "rgba(255,255,255,0.55)" : index === 0 ? "#f9f2de" : "#ffd28b";
  const sailColor = ghost ? "rgba(240,240,255,0.3)" : index === 0 ? "#c95f32" : "#123956";

  context.save();
  context.translate(x, centerY);
  context.fillStyle = "rgba(0,0,0,0.15)";
  context.beginPath();
  context.ellipse(0, 24, 64, 10, 0, 0, Math.PI * 2);
  context.fill();

  context.fillStyle = hullColor;
  context.beginPath();
  context.moveTo(-46, 12);
  context.quadraticCurveTo(-8, 28, 50, 8);
  context.quadraticCurveTo(8, -4, -46, 12);
  context.fill();

  context.fillStyle = sailColor;
  context.beginPath();
  context.moveTo(-10, 0);
  context.lineTo(-10, -50);
  context.lineTo(38, -14);
  context.closePath();
  context.fill();

  context.strokeStyle = "rgba(255,255,255,0.65)";
  context.lineWidth = 4;
  context.beginPath();
  context.moveTo(-10, 8);
  context.lineTo(-10, -50);
  context.stroke();

  context.fillStyle = "rgba(255,255,255,0.95)";
  context.font = `${isLiteMode ? 500 : 600} ${isLiteMode ? 18 : 24}px 'Chakra Petch'`;
  context.fillText(lane.name, -50, -54);
  context.restore();
}

function getWinnerName(currentSnapshot) {
  return (
    currentSnapshot.lanes.find((lane) => lane.lane_id === currentSnapshot.winner_lane)?.name
    ?? currentSnapshot.lanes.find((lane) => lane.rank === 1)?.name
    ?? null
  );
}

function describeEvent(currentSnapshot) {
  const winnerName = getWinnerName(currentSnapshot);
  if (currentSnapshot.status === "finished" && winnerName) {
    return `Vyhrál ${winnerName}`;
  }
  if (currentSnapshot.status === "racing" || currentSnapshot.event === "telemetry") {
    return "";
  }
  if (currentSnapshot.event === "race_started") {
    return "Závod odstartován";
  }
  if (currentSnapshot.event === "countdown") {
    return "Připravit";
  }
  return currentSnapshot.event.replaceAll("_", " ");
}

function updateSnapshot(nextSnapshot) {
  snapshot = nextSnapshot;
  setTheme(snapshot.theme);
  syncFormFromSnapshot(snapshot);
  renderScoreboard();
  drawScene();
  const countdownValue = snapshot.status === "countdown" ? String(snapshot.countdown_s) : snapshot.status === "finished" ? "VÍTĚZ" : "";
  const eventText = describeEvent(snapshot);
  if (countdown) {
    countdown.textContent = countdownValue;
  }
  if (eventLabel) {
    eventLabel.textContent = eventText;
  }
  if (overlayCard) {
    overlayCard.classList.toggle("is-hidden", !countdownValue && !eventText);
  }
}

function syncFormFromSnapshot(currentSnapshot) {
  if (!form.player1 || !form.player2 || !form.distance || !form.mode || !form.theme || !form.ghostSource) {
    return;
  }

  if (currentSnapshot.lanes.length >= 2) {
    form.player1.value = currentSnapshot.lanes[0].name || form.player1.value;
    form.player2.value = currentSnapshot.lanes[1].name || form.player2.value;
  }

  form.distance.value = String(currentSnapshot.distance_m || 1000);
  form.mode.value = currentSnapshot.mode || "realtime";
  form.theme.value = currentSnapshot.theme || "river";
  if (form.ghostSource.value === "") {
    form.ghostSource.value = "none";
  }
}

function getAudioContext() {
  if (!audioContext) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      return null;
    }
    audioContext = new AudioContextClass();
  }
  if (audioContext.state === "suspended") {
    audioContext.resume().catch(() => {});
  }
  return audioContext;
}

function tone(frequency, durationMs, options = {}) {
  const audio = getAudioContext();
  if (!audio) {
    return;
  }

  const oscillator = audio.createOscillator();
  const gain = audio.createGain();
  const now = audio.currentTime;

  oscillator.connect(gain);
  gain.connect(audio.destination);
  oscillator.type = options.type || "triangle";
  oscillator.frequency.value = frequency;
  gain.gain.setValueAtTime(options.volume ?? 0.05, now);
  if (options.fadeOut !== false) {
    gain.gain.exponentialRampToValueAtTime(0.0001, now + durationMs / 1000);
  }
  oscillator.start(now);
  oscillator.stop(now + durationMs / 1000);
}

function getSplashBuffer() {
  const audio = getAudioContext();
  if (!audio) {
    return null;
  }
  if (splashBuffer) {
    return splashBuffer;
  }

  const length = Math.floor(audio.sampleRate * 0.9);
  splashBuffer = audio.createBuffer(1, length, audio.sampleRate);
  const data = splashBuffer.getChannelData(0);

  for (let index = 0; index < length; index += 1) {
    const progress = index / length;
    const envelope = (1 - progress) ** 2;
    data[index] = (Math.random() * 2 - 1) * envelope;
  }

  return splashBuffer;
}

function playSplash() {
  const audio = getAudioContext();
  const buffer = getSplashBuffer();
  if (!audio || !buffer) {
    return;
  }

  const source = audio.createBufferSource();
  const filter = audio.createBiquadFilter();
  const gain = audio.createGain();
  const now = audio.currentTime;

  source.buffer = buffer;
  filter.type = "bandpass";
  filter.frequency.setValueAtTime(900, now);
  filter.Q.value = 0.8;
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(0.18, now + 0.04);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.8);

  source.connect(filter);
  filter.connect(gain);
  gain.connect(audio.destination);
  source.start(now);
  source.stop(now + 0.85);
}

function playCrowdCheer() {
  const audio = getAudioContext();
  const buffer = getSplashBuffer();
  if (!audio || !buffer) {
    return;
  }

  const now = audio.currentTime;

  [950, 1400, 2200].forEach((frequency, index) => {
    const source = audio.createBufferSource();
    const filter = audio.createBiquadFilter();
    const gain = audio.createGain();

    source.buffer = buffer;
    source.loop = true;
    filter.type = "bandpass";
    filter.frequency.setValueAtTime(frequency, now);
    filter.Q.value = 0.9 + index * 0.25;
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.03 + index * 0.018, now + 0.12 + index * 0.03);
    gain.gain.exponentialRampToValueAtTime(0.018 + index * 0.004, now + 1.9);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 3.8);

    source.connect(filter);
    filter.connect(gain);
    gain.connect(audio.destination);
    source.start(now);
    source.stop(now + 3.85);
  });

  [620, 760, 890, 1040, 1180].forEach((frequency, index) => {
    tone(frequency, 220 + index * 35, {
      volume: 0.025 + index * 0.008,
      type: index % 2 === 0 ? "triangle" : "sawtooth",
    });
  });
}

function playVictoryCue() {
  playCrowdCheer();
  tone(523.25, 240, { volume: 0.035 });
  setTimeout(() => tone(659.25, 260, { volume: 0.035 }), 170);
  setTimeout(() => tone(783.99, 560, { volume: 0.04 }), 340);
}

function playCountdownCue(second) {
  const sequence = {
    3: 740,
    2: 880,
    1: 1046,
  };
  const frequency = sequence[second] || 880;
  tone(frequency, second === 1 ? 220 : 150, { volume: 0.06, type: "square" });
}

function handleEventSounds(nextSnapshot) {
  const cueKey = nextSnapshot.event === "countdown" ? `countdown:${nextSnapshot.countdown_s}` : nextSnapshot.event;
  if (cueKey === lastSoundCue) {
    return;
  }
  lastSoundCue = cueKey;

  if (nextSnapshot.event === "countdown") {
    playCountdownCue(nextSnapshot.countdown_s);
  }
  if (nextSnapshot.event === "race_started") {
    playSplash();
    tone(1240, 240, { volume: 0.055, type: "sawtooth" });
    setTimeout(playCrowdCheer, 40);
  }
  if (nextSnapshot.event === "race_finished") {
    playVictoryCue();
  }
}

async function loadHistory() {
  if (!leaderboard && !history && !diagnostics) {
    return;
  }

  const response = await fetch("/api/history");
  if (!response.ok) {
    throw new Error("Nepodarilo se nacist historii.");
  }

  const payload = await response.json();
  const leaderboardEntries = isKioskPage ? payload.top_results.slice(0, 3) : payload.top_results;

  renderList(
    leaderboard,
    leaderboardEntries,
    (entry, index) => `
      <div class="list-row">
        <span>${index + 1}. ${entry.player_name}</span>
        <strong>${formatTime(entry.best_time_s)}</strong>
      </div>
    `,
  );

  renderList(
    history,
    payload.recent_results,
    (entry) => `
      <div class="list-row">
        <div>
          <strong>${entry.player_name}</strong>
          <div>${entry.distance_m} m • ${entry.mode}</div>
        </div>
        <div>
          <strong>${formatTime(entry.finish_time_s)}</strong>
          <div class="badge">${entry.bonus_points} b</div>
        </div>
      </div>
    `,
  );

  if (diagnostics) {
    const diagnosticsResponse = await fetch("/api/diagnostics/status");
    if (!diagnosticsResponse.ok) {
      throw new Error("Nepodarilo se nacist PM3 diagnostiku.");
    }

    const diagnosticsPayload = await diagnosticsResponse.json();
    renderList(
      diagnostics,
      [diagnosticsPayload],
      (entry) => `
        <div class="list-row">
          <div>
            <strong>${entry.enabled ? "PM3 logovani aktivni" : "PM3 logovani vypnuto"}</strong>
            <div>${entry.total_events} udalosti</div>
          </div>
          <div>
            <strong>${entry.log_path.split("/").at(-1) || "pm3-diagnostics.log"}</strong>
          </div>
        </div>
      `,
    );
  }
}

async function fetchSnapshot() {
  const response = await fetch("/api/race");
  if (!response.ok) {
    throw new Error("Nepodarilo se nacist stav zavodu.");
  }

  const payload = await response.json();
  updateSnapshot(payload);
}

async function fetchStatus() {
  const response = await fetch("/api/status");
  if (!response.ok) {
    throw new Error("Nepodarilo se nacist stav aplikace.");
  }

  const payload = await response.json();
  populateSerialPortOptions(payload);
  if (form.useMock) {
    form.useMock.checked = payload.using_mock_devices;
  }
  syncUsbControls();
  return payload;
}

async function startRace() {
  if (!form.player1 || !form.player2 || !form.distance || !form.mode || !form.theme || !form.ghostSource || !form.useMock || !form.intervalPreset) {
    return;
  }

  const [sprint, rest] = form.intervalPreset.value.split(",").map(Number);
  const payload = {
    player_names: [form.player1.value || "Veslar 1", form.player2.value || "Veslar 2"],
    distance_m: Number(form.distance.value),
    mode: form.mode.value,
    theme: form.theme.value,
    ghost_source: form.ghostSource.value,
    use_mock_devices: form.useMock.checked,
    interval: form.mode.value === "interval" ? { sprint_s: sprint, rest_s: rest, repeats: 8 } : null,
  };

  if (!form.useMock.checked && form.serialPort1 && form.serialPort2 && form.serialPort1.value && form.serialPort2.value) {
    payload.serial_ports = [form.serialPort1.value, form.serialPort2.value];
  }

  const response = await fetch("/api/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({ detail: "Nepodarilo se spustit zavod." }));
    countdown.textContent = "";
    eventLabel.textContent = errorPayload.detail || "Nepodarilo se spustit zavod.";
    return;
  }
  const nextSnapshot = await response.json();
  updateSnapshot(nextSnapshot);
  handleEventSounds(nextSnapshot);
}

async function resetRace() {
  const response = await fetch("/api/reset", { method: "POST" });
  const nextSnapshot = await response.json();
  updateSnapshot(nextSnapshot);
  await loadHistory();
}

async function clearHistory() {
  const confirmed = window.confirm("Opravdu vymazat celou historii závodů?");
  if (!confirmed) {
    return;
  }

  const response = await fetch("/api/history/clear", { method: "POST" });
  if (!response.ok) {
    return;
  }

  await loadHistory();
}

function downloadCsv() {
  const distance = Number(form.distance?.value ?? snapshot.distance_m);
  const playerName = form.player1?.value.trim() ?? "";
  const params = new URLSearchParams();

  if (Number.isFinite(distance) && distance > 0) {
    params.set("distance_m", String(distance));
  }
  if (playerName) {
    params.set("player_name", playerName);
  }

  const url = `/api/history/export${params.toString() ? `?${params}` : ""}`;
  window.location.assign(url);
}

function downloadLeaderboardCsv() {
  const distance = Number(form.distance?.value ?? snapshot.distance_m);
  const params = new URLSearchParams();
  if (Number.isFinite(distance) && distance > 0) {
    params.set("distance_m", String(distance));
  }
  params.set("limit", "10");
  const url = `/api/leaderboard/export?${params}`;
  window.location.assign(url);
}

function downloadDiagnosticsLog() {
  window.location.assign("/api/diagnostics/export");
}

function connectSocket() {
  socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/race`);
  socket.addEventListener("message", (event) => {
    const nextSnapshot = JSON.parse(event.data);
    updateSnapshot(nextSnapshot);
    handleEventSounds(nextSnapshot);
    if (nextSnapshot.event === "race_finished") {
      loadHistory();
    }
  });
  socket.addEventListener("close", () => setTimeout(connectSocket, 1200));
}

if (form.theme) {
  form.theme.addEventListener("change", () => setTheme(form.theme.value));
}
if (form.useMock) {
  form.useMock.addEventListener("change", syncUsbControls);
}
if (form.startButton) {
  form.startButton.addEventListener("click", startRace);
}
if (form.resetButton) {
  form.resetButton.addEventListener("click", resetRace);
}
if (exportCsvButton) {
  exportCsvButton.addEventListener("click", downloadCsv);
}
if (exportLeaderboardCsvButton) {
  exportLeaderboardCsvButton.addEventListener("click", downloadLeaderboardCsv);
}
if (exportDiagnosticsButton) {
  exportDiagnosticsButton.addEventListener("click", downloadDiagnosticsLog);
}
if (clearHistoryButton) {
  clearHistoryButton.addEventListener("click", clearHistory);
}

async function bootstrap() {
  setTheme(snapshot.theme);
  connectSocket();

  const tasks = [fetchSnapshot(), fetchStatus(), loadHistory()];
  const results = await Promise.allSettled(tasks);

  results.forEach((result) => {
    if (result.status === "rejected") {
      console.error(result.reason);
    }
  });
}

function animationLoop() {
  if (!canvas) {
    return;
  }
  requestAnimationFrame(animationLoop);
  const now = performance.now();
  const frameInterval = 1000 / renderSettings.targetFps;
  if (now - lastFrameTime < frameInterval) {
    return;
  }
  lastFrameTime = now;

  if (now - lastWaterTick >= frameInterval) {
    waterPhase += isLiteMode ? 3.5 : 5;
    lastWaterTick = now;
  }

  drawScene();
}

window.addEventListener("resize", resizeCanvas);
resizeCanvas();
if (canvas) {
  animationLoop();
}

bootstrap();