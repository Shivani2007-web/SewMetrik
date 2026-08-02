"""Parametric drafting engine for a saree blouse bodice.

All measurements and calculations use centimetres (cm).

NOTE: The drafting formulas below are prototype SewMetrik assumptions used to
turn body measurements into pattern dimensions. They are simplified working
approximations and are NOT official tailoring or NIFT drafting standards.
"""

from dataclasses import dataclass


# Ease added to quarter measurements so the garment is not skin-tight (cm).
EASE_CM = 2.0


@dataclass
class BlouseMeasurements:
    """Body measurements for a saree blouse, in centimetres."""

    bust: float
    waist: float
    shoulder_width: float
    blouse_length: float
    armhole_depth: float
    sleeve_length: float
    upper_arm_circumference: float


@dataclass
class Point:
    """A 2D point on the pattern draft, in centimetres."""

    x: float
    y: float


@dataclass
class LineSegment:
    """A straight stitching line between two points, in centimetres."""

    start: Point
    end: Point


@dataclass
class CubicBezier:
    """A cubic Bezier curve for a stitching edge, in centimetres."""

    start: Point
    control1: Point
    control2: Point
    end: Point


@dataclass
class BackBodice:
    """Named corner points of the back bodice draft, in centimetres."""

    center_back_neck: Point
    neck_end: Point
    shoulder_end: Point
    armhole_point: Point
    underarm: Point
    waist_side: Point
    center_back_waist: Point


@dataclass
class FrontBodice:
    """Named points of the front bodice draft (incl. dart), in centimetres."""

    center_front_neck: Point
    neck_end: Point
    shoulder_end: Point
    armhole_point: Point
    underarm: Point
    waist_side: Point
    center_front_waist: Point
    dart_left: Point
    dart_apex: Point
    dart_right: Point


@dataclass
class Sleeve:
    """Named points of a symmetric sleeve draft, in centimetres."""

    cap_center: Point
    cap_left: Point
    cap_right: Point
    underarm_left: Point
    underarm_right: Point
    hem_left: Point
    hem_right: Point


