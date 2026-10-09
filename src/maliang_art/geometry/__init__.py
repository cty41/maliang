"""Bounded geometry slice: measure, transform, compare, and review board.

S5 evidence split:
- core: user-confirmed body region from a same-size semantic mask
- full outline: alpha bbox for crop / margin / canvas occupancy
- ground: lowest non-transparent y plus optional declared contact points

Core is never inferred from alpha. Transforms are uniform scale plus integer
translation only; overflow and non-uniform scale are rejected.
"""
from __future__ import annotations

from .compare import compare_core
from .errors import GeometryError, MissingMaskError
from .measure import measure_alpha_bbox, measure_core, measure_ground
from .report import render_review_board
from .transform import fit_uniform
from .types import BBox, CoreMeasure, FitResult, GroundMeasure, OutlineMeasure

__all__ = [
    "BBox",
    "CoreMeasure",
    "FitResult",
    "GeometryError",
    "GroundMeasure",
    "MissingMaskError",
    "OutlineMeasure",
    "compare_core",
    "fit_uniform",
    "measure_alpha_bbox",
    "measure_core",
    "measure_ground",
    "render_review_board",
]
