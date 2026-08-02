"""DXF (CAD) exporter for SewMetrik blouse patterns.

This module writes geometry from the existing pattern engine to DXF without
recalculating any drafting math. Internal coordinates are centimetres; DXF
export coordinates are millimetres for broad CAD interoperability.
"""

from __future__ import annotations

import math

import ezdxf
from ezdxf.math import BSpline

from .blouse import CubicBezier, LineSegment, SareeBlousePattern

# Knot vector that makes a 4-point, degree-3 B-spline reproduce a cubic Bezier.
_BEZIER_KNOTS = [0, 0, 0, 0, 1, 1, 1, 1]

# Unit conversion: internal pattern engine is cm, DXF export is mm.
_CM_TO_MM = 10.0

# Horizontal gap between pieces on the DXF layout sheet, in cm.
_PIECE_GAP_CM = 10.0


def _to_mm(value_cm: float) -> float:
    return value_cm * _CM_TO_MM


def _add_line(msp, segment: LineSegment, layer: str, dx: float, dy: float) -> None:
    """Add a LineSegment to the DXF modelspace as a LINE entity."""
    msp.add_line(
        (_to_mm(segment.start.x + dx), _to_mm(segment.start.y + dy)),
        (_to_mm(segment.end.x + dx), _to_mm(segment.end.y + dy)),
        dxfattribs={"layer": layer},
    )


def _add_bezier(msp, curve: CubicBezier, layer: str, dx: float, dy: float) -> None:
    """Add a CubicBezier to the DXF modelspace as an exact SPLINE entity."""
    control_points = [
        (_to_mm(curve.start.x + dx), _to_mm(curve.start.y + dy)),
        (_to_mm(curve.control1.x + dx), _to_mm(curve.control1.y + dy)),
        (_to_mm(curve.control2.x + dx), _to_mm(curve.control2.y + dy)),
        (_to_mm(curve.end.x + dx), _to_mm(curve.end.y + dy)),
    ]
    # This degree-3 clamped B-spline with Bezier knots is an exact cubic Bezier.
    bspline = BSpline(control_points, order=4, knots=_BEZIER_KNOTS)
    msp.add_spline(dxfattribs={"layer": layer}).apply_construction_tool(bspline)


