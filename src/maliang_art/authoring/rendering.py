"""Unapproved debug layouts, never generation references or projection proofs."""
from __future__ import annotations

from io import BytesIO
from PIL import Image, ImageDraw


def geometry(variant: dict, shape: str, targets: dict, topology: dict) -> dict:
    """Core fractions use source dimensions; parts use core-local coordinates."""
    sw, sh = targets["sourceSize"]
    width, height = sw * variant["coreWidth"], sh * variant["coreHeight"]
    if shape == "ball":
        width = height = min(width, height)
    left = targets["anchorX"] - width / 2
    top = targets["groundY"] - height
    core = [left, top, left + width, top + height]
    parts = []
    for part in topology["parts"]:
        cx, cy = left + part["anchor"][0] * width, top + part["anchor"][1] * height
        pw, ph = part["size"][0] * width, part["size"][1] * height
        parts.append({"id": part["id"], "bounds": [cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2]})
    return {"shape": shape, "coreBounds": core, "parts": parts, "radius": min(width, height) / 2}


_VIEW_VECTORS = {"DR": (1, 1), "UL": (-1, -1), "R": (1, 0), "D": (0, 1), "U": (0, -1), "F": (0, 0)}


def render_blockout(parameters: dict, size: list[int], view: str) -> bytes:
    image = Image.new("RGBA", tuple(size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    bounds = tuple(round(x) for x in parameters["coreBounds"])
    if parameters["shape"] == "ball":
        draw.ellipse(bounds, fill="#303030")
    else:
        draw.rounded_rectangle(bounds, radius=round(parameters["radius"]), fill="#303030")
    for part in parameters["parts"]:
        draw.ellipse(tuple(round(x) for x in part["bounds"]), fill="#606060")
    left, top, right, bottom = bounds
    cx, cy = (left + right) // 2, (top + bottom) // 2
    dx = max(1, (right - left) // 5)
    dy = max(1, (bottom - top) // 5)
    vx, vy = _VIEW_VECTORS.get(view, (0, 0))
    if (vx, vy) == (0, 0):
        draw.ellipse((cx - dx // 2, cy - dx // 2, cx + dx // 2, cy + dx // 2), fill="#FFFFFF")
    elif vx and vy:
        draw.polygon([(cx + vx * dx, cy + vy * dy), (cx - vx * dx, cy), (cx, cy - vy * dy)], fill="#FFFFFF")
    else:
        tip = (cx + vx * dx, cy + vy * dy)
        base = [(cx - vy * dx // 2 - vx * dx // 2, cy - vx * dy // 2 - vy * dy // 2),
                (cx + vy * dx // 2 - vx * dx // 2, cy + vx * dy // 2 - vy * dy // 2)]
        draw.polygon([tip, *base], fill="#FFFFFF")
    out = BytesIO()
    image.save(out, format="PNG", optimize=False, compress_level=9)
    return out.getvalue()
