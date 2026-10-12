"""Core, full-outline, and ground measurements for game-art candidates."""
from __future__ import annotations

import io
from typing import Iterable, Sequence

from PIL import Image

from .errors import GeometryError, MissingMaskError
from .types import BBox, CoreMeasure, GroundMeasure, OutlineMeasure

DEFAULT_CORE_COLOR = (255, 0, 0, 255)


def load_rgba(data: bytes | bytearray | memoryview) -> Image.Image:
    if not isinstance(data, (bytes, bytearray, memoryview)) or not data:
        raise GeometryError("image bytes must be non-empty")
    try:
        with Image.open(io.BytesIO(bytes(data))) as image:
            return image.convert("RGBA")
    except GeometryError:
        raise
    except Exception as exc:  # noqa: BLE001 - decode failures become GeometryError
        raise GeometryError(f"cannot decode image: {exc}") from exc


def dump_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=9)
    return buffer.getvalue()


def _is_opaque_pixel(pixel: tuple[int, int, int, int]) -> bool:
    return pixel[3] > 0


def alpha_bbox_of(image: Image.Image) -> BBox:
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    min_x = image.width
    min_y = image.height
    max_x = -1
    max_y = -1
    for y in range(image.height):
        for x in range(image.width):
            if _is_opaque_pixel(image.getpixel((x, y))):  # type: ignore[arg-type]
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if max_x < 0 or max_y < 0:
        raise GeometryError("image has no non-transparent pixels")
    return BBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)


def _normalize_color(color: Sequence[int] | Iterable[int]) -> tuple[int, int, int, int]:
    values = tuple(color)
    if len(values) == 3:
        values = (*values, 255)
    if len(values) != 4:
        raise GeometryError("core_color must be RGB or RGBA")
    try:
        rgba = tuple(int(channel) for channel in values)
    except (TypeError, ValueError) as exc:
        raise GeometryError("core_color must be integers") from exc
    if any(channel < 0 or channel > 255 for channel in rgba):
        raise GeometryError("core_color channels must be in 0..255")
    return rgba  # type: ignore[return-value]


def core_pixels(mask: Image.Image, core_color: Sequence[int] = DEFAULT_CORE_COLOR) -> list[tuple[int, int]]:
    color = _normalize_color(core_color)
    if mask.mode != "RGBA":
        mask = mask.convert("RGBA")
    hits: list[tuple[int, int]] = []
    for y in range(mask.height):
        for x in range(mask.width):
            if mask.getpixel((x, y)) == color:  # type: ignore[arg-type]
                hits.append((x, y))
    return hits


def core_bbox_of(mask: Image.Image, core_color: Sequence[int] = DEFAULT_CORE_COLOR) -> BBox:
    hits = core_pixels(mask, core_color)
    if not hits:
        raise GeometryError("mask contains no core pixels for the requested core_color")
    xs = [point[0] for point in hits]
    ys = [point[1] for point in hits]
    return BBox(min_x=min(xs), min_y=min(ys), max_x=max(xs), max_y=max(ys))


def _section_widths(hits: Sequence[tuple[int, int]], bbox: BBox) -> tuple[int, int, int]:
    height = bbox.height
    widths: list[int] = []
    for index in range(3):
        y0 = bbox.min_y + (height * index) // 3
        y1 = bbox.min_y + (height * (index + 1)) // 3
        if index == 2:
            y1 = bbox.max_y + 1
        xs = [x for x, y in hits if y0 <= y < y1]
        if not xs:
            widths.append(0)
        else:
            widths.append(max(xs) - min(xs) + 1)
    return (widths[0], widths[1], widths[2])


def measure_alpha_bbox(image_bytes: bytes) -> OutlineMeasure:
    """Full outline bbox/width/height/center from non-transparent pixels."""
    image = load_rgba(image_bytes)
    return OutlineMeasure(bbox=alpha_bbox_of(image))


def measure_core(
    image_bytes: bytes,
    mask_bytes: bytes | None,
    core_color: Sequence[int] = DEFAULT_CORE_COLOR,
) -> CoreMeasure:
    """Core bbox/height/width/center/section widths from a same-size semantic mask.

    Core is never inferred from alpha. A missing mask is an error (or a pending
    status at the caller); it must not be replaced by the full outline bbox.
    Every selected core pixel must overlap a non-transparent candidate pixel.
    """
    if mask_bytes is None or (isinstance(mask_bytes, (bytes, bytearray, memoryview)) and not mask_bytes):
        raise MissingMaskError("measure_core requires a semantic mask; alpha bbox is not core")
    image = load_rgba(image_bytes)
    mask = load_rgba(mask_bytes)
    if image.size != mask.size:
        raise GeometryError("mask must be the same size as the image")
    hits = core_pixels(mask, core_color)
    if not hits:
        raise GeometryError("mask contains no core pixels for the requested core_color")
    if any(image.getpixel((x, y))[3] == 0 for x, y in hits):
        raise GeometryError("core mask pixels must overlap non-transparent image pixels")
    bbox = core_bbox_of(mask, core_color)
    return CoreMeasure(bbox=bbox, section_widths=_section_widths(hits, bbox))


def _parse_contact_points(contact_points: Sequence[Sequence[int]] | None) -> tuple[tuple[int, int], ...] | None:
    if contact_points is None:
        return None
    parsed: list[tuple[int, int]] = []
    for index, point in enumerate(contact_points):
        try:
            x, y = point
            ix = int(x)
            iy = int(y)
        except (TypeError, ValueError, OverflowError) as exc:
            raise GeometryError(f"contact_points[{index}] must be an (x, y) integer pair") from exc
        if isinstance(x, bool) or isinstance(y, bool) or ix != x or iy != y:
            raise GeometryError(f"contact_points[{index}] must be integers")
        parsed.append((ix, iy))
    return tuple(parsed)


def measure_ground(
    image_bytes: bytes,
    contact_points: Sequence[Sequence[int]] | None = None,
) -> GroundMeasure:
    """Lowest non-transparent y plus optional declared contact points.

    The lowest pixel is evidence only; it is never treated as the foot/ground
    unless contact points are declared.
    """
    image = load_rgba(image_bytes)
    lowest: int | None = None
    for y in range(image.height - 1, -1, -1):
        found = False
        for x in range(image.width):
            if _is_opaque_pixel(image.getpixel((x, y))):  # type: ignore[arg-type]
                found = True
                break
        if found:
            lowest = y
            break
    declared = _parse_contact_points(contact_points)
    status = "declared" if declared is not None else "pending"
    return GroundMeasure(
        lowest_nontransparent_y=lowest,
        contact_points=declared,
        status=status,
    )
