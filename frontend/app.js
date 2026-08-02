// SewMetrik frontend — vanilla JS client for the FastAPI pattern engine.

const API_BASE = "http://127.0.0.1:8000";

const MEASUREMENT_FIELDS = [
  "bust",
  "waist",
  "shoulder_width",
  "blouse_length",
  "armhole_depth",
  "sleeve_length",
  "upper_arm_circumference",
];

// Cached DOM references.
const els = {
  form: document.getElementById("measurementForm"),
  generateBtn: document.getElementById("generateBtn"),
  formMessage: document.getElementById("formMessage"),
  engineStatus: document.getElementById("engineStatus"),
  resultCard: document.getElementById("resultCard"),
  metaId: document.getElementById("metaId"),
  metaGarment: document.getElementById("metaGarment"),
  metaUnits: document.getElementById("metaUnits"),
  dimensionsGrid: document.getElementById("dimensionsGrid"),
  downloadDxf: document.getElementById("downloadDxf"),
  previewArea: document.getElementById("previewArea"),
};

// --- UI state helpers -------------------------------------------------------

function setState(state, message = "") {
  const busy = state === "generating";
  els.generateBtn.disabled = busy;
  els.generateBtn.textContent = busy
    ? "Generating pattern..."
    : "Generate Custom Pattern";

  els.formMessage.textContent = message;
  els.formMessage.className = "form-message";
  if (state === "error") els.formMessage.classList.add("form-message--error");
  if (state === "generating") els.formMessage.classList.add("form-message--busy");
}

function setEngineStatus(online) {
  els.engineStatus.classList.remove("status--unknown", "status--online", "status--offline");
  if (online) {
    els.engineStatus.classList.add("status--online");
    els.engineStatus.textContent = "Pattern Engine: Connected";
  } else {
    els.engineStatus.classList.add("status--offline");
    els.engineStatus.textContent = "Pattern Engine: Offline";
  }
}

// --- API calls --------------------------------------------------------------

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    setEngineStatus(res.ok);
  } catch {
    setEngineStatus(false);
  }
}

function readMeasurements() {
  const data = {};
  for (const name of MEASUREMENT_FIELDS) {
    data[name] = parseFloat(els.form.elements[name].value);
  }
  return data;
}

async function generatePattern(measurements) {
  const res = await fetch(`${API_BASE}/generate-pattern`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(measurements),
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore parse errors */
    }
    throw new Error(detail);
  }
  return res.json();
}

// --- Rendering --------------------------------------------------------------

function renderDimensions(dimensions) {
  els.dimensionsGrid.innerHTML = "";
  for (const [name, value] of Object.entries(dimensions)) {
    const item = document.createElement("div");
    item.className = "dim-item";
    item.innerHTML = `
      <span class="dim-name">${name}</span>
      <span class="dim-value">${value} cm</span>
    `;
    els.dimensionsGrid.appendChild(item);
  }
}

async function renderPreview(svgUrl) {
  const res = await fetch(`${API_BASE}${svgUrl}`);
  const svgText = await res.text();
  els.previewArea.innerHTML = svgText;
}

function renderResult(result) {
  els.metaId.textContent = result.pattern_id;
  els.metaGarment.textContent = result.garment_type;
  els.metaUnits.textContent = result.units;
  renderDimensions(result.calculated_dimensions);
  els.downloadDxf.href = `${API_BASE}${result.dxf_url}`;
  els.resultCard.classList.remove("hidden");
}

// --- Events -----------------------------------------------------------------

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setState("generating");
  try {
    const measurements = readMeasurements();
    const result = await generatePattern(measurements);
    renderResult(result);
    await renderPreview(result.svg_url);
    setState("success", "");
  } catch (err) {
    setState("error", err.message || "Pattern generation failed.");
  }
});

// Check backend health on load.
checkHealth();
