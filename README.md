# SewMetrik

**AI-Assisted Custom Pattern Drafting** — a prototype that turns body measurements into
production-style sewing patterns for a saree blouse, exported as both an on-screen SVG
preview and a CAD-ready DXF file.

SewMetrik pairs a parametric drafting engine (Python/FastAPI) with a browser-based
front end that can optionally estimate body measurements from a webcam using pose
detection and a printed calibration card.

> **Prototype notice:** The drafting formulas are simplified SewMetrik working
> approximations, not official tailoring or NIFT drafting standards. Always review
> generated measurements and patterns before cutting fabric.

---

## Features

- **Parametric blouse engine** — generates back bodice, front bodice (with waist dart),
  and sleeve geometry from seven body measurements.
- **SVG preview** — CAD-style rendering of all pattern pieces laid out on a single sheet,
  with construction points and the input measurements printed alongside.
- **DXF export** — millimetre-unit DXF (AutoCAD R2010 / `AC1024`) with separate layers
  (`PATTERN_OUTLINE`, `CONSTRUCTION`, `LABELS`, `VALIDATION`), curves written as exact
  cubic splines, plus a 100 mm test square for scale verification.
- **AI body measurement (optional)** — webcam pose landmark detection via MediaPipe,
  scaled to real-world centimetres using a printed calibration card, to auto-fill the
  measurement form.
- **Simple REST API** — a single `POST /generate-pattern` endpoint plus a health check.

---

## Project structure

```
SewMetrik/
├── backend/
│   ├── main.py                  # FastAPI app: /health, POST /generate-pattern
│   └── pattern_engine/
│       ├── blouse.py            # Parametric drafting math (cm)
│       ├── svg_exporter.py      # CAD-style SVG preview renderer
│       └── dxf_exporter.py      # DXF (mm) exporter + reload validator
├── frontend/
│   ├── index.html               # Single-page UI
│   ├── app.js                   # Talks to the API, renders results/preview
│   ├── pose.js                  # Webcam + MediaPipe pose landmarks
│   ├── calibration.js           # Detects the calibration card -> px/cm scale
│   ├── measurements.js          # Estimates measurements from landmarks
│   ├── styles.css
│   └── assets/
│       └── sewmetrik_calibration_card.svg   # Printable calibration card
├── generated/                   # Sample/example output (api/ subfolder is gitignored)
├── test_pattern.py              # Engine + DXF validation script
├── requirements.txt
└── README.md
```

---

## How it works

1. You enter (or scan) seven measurements in centimetres: bust, waist, shoulder width,
   blouse length, armhole depth, sleeve length, and upper arm circumference.
2. The front end sends them to `POST /generate-pattern`.
3. `SareeBlousePattern` computes panel dimensions (quarter bust/waist plus ease, shoulder
   segments, armhole and sleeve geometry) and produces each piece as a set of line
   segments and cubic Bezier curves.
4. The exporters render a preview **SVG** and a CAD-ready **DXF**, and the API returns
   their URLs plus the calculated dimensions.
5. The browser shows the preview and offers the DXF for download.

### Optional camera measurement flow

1. **Start Camera** — loads the MediaPipe pose model and begins landmark detection.
2. **Calibrate Camera** — hold the printed calibration card (85.6 mm × 53.98 mm, the
   standard credit-card width) flat near your torso so its width in pixels can be mapped
   to real centimetres (pixels-per-cm scale).
3. **Capture Measurements** — samples several frames, estimates body measurements from the
   landmarks and scale, and fills the measurement form.

> **Camera requires a secure context.** Browsers only grant webcam access over HTTPS or
> from `localhost` / `127.0.0.1`. Open the front end via `http://127.0.0.1:5500`, not a
> LAN IP or the `[::]` address. Pose model and WASM assets load from a CDN, so the camera
> feature needs internet access.

---

## Requirements

- Python 3.10+
- A modern browser (Chrome/Edge recommended for the camera feature)
- Internet access for the optional camera feature (MediaPipe assets load from a CDN)

Python dependencies (see `requirements.txt`):

- `fastapi`
- `uvicorn`
- `pydantic`
- `ezdxf`

---

## Setup

From the project root (`SewMetrik/`):

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt
```

---

## Running the prototype

You need two local servers: the **backend API** and a **static file server** for the
front end.

### 1. Start the backend (port 8000)

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Verify it is up: <http://127.0.0.1:8000/health> should return
`{"status":"ok","service":"SewMetrik Pattern Engine"}`.

### 2. Serve the front end (port 5500)

In a second terminal:

```powershell
python -m http.server 5500 --bind 127.0.0.1
```
(run from the `frontend/` directory)

Then open **<http://127.0.0.1:5500/index.html>**. The header should read
"Pattern Engine: Connected".

> Binding the static server to `127.0.0.1` matters: it guarantees a secure-context origin
> so the camera feature can request webcam access.

---

## API reference

Base URL: `http://127.0.0.1:8000`

### `GET /health`

Liveness check.

```json
{ "status": "ok", "service": "SewMetrik Pattern Engine" }
```

### `POST /generate-pattern`

Generate a complete blouse pattern from measurements (all values in cm, all `> 0`).

Request body:

```json
{
  "bust": 91.44,
  "waist": 76.2,
  "shoulder_width": 35.56,
  "blouse_length": 38.1,
  "armhole_depth": 20.32,
  "sleeve_length": 22.86,
  "upper_arm_circumference": 27.94
}
```

Response (abridged):

```json
{
  "pattern_id": "…",
  "garment_type": "saree_blouse",
  "units": "cm",
  "measurements": { "…": "…" },
  "calculated_dimensions": {
    "bodice_width": 24.86,
    "waist_width": 21.05,
    "shoulder_segment": 17.78,
    "pattern_height": 38.1,
    "armhole_depth": 20.32
  },
  "svg_url": "/files/pattern_<id>.svg",
  "dxf_url": "/files/pattern_<id>.dxf"
}
```

Generated files are written under `generated/api/` and served at `/files/<name>`.

---

## Testing the engine

`test_pattern.py` exercises the drafting math, runs a parametric sanity check
(a larger bust yields a wider bodice), and validates a freshly exported DXF by
reloading it and checking version, units, layers, entity counts, and finite
coordinates.

```powershell
python test_pattern.py
```

---

## DXF output notes

- **Version/units:** AutoCAD R2010 (`AC1024`), millimetres. Internal engine math is in
  centimetres and converted to mm on export.
- **Layers:** `PATTERN_OUTLINE` (cutting lines), `CONSTRUCTION` (darts and internal
  guides), `LABELS` (text), `VALIDATION` (a 100 mm test square for scale checks).
- **Curves:** cubic Bezier edges are written as exact degree-3 clamped B-splines.
- Import into CAD/CAM or cutting software and confirm the 100 mm square measures 100 mm.

---

## Tech stack

- **Backend:** Python, FastAPI, Uvicorn, Pydantic, ezdxf
- **Front end:** Vanilla HTML/CSS/JavaScript
- **Computer vision:** MediaPipe Tasks Vision (Pose Landmarker), loaded from CDN

---

## Limitations

- Drafting formulas are prototype approximations, not certified tailoring standards.
- Only the saree blouse garment is implemented (Kurti and Palazzo are placeholders).
- Camera-based measurement is an estimate from a single 2D view and depends on lighting,
  framing, and calibration quality. Always review before generating a pattern.
