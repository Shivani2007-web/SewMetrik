"""SVG preview exporter for SewMetrik bodice geometry.

This module renders the geometry produced by the pattern engine
(``generate_back_bodice_geometry`` / ``generate_front_bodice_geometry``) as a
simple, CAD-like SVG preview. It does NOT recalculate any pattern geometry; it
only visualizes what the pattern engine already produced.

Coordinates from the engine are in centimetres. For display only, they are
scaled by ``SCALE`` SVG units per centimetre. This scale never changes the real
pattern coordinates.
"""

from .blouse import CubicBezier, LineSegment, Point, SareeBlousePattern
# Visualization only: 1 cm = 10 SVG units.
SCALE = 10.0

# Padding around the drawing, in SVG units.
PADDING = 20.0


def _sx(value: float) -> float:
    """Scale a centimetre value to SVG units."""
    return value * SCALE


def _shape_points(shape: LineSegment | CubicBezier) -> list[Point]:
    """Return every defining Point of a shape (for bounds and markers)."""
    if isinstance(shape, LineSegment):
        return [shape.start, shape.end]
    return [shape.start, shape.control1, shape.control2, shape.end]


def _anchor_points(shapes: list[LineSegment | CubicBezier]) -> list[Point]:
    """Return unique on-outline anchor points (segment/curve endpoints)."""
    seen: set[tuple[float, float]] = set()
    points: list[Point] = []
    for shape in shapes:
        for point in (shape.start, shape.end):
            key = (point.x, point.y)
            if key not in seen:
                seen.add(key)
                points.append(point)
    return points


def _command_for(shape: LineSegment | CubicBezier) -> str:
    """Return the SVG path command that continues from the shape's start."""
    if isinstance(shape, LineSegment):
        return f"L {_sx(shape.end.x):.2f} {_sx(shape.end.y):.2f}"
    return (
        f"C {_sx(shape.control1.x):.2f} {_sx(shape.control1.y):.2f} "
        f"{_sx(shape.control2.x):.2f} {_sx(shape.control2.y):.2f} "
        f"{_sx(shape.end.x):.2f} {_sx(shape.end.y):.2f}"
    )


def _build_outline_path(
    geometry: dict[str, LineSegment | CubicBezier],
    ordered_keys: list[str],
) -> str:
    """Build one continuous, closed SVG path from ordered geometry keys."""
    first = geometry[ordered_keys[0]]
    commands = [f"M {_sx(first.start.x):.2f} {_sx(first.start.y):.2f}"]
    for key in ordered_keys:
        commands.append(_command_for(geometry[key]))
    commands.append("Z")
    return " ".join(commands)


