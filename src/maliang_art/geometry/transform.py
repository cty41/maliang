"""Uniform scale + integer translation fit with overflow rejection."""
from __future__ import annotations

import math
from typing import Sequence

from PIL import Image

from .errors import GeometryError
from .measure import (
    DEFAULT_CORE_COLOR,
    alpha_bbox_of,
    core_bbox_of,
    dump_png,
    load_rgba,
    measure_core,
    measure_ground,
)
from .types import BBox, FitResult, OutlineMeasure


def _normalize_scale(scale: float | Sequence[float] | None) -> float | None:
    if scale is None:
        return None
    if isinstance(scale, bool):
        raise GeometryError("scale must be a number or a pair of equal numbers")
    if isinstance(scale, (int, float)):
        value = float(scale)
        if not math.isfinite(value) or value <= 0:
            raise GeometryError("scale must be a positive finite number")
        return value
    if isinstance(scale, (list, tuple)) and len(scale) == 2:
        try:
            sx = float(scale[0])
            sy = float(scale[1])
        except (TypeError, ValueError) as exc:
            raise GeometryError("scale pair must be numeric") from exc
        if not (math.isfinite(sx) and math.isfinite(sy)) or sx <= 0 or sy <= 0:
            raise GeometryError("scale must be positive finite numbers")
        if sx != sy:
            raise GeometryError("non-uniform scale is not allowed")
        return sx
    raise GeometryError("scale must be a number or a pair of equal numbers")


def _normalize_canvas(canvas: Sequence[int]) -> tuple[int, int]:
    try:
        width_raw, height_raw = canvas
        width = int(width_raw)
        height = int(height_raw)
    except (TypeError, ValueError) as exc:
        raise GeometryError("canvas must be a pair of positive integers") from exc
    if width != width_raw or height != height_raw:
        raise GeometryError("canvas must be a pair of positive integers")
    if width <= 0 or height <= 0:
        raise GeometryError("canvas must be a pair of positive integers")
    return width, height


