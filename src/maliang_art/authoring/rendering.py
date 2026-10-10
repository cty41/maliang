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
    sign = 1 if view == "DR" else -1
    draw.polygon([(cx + sign * dx, cy + sign * dy), (cx - sign * dx, cy), (cx, cy - sign * dy)], fill="#FFFFFF")
    out = BytesIO()
    image.save(out, format="PNG", optimize=False, compress_level=9)
    return out.getvalue()
