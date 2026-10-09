"""Per-dimension core comparison with caller-supplied tolerance."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .errors import GeometryError
from .types import CoreMeasure

DIMENSION_NAMES = (
    "width",
    "height",
    "centerX",
    "centerY",
    "sectionTopWidth",
    "sectionMidWidth",
    "sectionBottomWidth",
)


def _dimension_values(core: CoreMeasure) -> dict[str, float]:
    cx, cy = core.center
    top, mid, bottom = core.section_widths
    return {
        "width": float(core.width),
        "height": float(core.height),
        "centerX": float(cx),
        "centerY": float(cy),
        "sectionTopWidth": float(top),
        "sectionMidWidth": float(mid),
        "sectionBottomWidth": float(bottom),
    }


def _as_core_measure(value: CoreMeasure | Mapping[str, Any]) -> CoreMeasure:
    if isinstance(value, CoreMeasure):
        return value
    if isinstance(value, Mapping):
        try:
            bbox_raw = value["bbox"]
            if isinstance(bbox_raw, Mapping):
                min_x = int(bbox_raw["minX"])
                min_y = int(bbox_raw["minY"])
                max_x = int(bbox_raw["maxX"])
                max_y = int(bbox_raw["maxY"])
            else:
                min_x, min_y, max_x, max_y = (int(part) for part in bbox_raw)
            sections = value.get("sectionWidths")
            if isinstance(sections, Mapping):
                section_widths = (
                    int(sections["top"]),
                    int(sections["mid"]),
                    int(sections["bottom"]),
                )
            elif isinstance(sections, Sequence) and not isinstance(sections, (str, bytes)):
                top, mid, bottom = (int(part) for part in sections)
                section_widths = (top, mid, bottom)
            else:
                raise GeometryError("core measure is missing sectionWidths")
            from .types import BBox

            return CoreMeasure(
                bbox=BBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y),
                section_widths=section_widths,
            )
        except GeometryError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise GeometryError(f"cannot read core measure mapping: {exc}") from exc
    raise GeometryError("core measure must be a CoreMeasure or mapping")


def _tolerance_for(name: str, tolerance: float | Mapping[str, float]) -> float:
    if isinstance(tolerance, Mapping):
        if name not in tolerance:
            raise GeometryError(f"tolerance mapping is missing dimension {name!r}")
        try:
            value = float(tolerance[name])
        except (TypeError, ValueError) as exc:
            raise GeometryError(f"tolerance for {name!r} must be numeric") from exc
    else:
        try:
            value = float(tolerance)
        except (TypeError, ValueError) as exc:
            raise GeometryError("tolerance must be numeric or a dimension mapping") from exc
    if not math.isfinite(value) or value < 0:
        raise GeometryError("tolerance must be a finite non-negative number")
    return value


def compare_core(
    a_measure: CoreMeasure | Mapping[str, Any],
    b_measure: CoreMeasure | Mapping[str, Any],
    tolerance: float | Mapping[str, float],
) -> dict[str, Any]:
    """Compare two core measures per dimension using the caller's tolerance.

    Tolerance is project policy and must be supplied; nothing is hardcoded here.
    """
    if isinstance(tolerance, bool) or (not isinstance(tolerance, (int, float, Mapping))):
        raise GeometryError("tolerance must be numeric or a dimension mapping")

    a = _as_core_measure(a_measure)
    b = _as_core_measure(b_measure)
    a_values = _dimension_values(a)
    b_values = _dimension_values(b)

    dimensions: dict[str, dict[str, Any]] = {}
    passed = True
    for name in DIMENSION_NAMES:
        limit = _tolerance_for(name, tolerance)
        left = a_values[name]
        right = b_values[name]
        delta = abs(left - right)
        ok = delta <= limit
        if not ok:
            passed = False
        dimensions[name] = {
            "a": left if name not in {"width", "height", "sectionTopWidth", "sectionMidWidth", "sectionBottomWidth"} else int(left),
            "b": right if name not in {"width", "height", "sectionTopWidth", "sectionMidWidth", "sectionBottomWidth"} else int(right),
            "delta": int(delta) if delta == int(delta) else delta,
            "tolerance": int(limit) if limit == int(limit) else limit,
            "passed": ok,
        }

    return {"passed": passed, "dimensions": dimensions}
