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


def _sample_nearest(image: Image.Image, xs: list[int], ys: list[int]) -> Image.Image:
    sampled = Image.new("RGBA", (len(xs), len(ys)), (0, 0, 0, 0))
    source = image.load()
    target = sampled.load()
    for y, sy in enumerate(ys):
        for x, sx in enumerate(xs):
            if sx < image.width and sy < image.height:
                target[x, y] = source[sx, sy]
    return sampled


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
    - Contact integers label pixel centers: source center ``c + 0.5`` maps
      to ``scale * (c + 0.5) + offset`` in pixel-edge coordinates. Its output
      pixel is selected with floor (center ties go toward positive infinity).
      Nearest sampling reads ``floor((d + 0.5) / scale)`` on both axes;
      ceil-sized output bounds do not change the scale. A contact must be an
      occupied source pixel and survive at its mapped output pixel, or fail.
    - Transform records with ``mappingVersion=2`` describe this sampling;
      ``scale`` remains the requested/resolved scale and ``offset`` the integer
      translation, not an effective width/height ratio.
    """
    image = load_rgba(image_bytes)
    source_core = measure_core(image_bytes, mask_bytes, core_color) if mask_bytes is not None else None
    mask = load_rgba(mask_bytes) if mask_bytes is not None else None
    source_ground = measure_ground(image_bytes, contact_points)
    for cx, cy in source_ground.contact_points or ():
        if not (0 <= cx < image.width and 0 <= cy < image.height):
            raise GeometryError(f"contact point ({cx},{cy}) is outside the source image")
        if image.getpixel((cx, cy))[3] == 0:
            raise GeometryError(f"contact point ({cx},{cy}) is not on an occupied source pixel")

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

    new_w = math.ceil(image.width * uniform_scale)
    new_h = math.ceil(image.height * uniform_scale)
    xs = [math.floor((x + 0.5) / uniform_scale) for x in range(new_w)]
    ys = [math.floor((y + 0.5) / uniform_scale) for y in range(new_h)]
    resized_image = _sample_nearest(image, xs, ys)
    resized_mask = _sample_nearest(mask, xs, ys) if mask is not None else None

    resized_alpha_bbox = alpha_bbox_of(resized_image)
    resized_core_bbox: BBox | None = None
    if resized_mask is not None:
        resized_core_bbox = core_bbox_of(resized_mask, core_color)
    resized_ref = resized_core_bbox if resized_core_bbox is not None else resized_alpha_bbox

    target_anchor_x = canvas_w // 2 if anchor_x is None else anchor_x
    offset_x = int(target_anchor_x) - (resized_ref.min_x + resized_ref.width // 2)
    offset_y = int(baseline_y) - resized_ref.max_y

    for label, sampled in (("image", resized_image), ("mask", resized_mask)):
        if sampled is None:
            continue
        bounds = alpha_bbox_of(sampled)
        if (bounds.min_x + offset_x < 0 or bounds.min_y + offset_y < 0
                or bounds.max_x + offset_x >= canvas_w or bounds.max_y + offset_y >= canvas_h):
            raise GeometryError(
                f"transform overflow: {label} content would fall outside the canvas "
                f"(canvas={canvas_w}x{canvas_h}, offset=({offset_x},{offset_y}))"
            )

    transformed_contacts: list[tuple[int, int]] | None = None
    if source_ground.contact_points is not None:
        transformed_contacts = []
        for cx, cy in source_ground.contact_points:
            x = math.floor((cx + 0.5) * uniform_scale)
            y = math.floor((cy + 0.5) * uniform_scale)
            if not (0 <= x < new_w and 0 <= y < new_h) or (xs[x], ys[y]) != (cx, cy):
                raise GeometryError(f"contact point ({cx},{cy}) is lost by nearest sampling")
            tx, ty = x + offset_x, y + offset_y
            if not (0 <= tx < canvas_w and 0 <= ty < canvas_h):
                raise GeometryError(f"transformed contact point ({tx},{ty}) is outside the canvas")
            transformed_contacts.append((tx, ty))

    placed = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    placed.paste(resized_image, (offset_x, offset_y))
    placed_mask: Image.Image | None = None
    if resized_mask is not None:
        placed_mask = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        placed_mask.paste(resized_mask, (offset_x, offset_y))

    source_alpha = OutlineMeasure(bbox=source_alpha_bbox)
    target_alpha = OutlineMeasure(bbox=alpha_bbox_of(placed))
    target_core = (
        measure_core(dump_png(placed), dump_png(placed_mask), core_color)
        if placed_mask is not None
        else None
    )

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
        sampling={
            "coordinateConvention": "integer labels pixel center at index + 0.5",
            "filter": "nearest",
            "sourceIndex": "floor((targetIndex + 0.5) / scale)",
            "contactIndex": "floor((sourceIndex + 0.5) * scale) + offset",
            "sizeRounding": "ceil",
            "outsideSource": "transparent",
            "sourceSize": {"width": image.width, "height": image.height},
            "sampledSize": {"width": new_w, "height": new_h},
        },
    )
