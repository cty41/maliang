"""Rebuild the uniform gallery thumbnails and thumbs.json from repository images."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SIZE = (480, 360)
BACKGROUND = "#F4F1EA"
MARGIN = 16
KEYED = {"falcon", "crested-goshawk"}
SOURCES = {
    "little-orange-sprite": "examples/little-orange/candidates/orange-front-003-sprite.png",
    "falcon": "examples/art-pilot/characters/falcon-idle/raw/codex-idle.png",
    "crested-goshawk": "examples/art-pilot/characters/crested-goshawk-idle/raw/v01-a001.png",
    "five-red-chow-poet": "examples/poet-cast/store/Tools/artworks/poet_five_red_chow/calibrated/"
                          "poet_five_red_chow_ring_pommel_dao_idle_dr_v03.png",
    "gamemancer": "examples/gamemancer/gamemancer.jpg",
    "five-red-chow-poet-cast": "examples/poet-cast/store/Tools/artworks/poet_five_red_chow/calibrated/"
                               "poet_five_red_chow_cast_dr_vertical_guard_grip_v01.png",
    "red-shiba-amazon": "examples/tactics-amazon/doge_hunter_death.png",
}


def thumbnail(data: bytes, keyed: bool) -> bytes:
    with Image.open(io.BytesIO(data)) as source:
        image = source.convert("RGBA")
    r, g, b, _ = image.getpixel((0, 0))
    if keyed:
        pixels = image.load()
        for y in range(image.height):
            for x in range(image.width):
                pr, pg, pb, _ = pixels[x, y]
                if abs(pr - r) < 60 and abs(pg - g) < 60 and abs(pb - b) < 60:
                    pixels[x, y] = (pr, pg, pb, 0)
    bbox = image.getchannel("A").getbbox()
    if bbox:
        image = image.crop(bbox)
    box = (SIZE[0] - 2 * MARGIN, SIZE[1] - 2 * MARGIN)
    scale = min(box[0] / image.width, box[1] / image.height)
    target = (round(image.width * scale), round(image.height * scale))
    image = image.resize(target, Image.LANCZOS)
    canvas = Image.new("RGBA", SIZE, BACKGROUND)
    canvas.alpha_composite(image, ((SIZE[0] - target[0]) // 2, (SIZE[1] - target[1]) // 2))
    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def main() -> None:
    thumbs = []
    for name, relative in SOURCES.items():
        data = (ROOT / relative).read_bytes()
        output = thumbnail(data, name in KEYED)
        path = f"docs/gallery/thumbs/{name}.png"
        (ROOT / path).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / path).write_bytes(output)
        thumbs.append({"path": path, "sha256": hashlib.sha256(output).hexdigest(),
                       "source": relative, "sourceSha256": hashlib.sha256(data).hexdigest()})
    manifest = {"schemaVersion": 1, "size": list(SIZE), "background": BACKGROUND, "thumbs": thumbs}
    (ROOT / "docs/gallery/thumbs.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
