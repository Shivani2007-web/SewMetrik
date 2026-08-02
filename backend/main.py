"""FastAPI service exposing the SewMetrik saree blouse pattern engine.

This layer only wires HTTP requests to the existing pattern engine and
exporters. It contains no drafting logic of its own.
"""

import os
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.pattern_engine.blouse import BlouseMeasurements, SareeBlousePattern
from backend.pattern_engine.dxf_exporter import export_blouse_dxf
from backend.pattern_engine.svg_exporter import export_complete_blouse_svg

# Output directory for API-generated files.
API_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "generated", "api"
)
os.makedirs(API_OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="SewMetrik Pattern Engine")

# Local prototype CORS: allow a frontend on any localhost port to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated SVG/DXF files over HTTP so the browser can load them.
app.mount("/files", StaticFiles(directory=API_OUTPUT_DIR), name="files")


class BlousePatternRequest(BaseModel):
    """Body measurements for a saree blouse, in centimetres (all > 0)."""

    bust: float = Field(gt=0)
    waist: float = Field(gt=0)
    shoulder_width: float = Field(gt=0)
    blouse_length: float = Field(gt=0)
    armhole_depth: float = Field(gt=0)
    sleeve_length: float = Field(gt=0)
    upper_arm_circumference: float = Field(gt=0)


@app.get("/health")
def health() -> dict:
    """Simple liveness check."""
    return {"status": "ok", "service": "SewMetrik Pattern Engine"}


@app.post("/generate-pattern")
def generate_pattern(request: BlousePatternRequest) -> dict:
    """Generate a complete blouse pattern (SVG + DXF) from measurements."""
    try:
        measurements = BlouseMeasurements(
            bust=request.bust,
            waist=request.waist,
            shoulder_width=request.shoulder_width,
            blouse_length=request.blouse_length,
            armhole_depth=request.armhole_depth,
            sleeve_length=request.sleeve_length,
            upper_arm_circumference=request.upper_arm_circumference,
        )
        pattern = SareeBlousePattern(measurements)

        os.makedirs(API_OUTPUT_DIR, exist_ok=True)
        pattern_id = str(uuid.uuid4())
        svg_name = f"pattern_{pattern_id}.svg"
        dxf_name = f"pattern_{pattern_id}.dxf"
        svg_file = os.path.join(API_OUTPUT_DIR, svg_name)
        dxf_file = os.path.join(API_OUTPUT_DIR, dxf_name)

        export_complete_blouse_svg(pattern, svg_file)
        export_blouse_dxf(pattern, dxf_file)

        return {
            "pattern_id": pattern_id,
            "garment_type": "saree_blouse",
            "units": "cm",
            "measurements": request.model_dump(),
            "calculated_dimensions": pattern.debug_dimensions(),
            "svg_file": svg_file,
            "dxf_file": dxf_file,
            "svg_url": f"/files/{svg_name}",
            "dxf_url": f"/files/{dxf_name}",
        }
    except Exception as exc:  # convert any failure into a clean HTTP error
        raise HTTPException(
            status_code=500, detail=f"Pattern generation failed: {exc}"
        ) from exc
