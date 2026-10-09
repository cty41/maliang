"""Measurement and transform result types."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BBox:
    """Inclusive pixel bounding box."""

    min_x: int
    min_y: int
    max_x: int
    max_y: int

    @property
    def width(self) -> int:
        return self.max_x - self.min_x + 1

    @property
    def height(self) -> int:
        return self.max_y - self.min_y + 1

    @property
    def center(self) -> tuple[float, float]:
        """Geometric center in continuous coordinates (pixel i covers [i, i+1))."""
        return (self.min_x + self.width / 2.0, self.min_y + self.height / 2.0)

    def as_dict(self) -> dict[str, int]:
        return {
            "minX": self.min_x,
            "minY": self.min_y,
            "maxX": self.max_x,
            "maxY": self.max_y,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> BBox:
        return cls(
            min_x=int(value["minX"]),
            min_y=int(value["minY"]),
            max_x=int(value["maxX"]),
            max_y=int(value["maxY"]),
        )


@dataclass(frozen=True, slots=True)
class OutlineMeasure:
    """Full alpha outline: bbox plus derived size and center."""

    bbox: BBox

    @property
    def width(self) -> int:
        return self.bbox.width

    @property
    def height(self) -> int:
        return self.bbox.height

    @property
    def center(self) -> tuple[float, float]:
        return self.bbox.center

    @property
    def center_x(self) -> float:
        return self.bbox.center[0]

    @property
    def center_y(self) -> float:
        return self.bbox.center[1]

    def as_dict(self) -> dict[str, Any]:
        cx, cy = self.center
        return {
            "bbox": self.bbox.as_dict(),
            "width": self.width,
            "height": self.height,
            "center": {"x": cx, "y": cy},
        }


@dataclass(frozen=True, slots=True)
class CoreMeasure:
    """Semantic core metrics bound to a same-size mask."""

    bbox: BBox
    section_widths: tuple[int, int, int]

    @property
    def width(self) -> int:
        return self.bbox.width

    @property
    def height(self) -> int:
        return self.bbox.height

    @property
    def center(self) -> tuple[float, float]:
        return self.bbox.center

    @property
    def center_x(self) -> float:
        return self.bbox.center[0]

    @property
    def center_y(self) -> float:
        return self.bbox.center[1]

    def as_dict(self) -> dict[str, Any]:
        cx, cy = self.center
        return {
            "bbox": self.bbox.as_dict(),
            "width": self.width,
            "height": self.height,
            "center": {"x": cx, "y": cy},
            "sectionWidths": {
                "top": self.section_widths[0],
                "mid": self.section_widths[1],
                "bottom": self.section_widths[2],
            },
        }


@dataclass(frozen=True, slots=True)
class GroundMeasure:
    """Lowest non-transparent y plus optional declared contact points."""

    lowest_nontransparent_y: int | None
    contact_points: tuple[tuple[int, int], ...] | None
    status: str  # "pending" | "declared"

    def as_dict(self) -> dict[str, Any]:
        return {
            "lowestNontransparentY": self.lowest_nontransparent_y,
            "contactPoints": (
                None
                if self.contact_points is None
                else [{"x": x, "y": y} for x, y in self.contact_points]
            ),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class FitResult:
    """Uniform-scale + integer-translation fit with full measurement lineage."""

    image_bytes: bytes
    mask_bytes: bytes | None
    scale: float
    offset_x: int
    offset_y: int
    source_core: CoreMeasure | None
    target_core: CoreMeasure | None
    source_alpha: OutlineMeasure
    target_alpha: OutlineMeasure
    source_ground: GroundMeasure | None
    target_ground: GroundMeasure | None

    @property
    def transform_record(self) -> dict[str, Any]:
        return {
            "scale": self.scale,
            "offset": {"x": self.offset_x, "y": self.offset_y},
            "sourceCoreBbox": None if self.source_core is None else self.source_core.bbox.as_dict(),
            "targetCoreBbox": None if self.target_core is None else self.target_core.bbox.as_dict(),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "transform": self.transform_record,
            "source": {
                "alpha": self.source_alpha.as_dict(),
                "core": None if self.source_core is None else self.source_core.as_dict(),
                "ground": None if self.source_ground is None else self.source_ground.as_dict(),
            },
            "target": {
                "alpha": self.target_alpha.as_dict(),
                "core": None if self.target_core is None else self.target_core.as_dict(),
                "ground": None if self.target_ground is None else self.target_ground.as_dict(),
            },
        }