def _bounds_cm(
    geometry: dict[str, LineSegment | CubicBezier],
    keys: list[str],
) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) of the given shapes in centimetres."""
    xs: list[float] = []
    ys: list[float] = []
    for key in keys:
        shape = geometry[key]
        if isinstance(shape, LineSegment):
            points = [shape.start, shape.end]
        else:
            points = [shape.start, shape.control1, shape.control2, shape.end]
        xs.extend(p.x for p in points)
        ys.extend(p.y for p in points)
    return min(xs), min(ys), max(xs), max(ys)


def _add_validation_square(msp) -> None:
    """Add a 100 mm x 100 mm scale check square and label on VALIDATION layer."""
    x0 = -140.0
    y0 = 40.0
    size = 100.0
    x1 = x0 + size
    y1 = y0 + size

    msp.add_line((x0, y0), (x1, y0), dxfattribs={"layer": "VALIDATION"})
    msp.add_line((x1, y0), (x1, y1), dxfattribs={"layer": "VALIDATION"})
    msp.add_line((x1, y1), (x0, y1), dxfattribs={"layer": "VALIDATION"})
    msp.add_line((x0, y1), (x0, y0), dxfattribs={"layer": "VALIDATION"})
    msp.add_text(
        "100 mm TEST SQUARE",
        dxfattribs={"layer": "VALIDATION", "height": 8.0},
    ).set_placement((x0, y1 + 12.0))


def _iter_entity_points(entity):
    """Yield coordinate tuples for finite-coordinate validation."""
    t = entity.dxftype()
    if t == "LINE":
        yield tuple(entity.dxf.start)
        yield tuple(entity.dxf.end)
    elif t == "SPLINE":
        for p in entity.control_points:
            yield tuple(p)
        for p in entity.fit_points:
            yield tuple(p)
    elif t == "TEXT":
        yield tuple(entity.dxf.insert)


def _is_finite_number(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def validate_dxf_file(dxf_path: str) -> dict[str, float | int | str]:
    """Reload and validate exported DXF for CAD compatibility checks."""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    required_layers = ("PATTERN_OUTLINE", "CONSTRUCTION", "LABELS", "VALIDATION")
    missing_layers = [layer for layer in required_layers if layer not in doc.layers]
    if missing_layers:
        raise ValueError(f"Missing DXF layers: {', '.join(missing_layers)}")

    lines = msp.query("LINE")
    splines = msp.query("SPLINE")
    construction_entities = [e for e in msp if e.dxf.layer == "CONSTRUCTION"]

    if len(lines) == 0:
        raise ValueError("DXF has no LINE entities.")
    if len(splines) == 0:
        raise ValueError("DXF has no SPLINE entities.")

    if doc.dxfversion != "AC1024":
        raise ValueError(f"DXF version is {doc.dxfversion}, expected AC1024.")
    if doc.units != ezdxf.units.MM:
        raise ValueError(f"DXF units are {doc.units}, expected millimetres.")

    has_non_finite = False
    xs: list[float] = []
    ys: list[float] = []

    for entity in msp:
        for point in _iter_entity_points(entity):
            if not point:
                continue
            if not all(_is_finite_number(n) for n in point):
                has_non_finite = True
                continue
            if len(point) >= 1:
                xs.append(float(point[0]))
            if len(point) >= 2:
                ys.append(float(point[1]))

    if has_non_finite:
        raise ValueError("DXF contains non-finite coordinates (NaN/inf).")
    if not xs or not ys:
        raise ValueError("Could not compute DXF bounding box from entities.")

    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)

    return {
        "dxf_version": doc.dxfversion,
        "units": "mm",
        "pattern_width": max_x - min_x,
        "pattern_height": max_y - min_y,
        "line_entities": len(lines),
        "spline_entities": len(splines),
        "construction_entities": len(construction_entities),
    }


def export_blouse_dxf(pattern: SareeBlousePattern, output_path: str) -> str:
    """Write the complete blouse pattern to a DXF file and return its path."""
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    doc.header["$INSUNITS"] = ezdxf.units.MM

    doc.layers.new("PATTERN_OUTLINE", dxfattribs={"color": 7})
    doc.layers.new("CONSTRUCTION", dxfattribs={"color": 5})
    doc.layers.new("LABELS", dxfattribs={"color": 3})
    doc.layers.new("VALIDATION", dxfattribs={"color": 1})

    msp = doc.modelspace()

    back = pattern.generate_back_bodice_geometry()
    front = pattern.generate_front_bodice_geometry()
    sleeve = pattern.generate_sleeve_geometry()

    # (label, geometry, outline keys, dart/construction keys)
    pieces = [
        (
            "BACK BODICE",
            back,
            ["neckline", "shoulder", "armhole", "side_seam", "waist", "center_back"],
            [],
        ),
        (
            "FRONT BODICE",
            front,
            ["neckline", "shoulder", "armhole", "side_seam", "waist", "center_front"],
            ["dart_left", "dart_right"],
        ),
        (
            "SLEEVE",
            sleeve,
            ["cap_left_curve", "cap_right_curve", "side_seam_right", "hem", "side_seam_left"],
            [],
        ),
    ]

    cursor_x = 0.0
    for label, geometry, outline_keys, dart_keys in pieces:
        min_x, _, max_x, _ = _bounds_cm(geometry, outline_keys + dart_keys)

        # Pure translation to separate pieces horizontally (dimensions kept).
        dx = cursor_x - min_x
        dy = 0.0

        # Cutting outline on PATTERN_OUTLINE.
        for key in outline_keys:
            shape = geometry[key]
            if isinstance(shape, LineSegment):
                _add_line(msp, shape, "PATTERN_OUTLINE", dx, dy)
            else:
                _add_bezier(msp, shape, "PATTERN_OUTLINE", dx, dy)

        # Dart legs on CONSTRUCTION (never part of the cutting outline).
        for key in dart_keys:
            _add_line(msp, geometry[key], "CONSTRUCTION", dx, dy)

        # Piece label placed just above the piece.
        msp.add_text(
            label,
            dxfattribs={"layer": "LABELS", "height": 25.0},
        ).set_placement((_to_mm(cursor_x), _to_mm(-4.0)))

        cursor_x += (max_x - min_x) + _PIECE_GAP_CM

    # Sheet-level labels.
    msp.add_text(
        "SewMetrik Prototype v1",
        dxfattribs={"layer": "LABELS", "height": 30.0},
    ).set_placement((_to_mm(0.0), _to_mm(-12.0)))
    msp.add_text(
        "Units: mm",
        dxfattribs={"layer": "LABELS", "height": 25.0},
    ).set_placement((_to_mm(0.0), _to_mm(-17.0)))

    _add_validation_square(msp)

    doc.saveas(output_path)
    return output_path