class SareeBlousePattern:
    """Builds a parametric saree blouse pattern from body measurements."""

    def __init__(self, measurements: BlouseMeasurements) -> None:
        self.measurements = measurements

    @property
    def bodice_width(self) -> float:
        """Quarter bust plus ease (front/back panel width)."""
        return self.measurements.bust / 4 + EASE_CM

    @property
    def waist_width(self) -> float:
        """Quarter waist plus ease (panel width at the waistline)."""
        return self.measurements.waist / 4 + EASE_CM

    @property
    def shoulder_segment(self) -> float:
        """Half of the total shoulder width (one shoulder segment)."""
        return self.measurements.shoulder_width / 2

    @property
    def pattern_height(self) -> float:
        """Overall vertical height of the pattern (blouse length)."""
        return self.measurements.blouse_length

    @property
    def armhole_depth(self) -> float:
        """Armhole depth as supplied in the measurements."""
        return self.measurements.armhole_depth

    @property
    def sleeve_width(self) -> float:
        """Half upper-arm circumference plus 3 cm ease (SewMetrik prototype)."""
        return self.measurements.upper_arm_circumference / 2 + 3.0

    @property
    def sleeve_cap_height(self) -> float:
        """Sleeve cap height derived from armhole depth (SewMetrik prototype)."""
        return self.measurements.armhole_depth * 0.45

    def debug_dimensions(self) -> dict[str, float]:
        """Return the key calculated pattern dimensions as a dictionary."""
        return {
            "bodice_width": self.bodice_width,
            "waist_width": self.waist_width,
            "shoulder_segment": self.shoulder_segment,
            "pattern_height": self.pattern_height,
            "armhole_depth": self.armhole_depth,
        }

    def generate_back_bodice(self) -> BackBodice:
        """Generate the back bodice corner points from the measurements.

        Coordinate system:
          - (0, 0) is the top center-back
          - x increases toward the side seam
          - y increases downward
          - all values are centimetres

        The formulas below are SewMetrik prototype drafting assumptions, not
        official tailoring or NIFT standards.
        """
        # SewMetrik prototype drafting assumptions.
        neck_width = self.shoulder_segment * 0.35
        back_neck_depth = 3.0

        return BackBodice(
            center_back_neck=Point(0, 0),
            neck_end=Point(neck_width, back_neck_depth),
            shoulder_end=Point(self.shoulder_segment, 4.0),
            armhole_point=Point(self.bodice_width, self.armhole_depth * 0.45),
            underarm=Point(self.bodice_width, self.armhole_depth),
            waist_side=Point(self.waist_width, self.pattern_height),
            center_back_waist=Point(0, self.pattern_height),
        )

    def generate_back_bodice_geometry(
        self,
    ) -> dict[str, LineSegment | CubicBezier]:
        """Turn the back bodice points into a stitching-outline geometry.

        The outline is built entirely from the points produced by
        ``generate_back_bodice`` (no separate static coordinates). It consists
        of a curved neckline, a straight shoulder line, a curved armhole, the
        side seam, the waist line and the center-back line.

        All control-point factors below are SewMetrik prototype drafting
        assumptions, not official tailoring or NIFT standards.
        """
        b = self.generate_back_bodice()

        # Neckline: smooth curve from center_back_neck to neck_end. Control
        # points are derived from neck_width (neck_end.x) and back_neck_depth
        # (neck_end.y) so the curve leaves the center-back nearly vertically,
        # rounds through the neck, then arrives horizontally to join the
        # shoulder (SewMetrik prototype assumption).
        neckline = CubicBezier(
            start=b.center_back_neck,
            control1=Point(b.neck_end.x * 0.15, b.neck_end.y * 0.55),
            control2=Point(b.neck_end.x * 0.55, b.neck_end.y),
            end=b.neck_end,
        )

        # Shoulder: straight line from neck_end to shoulder_end.
        shoulder = LineSegment(start=b.neck_end, end=b.shoulder_end)

        # Armhole: smooth scye curve from shoulder_end to underarm. Control
        # points are interpolated toward armhole_point so the curve leaves the
        # shoulder gently, bows outward through the armhole region, and returns
        # into the side seam nearly vertically. Everything scales with
        # bodice_width and armhole_depth (SewMetrik prototype assumption).
        armhole = CubicBezier(
            start=b.shoulder_end,
            control1=Point(
                b.shoulder_end.x + (b.armhole_point.x - b.shoulder_end.x) * 0.65,
                b.shoulder_end.y + (b.armhole_point.y - b.shoulder_end.y) * 0.30,
            ),
            control2=Point(
                b.armhole_point.x,
                b.armhole_point.y + (b.underarm.y - b.armhole_point.y) * 0.55,
            ),
            end=b.underarm,
        )

        # Side seam: straight line from underarm down to the waist side.
        side_seam = LineSegment(start=b.underarm, end=b.waist_side)

        # Waist: straight line from waist side back to center-back waist.
        waist = LineSegment(start=b.waist_side, end=b.center_back_waist)

        # Center back: straight line from center-back waist up to the neck.
        center_back = LineSegment(
            start=b.center_back_waist, end=b.center_back_neck
        )

        return {
            "neckline": neckline,
            "shoulder": shoulder,
            "armhole": armhole,
            "side_seam": side_seam,
            "waist": waist,
            "center_back": center_back,
        }

    def generate_front_bodice(self) -> FrontBodice:
        """Generate the front bodice points (including the waist dart).

        Uses the same coordinate system and centimetres as the back bodice.
        The front neckline is deeper than the back, and a single waist dart is
        placed dynamically from ``waist_width``.

        All formulas below are SewMetrik prototype drafting assumptions, not
        official tailoring or NIFT standards.
        """
        # SewMetrik prototype drafting assumptions.
        neck_width = self.shoulder_segment * 0.35
        front_neck_depth = 7.5

        # Waist dart, positioned dynamically from the waist width.
        dart_center_x = self.waist_width * 0.55
        dart_width = 2.0

        return FrontBodice(
            center_front_neck=Point(0, 0),
            neck_end=Point(neck_width, front_neck_depth),
            shoulder_end=Point(self.shoulder_segment, 4.0),
            armhole_point=Point(self.bodice_width, self.armhole_depth * 0.45),
            underarm=Point(self.bodice_width, self.armhole_depth),
            waist_side=Point(self.waist_width, self.pattern_height),
            center_front_waist=Point(0, self.pattern_height),
            dart_left=Point(dart_center_x - dart_width / 2, self.pattern_height),
            dart_apex=Point(dart_center_x, self.pattern_height * 0.65),
            dart_right=Point(dart_center_x + dart_width / 2, self.pattern_height),
        )

    def generate_front_bodice_geometry(
        self,
    ) -> dict[str, LineSegment | CubicBezier]:
        """Turn the front bodice points into a stitching-outline geometry.

        The outer outline consists of a curved (deep) neckline, a straight
        shoulder, a shaped armhole, the side seam, the waist and the
        center-front line. The waist dart is returned as two separate internal
        line segments and is NOT part of the outer outline.

        All control-point factors below are SewMetrik prototype drafting
        assumptions, not official tailoring or NIFT standards.
        """
        f = self.generate_front_bodice()

        # Neckline: deep front scoop from center_front_neck to neck_end. It
        # leaves the center-front nearly vertically, rounds through the deeper
        # neck, then arrives horizontally to join the shoulder (SewMetrik
        # prototype assumption).
        neckline = CubicBezier(
            start=f.center_front_neck,
            control1=Point(f.neck_end.x * 0.12, f.neck_end.y * 0.60),
            control2=Point(f.neck_end.x * 0.55, f.neck_end.y),
            end=f.neck_end,
        )

        # Shoulder: straight line from neck_end to shoulder_end.
        shoulder = LineSegment(start=f.neck_end, end=f.shoulder_end)

        # Armhole: scye curve from shoulder_end to underarm, shaped slightly
        # deeper (more concave) than the back by pulling control1 inward. Still
        # scales with bodice_width and armhole_depth (SewMetrik prototype
        # assumption).
        armhole = CubicBezier(
            start=f.shoulder_end,
            control1=Point(
                f.shoulder_end.x + (f.armhole_point.x - f.shoulder_end.x) * 0.55,
                f.shoulder_end.y + (f.armhole_point.y - f.shoulder_end.y) * 0.40,
            ),
            control2=Point(
                f.armhole_point.x,
                f.armhole_point.y + (f.underarm.y - f.armhole_point.y) * 0.50,
            ),
            end=f.underarm,
        )

        # Side seam: straight line from underarm down to the waist side.
        side_seam = LineSegment(start=f.underarm, end=f.waist_side)

        # Waist: straight line from waist side back to center-front waist.
        waist = LineSegment(start=f.waist_side, end=f.center_front_waist)

        # Center front: straight line from center-front waist up to the neck.
        center_front = LineSegment(
            start=f.center_front_waist, end=f.center_front_neck
        )

        # Waist dart: two internal legs meeting at the apex (construction only).
        dart_left = LineSegment(start=f.dart_left, end=f.dart_apex)
        dart_right = LineSegment(start=f.dart_right, end=f.dart_apex)

        return {
            "neckline": neckline,
            "shoulder": shoulder,
            "armhole": armhole,
            "side_seam": side_seam,
            "waist": waist,
            "center_front": center_front,
            "dart_left": dart_left,
            "dart_right": dart_right,
        }

    def generate_sleeve(self) -> Sleeve:
        """Generate the symmetric sleeve points from the measurements.

        Coordinate system:
          - cap_center (0, 0) is the top-center of the sleeve cap
          - x increases to the right, y increases downward
          - all values are centimetres

        The sleeve reacts dynamically to sleeve_length, upper_arm_circumference
        and armhole_depth. All formulas are SewMetrik prototype drafting
        assumptions, not official tailoring or NIFT standards.
        """
        half_sleeve_width = self.sleeve_width / 2
        cap_height = self.sleeve_cap_height
        sleeve_length = self.measurements.sleeve_length

        # Hem is slightly narrower than the upper sleeve (SewMetrik prototype).
        hem_width = self.sleeve_width * 0.85
        half_hem_width = hem_width / 2

        return Sleeve(
            cap_center=Point(0, 0),
            cap_left=Point(-half_sleeve_width * 0.45, cap_height * 0.25),
            cap_right=Point(half_sleeve_width * 0.45, cap_height * 0.25),
            underarm_left=Point(-half_sleeve_width, cap_height),
            underarm_right=Point(half_sleeve_width, cap_height),
            hem_left=Point(-half_hem_width, sleeve_length),
            hem_right=Point(half_hem_width, sleeve_length),
        )

    def generate_sleeve_geometry(
        self,
    ) -> dict[str, LineSegment | CubicBezier]:
        """Turn the sleeve points into a symmetric stitching outline.

        The outline is built from two mirrored cap curves that meet smoothly at
        cap_center, two straight side seams and a straight hem. All control
        points are SewMetrik prototype drafting assumptions, not official
        tailoring or NIFT standards.
        """
        s = self.generate_sleeve()
        cap_height = self.sleeve_cap_height

        # Left cap: rises vertically from underarm_left, then turns in toward
        # cap_center, arriving horizontally so the two halves meet smoothly.
        cap_left_curve = CubicBezier(
            start=s.underarm_left,
            control1=Point(s.underarm_left.x, cap_height * 0.45),
            control2=Point(s.cap_left.x, s.cap_center.y),
            end=s.cap_center,
        )

        # Right cap: mirror of the left, leaving cap_center horizontally.
        cap_right_curve = CubicBezier(
            start=s.cap_center,
            control1=Point(s.cap_right.x, s.cap_center.y),
            control2=Point(s.underarm_right.x, cap_height * 0.45),
            end=s.underarm_right,
        )

        # Side seams from the underarm points down to the hem corners.
        side_seam_right = LineSegment(start=s.underarm_right, end=s.hem_right)
        side_seam_left = LineSegment(start=s.hem_left, end=s.underarm_left)

        # Straight hem across the bottom.
        hem = LineSegment(start=s.hem_right, end=s.hem_left)

        return {
            "cap_left_curve": cap_left_curve,
            "cap_right_curve": cap_right_curve,
            "side_seam_right": side_seam_right,
            "hem": hem,
            "side_seam_left": side_seam_left,
        }
