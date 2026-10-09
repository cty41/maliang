"""Deterministic multi-cell review board for DR/UL / 4-dir comparison."""
from __future__ import annotations

import io
import math
from typing import Any, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont

from .errors import GeometryError
from .measure import load_rgba

_LABEL_HEIGHT = 12
_PADDING = 2
_BACKGROUND = (245, 245, 245, 255)
_LABEL_BAND = (220, 220, 220, 255)
_TEXT = (20, 20, 20, 255)
_DIVIDER = (160, 160, 160, 255)


def _normalize_cell_size(cell_size: int | Sequence[int]) -> tuple[int, int]:
    if isinstance(cell_size, bool):
        raise GeometryError("cell_size must be a positive integer or (width, height)")
    if isinstance(cell_size, int):
        if cell_size <= 0:
            raise GeometryError("cell_size must be positive")
        return cell_size, cell_size
    try:
        width_raw, height_raw = cell_size
        width = int(width_raw)
        height = int(height_raw)
    except (TypeError, ValueError) as exc:
        raise GeometryError("cell_size must be a positive integer or (width, height)") from exc
    if width != width_raw or height != height_raw or width <= 0 or height <= 0:
        raise GeometryError("cell_size must be a positive integer or (width, height)")
    return width, height


def _fit_into(image: Image.Image, box_w: int, box_h: int) -> Image.Image:
    if image.width <= 0 or image.height <= 0:
        raise GeometryError("candidate image has invalid size")
    if box_w <= 0 or box_h <= 0:
        raise GeometryError("cell art area must be positive")
    scale = min(box_w / image.width, box_h / image.height)
    if scale >= 1.0:
        new_w = image.width
        new_h = image.height
    else:
        new_w = max(1, int(math.floor(image.width * scale)))
        new_h = max(1, int(math.floor(image.height * scale)))
    if (new_w, new_h) != image.size:
        image = image.resize((new_w, new_h), resample=Image.Resampling.NEAREST)
    framed = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    framed.paste(image, ((box_w - new_w) // 2, (box_h - new_h) // 2))
    return framed


def render_review_board(
    candidates: Sequence[Mapping[str, Any]],
    cell_size: int | Sequence[int],
    columns: int,
) -> bytes:
    """Render a deterministic multi-cell comparison board as PNG bytes.

    Pure function: no filesystem writes, no clock, no randomness. The same
    candidates, cell_size, and columns always produce identical bytes.
    """
    if not candidates:
        raise GeometryError("candidates must be non-empty")
    if isinstance(columns, bool) or not isinstance(columns, int) or columns < 1:
        raise GeometryError("columns must be a positive integer")

    cell_w, cell_h = _normalize_cell_size(cell_size)
    label_h = min(_LABEL_HEIGHT, max(1, cell_h // 4))
    art_h = cell_h - label_h
    if art_h <= 0:
        raise GeometryError("cell_size height must leave room for the label band")
    pad = min(_PADDING, max(0, (min(cell_w, art_h) - 1) // 2))
    art_box_w = max(1, cell_w - 2 * pad)
    art_box_h = max(1, art_h - 2 * pad)

    prepared: list[tuple[Image.Image, str]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise GeometryError(f"candidates[{index}] must be a mapping")
        raw = candidate.get("image_bytes", candidate.get("image"))
        if raw is None:
            raise GeometryError(f"candidates[{index}] is missing image_bytes")
        label = candidate.get("label", "")
        if label is None:
            label = ""
        if not isinstance(label, str):
            label = str(label)
        image = load_rgba(raw)
        prepared.append((_fit_into(image, art_box_w, art_box_h), label))

    rows = (len(prepared) + columns - 1) // columns
    board_w = columns * cell_w
    board_h = rows * cell_h
    board = Image.new("RGBA", (board_w, board_h), _BACKGROUND)
    draw = ImageDraw.Draw(board)
    font = ImageFont.load_default()

    for index, (art, label) in enumerate(prepared):
        row, col = divmod(index, columns)
        origin_x = col * cell_w
        origin_y = row * cell_h
        # Label band.
        draw.rectangle(
            (origin_x, origin_y + art_h, origin_x + cell_w - 1, origin_y + cell_h - 1),
            fill=_LABEL_BAND,
        )
        # Art.
        board.paste(art, (origin_x + pad, origin_y + pad), art)
        # Label text, clipped deterministically.
        draw.text(
            (origin_x + cell_w // 2, origin_y + art_h + label_h // 2),
            label[:24],
            fill=_TEXT,
            font=font,
            anchor="mm",
        )
        # Cell border.
        draw.rectangle(
            (origin_x, origin_y, origin_x + cell_w - 1, origin_y + cell_h - 1),
            outline=_DIVIDER,
        )

    buffer = io.BytesIO()
    board.save(buffer, format="PNG", optimize=False, compress_level=9)
    return buffer.getvalue()
