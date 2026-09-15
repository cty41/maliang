"""Concrete JSON and Pillow adapters for MaLiang's pure core."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from .core import contained_path, write_immutable_bytes, write_immutable_json
from .records import load_json


class JsonFileAdapter:
    """Read JSON and publish immutable canonical JSON below one root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def load(self, path: str | Path) -> Any:
        return load_json(contained_path(self.root, path))

    def publish(self, path: str | Path, value: Any) -> Path:
        return write_immutable_json(self.root, path, value)


class PillowImageAdapter:
    """Save deterministic PNG files through immutable publication."""

    def publish_png(self, root: str | Path, path: str | Path, image: Image.Image) -> Path:
        import io
        stream = io.BytesIO()
        image.save(stream, format="PNG", optimize=False, compress_level=9)
        return write_immutable_bytes(root, path, stream.getvalue())

    def open_rgba(self, path: str | Path) -> Image.Image:
        with Image.open(path) as image:
            return image.convert("RGBA")
