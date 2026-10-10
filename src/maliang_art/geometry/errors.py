"""Geometry errors for the bounded measure/transform/compare slice."""
from __future__ import annotations

from ..core import MaLiangError


class GeometryError(MaLiangError):
    """Invalid geometry input or a refused transform."""


class MissingMaskError(GeometryError):
    """Core evidence requires a semantic mask; alpha alone is never core."""
