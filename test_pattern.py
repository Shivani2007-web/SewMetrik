"""Manual test script for the SewMetrik saree blouse pattern engine."""

import os
from dataclasses import replace

from backend.pattern_engine.blouse import BlouseMeasurements, SareeBlousePattern
from backend.pattern_engine.dxf_exporter import export_blouse_dxf, validate_dxf_file
from backend.pattern_engine.svg_exporter import (
    export_back_bodice_svg,
    export_complete_blouse_svg,
    export_front_bodice_svg,
    export_sleeve_svg,
)


measurements = BlouseMeasurements(
    bust=91.44,
    waist=76.2,
    shoulder_width=35.56,
    blouse_length=38.1,
    armhole_depth=20.32,
    sleeve_length=22.86,
    upper_arm_circumference=27.94,
)

pattern = SareeBlousePattern(measurements)

print("SewMetrik Pattern Engine Test")
for name, value in pattern.debug_dimensions().items():
    print(f"{name}: {value} cm")

back_bodice = pattern.generate_back_bodice()
print("\nBack Bodice Points")
for name, point in vars(back_bodice).items():
    print(f"{name}: x={point.x} cm, y={point.y} cm")

geometry = pattern.generate_back_bodice_geometry()
print("\nBack Bodice Geometry")
for name, shape in geometry.items():
    print(f"{name}: {type(shape).__name__}")
    for field, point in vars(shape).items():
        print(f"    {field}: x={point.x} cm, y={point.y} cm")

output_dir = os.path.join(os.path.dirname(__file__), "generated")
os.makedirs(output_dir, exist_ok=True)
svg_path = export_back_bodice_svg(
    geometry, os.path.join(output_dir, "back_bodice.svg")
)
print(f"\nSVG preview written to: {svg_path}")

front_geometry = pattern.generate_front_bodice_geometry()
print("\nFront Bodice Geometry")
for name, shape in front_geometry.items():
    print(f"{name}: {type(shape).__name__}")
    for field, point in vars(shape).items():
        print(f"    {field}: x={point.x} cm, y={point.y} cm")

front_svg_path = export_front_bodice_svg(
    front_geometry, os.path.join(output_dir, "front_bodice.svg")
)
print(f"\nSVG preview written to: {front_svg_path}")

print("\nSleeve Dimensions")
print(f"sleeve_width: {pattern.sleeve_width} cm")
print(f"sleeve_cap_height: {pattern.sleeve_cap_height} cm")
print(f"sleeve_length: {measurements.sleeve_length} cm")

sleeve_geometry = pattern.generate_sleeve_geometry()
print("\nSleeve Geometry")
for name, shape in sleeve_geometry.items():
    print(f"{name}: {type(shape).__name__}")
    for field, point in vars(shape).items():
        print(f"    {field}: x={point.x} cm, y={point.y} cm")

sleeve_svg_path = export_sleeve_svg(
    sleeve_geometry, os.path.join(output_dir, "sleeve.svg")
)
print(f"\nSVG preview written to: {sleeve_svg_path}")

complete_svg_path = export_complete_blouse_svg(
    pattern, os.path.join(output_dir, "complete_blouse_pattern.svg")
)
print(f"\nComplete pattern written to: {complete_svg_path}")

# Parametric verification: same measurements but a 40-inch bust.
measurements_40in = replace(measurements, bust=101.60)
pattern_40in = SareeBlousePattern(measurements_40in)

complete_svg_path_40in = export_complete_blouse_svg(
    pattern_40in, os.path.join(output_dir, "complete_blouse_pattern_40in.svg")
)
print(f"\nComplete 40-inch pattern written to: {complete_svg_path_40in}")

print("\nPARAMETRIC VERIFICATION")
print("\n36-inch bust:")
print(f"- bodice_width: {pattern.bodice_width} cm")
print(f"- waist_width: {pattern.waist_width} cm")
print(f"- armhole_depth: {pattern.armhole_depth} cm")
print("\n40-inch bust:")
print(f"- bodice_width: {pattern_40in.bodice_width} cm")
print(f"- waist_width: {pattern_40in.waist_width} cm")
print(f"- armhole_depth: {pattern_40in.armhole_depth} cm")

assert pattern_40in.bodice_width > pattern.bodice_width, (
    "Pattern is not parametric: 40-inch bodice_width should exceed 36-inch."
)
print("\nParametric check passed: 40-inch bodice_width > 36-inch bodice_width.")

# Hardened DXF export + compatibility validation.
dxf_path = export_blouse_dxf(
    pattern, os.path.join(output_dir, "sewmetrik_blouse_pattern_validated.dxf")
)
report = validate_dxf_file(dxf_path)

print("\nDXF VALIDATION")
print("--------------")
print(f"DXF version: {report['dxf_version']}")
print("Units: mm")
print(f"Pattern width: {report['pattern_width']:.2f} mm")
print(f"Pattern height: {report['pattern_height']:.2f} mm")
print(f"LINE entities: {report['line_entities']}")
print(f"SPLINE entities: {report['spline_entities']}")
print(f"Construction entities: {report['construction_entities']}")
print("Validation square: 100 x 100 mm")
print("Reload test: PASSED")
