"""Step protocol, registry, and built-in state-machine steps."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

from PIL import Image

from ..core import MaLiangError

_ACTION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")


@runtime_checkable
class Step(Protocol):
    action: str

    def run(self, params: Mapping[str, Any], context: Mapping[str, Any]) -> Mapping[str, Any]: ...


class StepRegistry:
    def __init__(self) -> None:
        self._steps: dict[str, Step] = {}

    @classmethod
    def with_builtins(cls) -> "StepRegistry":
        registry = cls()
        registry.register("chroma-key", ChromaKeyStep())
        registry.register("align-canvas", AlignCanvasStep())
        return registry

    def register(self, action: str, step: Step) -> None:
        if not isinstance(action, str) or not _ACTION_RE.fullmatch(action):
            raise MaLiangError("step action name is invalid")
        if action in self._steps:
            raise MaLiangError("step action is already registered")
        self._steps[action] = step

    def get(self, action: str) -> Step:
        try:
            return self._steps[action]
        except KeyError as exc:
            raise MaLiangError("unknown step action") from exc

    def actions(self) -> tuple[str, ...]:
        return tuple(sorted(self._steps))


def _image_path(context: Mapping[str, Any]) -> str | None:
    value = context.get("image_path")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise MaLiangError("context.image_path must be non-empty text when present")
    return value


def _output_path(context: Mapping[str, Any], image_path: str) -> str:
    out = context.get("image_out")
    if out is None:
        return image_path
    if not isinstance(out, str) or not out:
        raise MaLiangError("context.image_out must be non-empty text when present")
    return out


def _normalize_key(raw: Any) -> tuple[int, int, int]:
    if not isinstance(raw, str):
        raise MaLiangError("step key must be text")
    match = _HEX_RE.fullmatch(raw.strip())
    if not match:
        raise MaLiangError("step key must be #RRGGBB")
    value = match.group(1)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _iter_pixels(image: Image.Image):
    getter = getattr(image, "get_flattened_data", image.getdata)
    return getter()


class ChromaKeyStep:
    action = "chroma-key"

    def run(self, params: Mapping[str, Any], context: Mapping[str, Any]) -> Mapping[str, Any]:
        if "key" not in params:
            raise MaLiangError("chroma-key requires key")
        key = _normalize_key(params["key"])
        tolerance = params.get("tolerance", 0)
        if isinstance(tolerance, bool) or not isinstance(tolerance, int) or not 0 <= tolerance <= 255:
            raise MaLiangError("chroma-key tolerance must be an integer from 0 through 255")
        image_path = _image_path(context)
        if image_path is None:
            return {"skipped": True}
        path = Path(image_path)
        image = Image.open(path).convert("RGBA")
        changed = 0
        cleaned = []
        limit = tolerance * tolerance
        for red, green, blue, alpha in _iter_pixels(image):
            if alpha == 0:
                cleaned.append((0, 0, 0, 0))
                continue
            distance = (red - key[0]) ** 2 + (green - key[1]) ** 2 + (blue - key[2]) ** 2
            if distance <= limit:
                cleaned.append((0, 0, 0, 0))
                changed += 1
            else:
                cleaned.append((red, green, blue, alpha))
        image.putdata(cleaned)
        output = _output_path(context, image_path)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        image.save(output, format="PNG", optimize=False, compress_level=9)
        return {"changed_pixels": changed, "output": output}


class AlignCanvasStep:
    action = "align-canvas"

    def run(self, params: Mapping[str, Any], context: Mapping[str, Any]) -> Mapping[str, Any]:
        canvas = params.get("canvas")
        if (
            type(canvas) is not list
            or len(canvas) != 2
            or any(type(channel) is not int or not 1 <= channel <= 8192 for channel in canvas)
        ):
            raise MaLiangError("align-canvas canvas must be a list of two integers from 1 through 8192")
        width, height = int(canvas[0]), int(canvas[1])
        image_path = _image_path(context)
        if image_path is None:
            return {"skipped": True}
        path = Path(image_path)
        image = Image.open(path).convert("RGBA")
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        frame = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        offset = ((width - image.width) // 2, (height - image.height) // 2)
        frame.paste(image, offset)
        output = _output_path(context, image_path)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        frame.save(output, format="PNG", optimize=False, compress_level=9)
        return {"size": [width, height], "output": output}