def _resize_nearest(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image.copy()
    return image.resize(size, resample=Image.Resampling.NEAREST)


def fit_uniform(
    image_bytes: bytes,
    mask_bytes: bytes | None = None,
    canvas: Sequence[int] = (256, 256),
    baseline_y: int | None = None,
    target_height: int | None = None,
    anchor_x: int | None = None,
    scale: float | Sequence[float] | None = None,
    *,
    contact_points: Sequence[Sequence[int]] | None = None,
    core_color: Sequence[int] = DEFAULT_CORE_COLOR,
) -> FitResult:
    """Fit a candidate on a canvas with uniform scale and integer translation only.

    - ``baseline_y`` is required; project landing values are caller policy,
      not a library default.
    - ``scale`` accepts a number or an equal pair; unequal pairs are rejected
      (non-uniform scale is never applied).
    - Overflow (any non-transparent pixel outside the canvas) is an error;
      silent crop is forbidden.
    - When ``mask_bytes`` is provided, core evidence from the semantic mask is
      used for anchoring. When it is absent, alpha outline is used for fitting
      and core fields stay empty — alpha is never pretended to be core.
    - ``contact_points`` share the same scale+offset as image and mask.
    """
    image = load_rgba(image_bytes)
    mask = load_rgba(mask_bytes) if mask_bytes else None
    if mask is not None and mask.size != image.size:
        raise GeometryError("mask must be the same size as the image")

    canvas_w, canvas_h = _normalize_canvas(canvas)
    if baseline_y is None:
        raise GeometryError("baseline_y is required; project landing values are caller policy")
    if isinstance(baseline_y, bool) or not isinstance(baseline_y, int):
        raise GeometryError("baseline_y must be an integer")
    if anchor_x is not None and (isinstance(anchor_x, bool) or not isinstance(anchor_x, int)):
        raise GeometryError("anchor_x must be an integer or None")

    explicit_scale = _normalize_scale(scale)
    if explicit_scale is not None and target_height is not None:
        raise GeometryError("provide either scale or target_height, not both")
    if target_height is not None and (isinstance(target_height, bool) or not isinstance(target_height, int) or target_height <= 0):
        raise GeometryError("target_height must be a positive integer")

    source_alpha_bbox = alpha_bbox_of(image)
    source_core_bbox: BBox | None = None
    if mask is not None:
        source_core_bbox = core_bbox_of(mask, core_color)

    # Reference region: core when a mask is present, otherwise full alpha.
    ref_bbox = source_core_bbox if source_core_bbox is not None else source_alpha_bbox

    if explicit_scale is not None:
        uniform_scale = explicit_scale
    elif target_height is not None:
        if ref_bbox.height <= 0:
            raise GeometryError("reference region has no height to scale")
        uniform_scale = target_height / ref_bbox.height
    else:
        uniform_scale = 1.0

    if not math.isfinite(uniform_scale) or uniform_scale <= 0:
        raise GeometryError("resolved scale must be a positive finite number")

    new_w = max(1, int(round(image.width * uniform_scale)))
    new_h = max(1, int(round(image.height * uniform_scale)))
    resized_image = _resize_nearest(image, (new_w, new_h))
    resized_mask = _resize_nearest(mask, (new_w, new_h)) if mask is not None else None

    resized_alpha_bbox = alpha_bbox_of(resized_image)
    resized_core_bbox: BBox | None = None
    if resized_mask is not None:
        resized_core_bbox = core_bbox_of(resized_mask, core_color)
    resized_ref = resized_core_bbox if resized_core_bbox is not None else resized_alpha_bbox

    target_anchor_x = canvas_w // 2 if anchor_x is None else anchor_x
    offset_x = int(target_anchor_x) - (resized_ref.min_x + resized_ref.width // 2)
    offset_y = int(baseline_y) - resized_ref.max_y

    # Overflow check: every non-transparent pixel must land inside the canvas.
    out_of_bounds = False
    pixels = resized_image.load()
    assert pixels is not None
    for y in range(new_h):
        row_oob = False
        for x in range(new_w):
            if pixels[x, y][3] > 0:  # type: ignore[index]
                tx = x + offset_x
                ty = y + offset_y
                if tx < 0 or ty < 0 or tx >= canvas_w or ty >= canvas_h:
                    out_of_bounds = True
                    row_oob = True
                    break
        if row_oob:
            break
    if out_of_bounds:
        raise GeometryError(
            "transform overflow: content would fall outside the canvas "
            f"(canvas={canvas_w}x{canvas_h}, offset=({offset_x},{offset_y}))"
        )

    placed = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    placed.paste(resized_image, (offset_x, offset_y))
    placed_mask: Image.Image | None = None
    if resized_mask is not None:
        placed_mask = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        placed_mask.paste(resized_mask, (offset_x, offset_y))

    source_alpha = OutlineMeasure(bbox=source_alpha_bbox)
    target_alpha = OutlineMeasure(bbox=alpha_bbox_of(placed))
    source_core = measure_core(image_bytes, mask_bytes, core_color) if mask is not None else None
    target_core = (
        measure_core(dump_png(placed), dump_png(placed_mask), core_color)
        if placed_mask is not None
        else None
    )
    source_ground = measure_ground(image_bytes, contact_points)

    # Transform contact points with the same scale+offset as image and mask.
    transformed_contacts: list[tuple[int, int]] | None = None
    if contact_points is not None:
        transformed_contacts = []
        for cp in contact_points:
            try:
                cx_raw, cy_raw = cp
                cx = int(cx_raw)
                cy = int(cy_raw)
            except (TypeError, ValueError) as exc:
                raise GeometryError("contact points must be integer [x,y] pairs") from exc
            if cx != cx_raw or cy != cy_raw:
                raise GeometryError("contact points must be integer [x,y] pairs")
            transformed_contacts.append((
                int(round(cx * uniform_scale)) + offset_x,
                int(round(cy * uniform_scale)) + offset_y,
            ))
        transformed_contacts = tuple(transformed_contacts)

    target_ground = measure_ground(dump_png(placed), transformed_contacts)

    return FitResult(
        image_bytes=dump_png(placed),
        mask_bytes=None if placed_mask is None else dump_png(placed_mask),
        scale=float(uniform_scale),
        offset_x=int(offset_x),
        offset_y=int(offset_y),
        source_core=source_core,
        target_core=target_core,
        source_alpha=source_alpha,
        target_alpha=target_alpha,
        source_ground=source_ground,
        target_ground=target_ground,
    )