def _render_svg(
    geometry: dict[str, LineSegment | CubicBezier],
    ordered_keys: list[str],
    output_path: str,
    title: str,
    label: str,
    dart_keys: list[str] | None = None,
    extra_points: list[Point] | None = None,
) -> str:
    """Render an outline (plus optional internal dart) to an SVG file."""
    dart_keys = dart_keys or []
    extra_points = extra_points or []
    outline_shapes = [geometry[k] for k in ordered_keys]
    dart_shapes = [geometry[k] for k in dart_keys]

    # Bounds computed from every point that will be drawn.
    all_points: list[Point] = []
    for shape in outline_shapes + dart_shapes:
        all_points.extend(_shape_points(shape))
    all_points.extend(extra_points)
    xs = [_sx(p.x) for p in all_points]
    ys = [_sx(p.y) for p in all_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    view_x = min_x - PADDING
    view_y = min_y - PADDING
    view_w = (max_x - min_x) + 2 * PADDING
    view_h = (max_y - min_y) + 2 * PADDING

    outline = _build_outline_path(geometry, ordered_keys)

    # Internal dart legs (construction only, not part of the outer outline).
    dart_paths: list[str] = []
    for shape in dart_shapes:
        dart_paths.append(
            f'    <path d="M {_sx(shape.start.x):.2f} {_sx(shape.start.y):.2f} '
            f'L {_sx(shape.end.x):.2f} {_sx(shape.end.y):.2f}" />'
        )

    # Construction-point markers: outline anchors, dart endpoints and extras.
    marker_points = _anchor_points(outline_shapes + dart_shapes)
    seen = {(p.x, p.y) for p in marker_points}
    for point in extra_points:
        if (point.x, point.y) not in seen:
            seen.add((point.x, point.y))
            marker_points.append(point)
    markers: list[str] = []
    for point in marker_points:
        cx, cy = _sx(point.x), _sx(point.y)
        markers.append(
            f'    <circle cx="{cx:.2f}" cy="{cy:.2f}" r="3" '
            f'fill="#c0392b" stroke="#ffffff" stroke-width="0.8" />'
        )

    title_x = view_x + PADDING * 0.5
    title_y = view_y + PADDING * 0.9
    label_x = view_x + view_w * 0.5
    label_y = view_y + view_h * 0.5
    note_x = view_x + PADDING * 0.5
    note_y = view_y + view_h - PADDING * 0.3

    dart_group = ""
    if dart_paths:
        dart_group = f"""
  <!-- Internal waist dart (construction only) -->
  <g fill="none" stroke="#2980b9" stroke-width="1"
     stroke-dasharray="4 3" stroke-linecap="round">
{chr(10).join(dart_paths)}
  </g>
"""

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="{view_x:.2f} {view_y:.2f} {view_w:.2f} {view_h:.2f}"
     width="{view_w:.2f}" height="{view_h:.2f}">
  <!-- White CAD-style background -->
  <rect x="{view_x:.2f}" y="{view_y:.2f}" width="{view_w:.2f}" height="{view_h:.2f}"
        fill="#ffffff" />

  <!-- Title -->
  <text x="{title_x:.2f}" y="{title_y:.2f}" font-family="sans-serif"
        font-size="10" font-weight="bold" fill="#1a1a1a">{title}</text>

  <!-- Continuous bodice outline -->
  <g fill="none" stroke="#1a1a1a" stroke-width="1.5"
     stroke-linejoin="round" stroke-linecap="round">
    <path d="{outline}" />
  </g>
{dart_group}
  <!-- Construction points -->
  <g>
{chr(10).join(markers)}
  </g>

  <!-- Panel label -->
  <text x="{label_x:.2f}" y="{label_y:.2f}" font-family="sans-serif"
        font-size="9" fill="#7f8c8d" text-anchor="middle">{label}</text>

  <!-- Note -->
  <text x="{note_x:.2f}" y="{note_y:.2f}" font-family="sans-serif"
        font-size="8" fill="#7f8c8d">Dimensions in cm</text>
</svg>
"""

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(svg)

    return output_path


def export_back_bodice_svg(
    geometry: dict[str, LineSegment | CubicBezier],
    output_path: str,
) -> str:
    """Render the back bodice geometry to an SVG file and return its path."""
    ordered_keys = [
        "neckline",
        "shoulder",
        "armhole",
        "side_seam",
        "waist",
        "center_back",
    ]
    return _render_svg(
        geometry,
        ordered_keys,
        output_path,
        title="SewMetrik — Back Bodice Prototype",
        label="BACK BODICE",
    )


def export_front_bodice_svg(
    geometry: dict[str, LineSegment | CubicBezier],
    output_path: str,
) -> str:
    """Render the front bodice geometry (with dart) and return its path."""
    ordered_keys = [
        "neckline",
        "shoulder",
        "armhole",
        "side_seam",
        "waist",
        "center_front",
    ]
    return _render_svg(
        geometry,
        ordered_keys,
        output_path,
        title="SewMetrik — Front Bodice Prototype",
        label="FRONT BODICE",
        dart_keys=["dart_left", "dart_right"],
    )


def export_sleeve_svg(
    geometry: dict[str, LineSegment | CubicBezier],
    output_path: str,
) -> str:
    """Render the sleeve geometry to an SVG file and return its path."""
    ordered_keys = [
        "cap_left_curve",
        "cap_right_curve",
        "side_seam_right",
        "hem",
        "side_seam_left",
    ]
    # Cap shoulder points live inside the cap curves as control points.
    extra_points = [
        geometry["cap_left_curve"].control2,
        geometry["cap_right_curve"].control1,
    ]
    return _render_svg(
        geometry,
        ordered_keys,
        output_path,
        title="SewMetrik — Sleeve Prototype",
        label="SLEEVE",
        extra_points=extra_points,
    )


def _piece_scaled_bounds(
    geometry: dict[str, LineSegment | CubicBezier],
    ordered_keys: list[str],
    dart_keys: list[str],
    extra_points: list[Point],
) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) of a piece in SVG units."""
    points: list[Point] = list(extra_points)
    for key in ordered_keys + dart_keys:
        points.extend(_shape_points(geometry[key]))
    xs = [_sx(p.x) for p in points]
    ys = [_sx(p.y) for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _piece_group(
    geometry: dict[str, LineSegment | CubicBezier],
    ordered_keys: list[str],
    dart_keys: list[str],
    extra_points: list[Point],
    dx: float,
    dy: float,
) -> str:
    """Build a translated <g> containing one piece's outline, dart and markers.

    The translate only moves the piece on the sheet for display; it does not
    change any underlying pattern coordinate.
    """
    outline = _build_outline_path(geometry, ordered_keys)
    outline_shapes = [geometry[k] for k in ordered_keys]
    dart_shapes = [geometry[k] for k in dart_keys]

    marker_points = _anchor_points(outline_shapes + dart_shapes)
    seen = {(p.x, p.y) for p in marker_points}
    for point in extra_points:
        if (point.x, point.y) not in seen:
            seen.add((point.x, point.y))
            marker_points.append(point)

    markers = [
        f'      <circle cx="{_sx(p.x):.2f}" cy="{_sx(p.y):.2f}" r="3" '
        f'fill="#c0392b" stroke="#ffffff" stroke-width="0.8" />'
        for p in marker_points
    ]

    dart_paths = [
        f'      <path d="M {_sx(s.start.x):.2f} {_sx(s.start.y):.2f} '
        f'L {_sx(s.end.x):.2f} {_sx(s.end.y):.2f}" />'
        for s in dart_shapes
    ]

    dart_group = ""
    if dart_paths:
        dart_group = f"""
    <g fill="none" stroke="#2980b9" stroke-width="1"
       stroke-dasharray="4 3" stroke-linecap="round">
{chr(10).join(dart_paths)}
    </g>"""

    return f"""  <g transform="translate({dx:.2f} {dy:.2f})">
    <g fill="none" stroke="#1a1a1a" stroke-width="1.5"
       stroke-linejoin="round" stroke-linecap="round">
      <path d="{outline}" />
    </g>{dart_group}
    <g>
{chr(10).join(markers)}
    </g>
  </g>"""


def export_complete_blouse_svg(
    pattern: SareeBlousePattern,
    output_path: str,
) -> str:
    """Arrange back bodice, front bodice and sleeve on one sheet SVG.

    Uses the existing geometry methods without recalculating anything. Pieces
    are placed side by side using per-piece bounds so they never overlap; the
    arrangement is display-only and never alters pattern coordinates.
    """
    m = pattern.measurements

    # Piece definitions: (label, geometry, outline keys, dart keys, extras).
    back_geometry = pattern.generate_back_bodice_geometry()
    front_geometry = pattern.generate_front_bodice_geometry()
    sleeve_geometry = pattern.generate_sleeve_geometry()

    pieces = [
        (
            "BACK BODICE",
            back_geometry,
            ["neckline", "shoulder", "armhole", "side_seam", "waist", "center_back"],
            [],
            [],
        ),
        (
            "FRONT BODICE",
            front_geometry,
            ["neckline", "shoulder", "armhole", "side_seam", "waist", "center_front"],
            ["dart_left", "dart_right"],
            [],
        ),
        (
            "SLEEVE",
            sleeve_geometry,
            ["cap_left_curve", "cap_right_curve", "side_seam_right", "hem", "side_seam_left"],
            [],
            [
                sleeve_geometry["cap_left_curve"].control2,
                sleeve_geometry["cap_right_curve"].control1,
            ],
        ),
    ]

    # Sheet layout constants (SVG units).
    margin = 40.0
    gap = 60.0
    top_baseline = 80.0

    cursor_x = margin
    groups: list[str] = []
    labels: list[str] = []
    max_bottom = top_baseline

    for label, geometry, ordered_keys, dart_keys, extra_points in pieces:
        min_x, min_y, max_x, max_y = _piece_scaled_bounds(
            geometry, ordered_keys, dart_keys, extra_points
        )
        width = max_x - min_x
        height = max_y - min_y

        dx = cursor_x - min_x
        dy = top_baseline - min_y
        groups.append(
            _piece_group(geometry, ordered_keys, dart_keys, extra_points, dx, dy)
        )

        center_x = cursor_x + width / 2
        labels.append(
            f'  <text x="{center_x:.2f}" y="{top_baseline - 16:.2f}" '
            f'font-family="sans-serif" font-size="11" font-weight="bold" '
            f'fill="#1a1a1a" text-anchor="middle">{label}</text>'
        )

        max_bottom = max(max_bottom, top_baseline + height)
        cursor_x += width + gap

    content_right = cursor_x - gap + margin

    # Measurement information section below the pieces.
    info_lines = [
        ("Bust", m.bust),
        ("Waist", m.waist),
        ("Shoulder", m.shoulder_width),
        ("Blouse Length", m.blouse_length),
        ("Armhole Depth", m.armhole_depth),
        ("Sleeve Length", m.sleeve_length),
        ("Upper Arm Circumference", m.upper_arm_circumference),
    ]
    info_top = max_bottom + 40.0
    line_height = 16.0

    info_texts = [
        f'  <text x="{margin:.2f}" y="{info_top:.2f}" font-family="sans-serif" '
        f'font-size="11" font-weight="bold" fill="#1a1a1a">Measurements (input):</text>'
    ]
    for index, (name, value) in enumerate(info_lines, start=1):
        y = info_top + index * line_height
        info_texts.append(
            f'  <text x="{margin:.2f}" y="{y:.2f}" font-family="sans-serif" '
            f'font-size="10" fill="#333333">{name}: {value} cm</text>'
        )

    info_bottom = info_top + (len(info_lines) + 1) * line_height

    view_w = content_right
    view_h = info_bottom + margin

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {view_w:.2f} {view_h:.2f}"
     width="{view_w:.2f}" height="{view_h:.2f}">
  <!-- White CAD-style background -->
  <rect x="0" y="0" width="{view_w:.2f}" height="{view_h:.2f}" fill="#ffffff" />

  <!-- Title -->
  <text x="{margin:.2f}" y="32" font-family="sans-serif" font-size="14"
        font-weight="bold" fill="#1a1a1a">SewMetrik Parametric Blouse Pattern — Prototype v1</text>
  <text x="{margin:.2f}" y="50" font-family="sans-serif" font-size="10"
        fill="#7f8c8d">Dimensions: cm</text>

  <!-- Piece labels -->
{chr(10).join(labels)}

  <!-- Pattern pieces -->
{chr(10).join(groups)}

  <!-- Measurements -->
{chr(10).join(info_texts)}
</svg>
"""

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(svg)

    return output_path
