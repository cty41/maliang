"""Concrete JSON and Pillow adapters for MaLiang's pure core."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from .core import read_contained_bytes, write_immutable_bytes, write_immutable_json
from .records import RecordValidationError


class JsonFileAdapter:
    """Read JSON and publish immutable canonical JSON below one root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def load(self, path: str | Path) -> Any:
        try:
            return json.loads(read_contained_bytes(self.root, path).decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RecordValidationError(f"cannot load JSON record: {exc}") from exc

    def publish(self, path: str | Path, value: Any) -> Path:
        return write_immutable_json(self.root, path, value)


class PillowImageAdapter:
    """Save deterministic PNG files through immutable publication."""

    def publish_png(self, root: str | Path, path: str | Path, image: Image.Image) -> Path:
        import io
        stream = io.BytesIO()
        image.save(stream, format="PNG", optimize=False, compress_level=9)
        return write_immutable_bytes(root, path, stream.getvalue())

    def bind_image(self, root: str | Path, relative: str) -> tuple[dict[str, str], list[int]]:
        """Return the artifact binding and [width, height] of a contained image."""
        import hashlib
        import io
        data = read_contained_bytes(root, relative)
        try:
            with Image.open(io.BytesIO(data)) as image:
                size = [image.width, image.height]
        except OSError as exc:
            raise RecordValidationError(f"cannot read image: {relative}") from exc
        return {"path": relative, "sha256": hashlib.sha256(data).hexdigest()}, size

    def open_rgba(self, path: str | Path) -> Image.Image:
        with Image.open(path) as image:
            return image.convert("RGBA")
