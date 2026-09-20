from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from maliang_art.core import MaLiangError
from maliang_art.statemachine import StepRegistry
from maliang_art.statemachine.steps import AlignCanvasStep, ChromaKeyStep


def test_with_builtins_contains_expected_actions():
    registry = StepRegistry.with_builtins()
    assert "chroma-key" in registry.actions()
    assert "align-canvas" in registry.actions()


def test_chroma_key_skipped_without_image():
    step = ChromaKeyStep()
    result = step.run({"key": "#FF00FF", "tolerance": 0}, {})
    assert result == {"skipped": True}


def test_chroma_key_removes_key_color(tmp_path: Path):
    path = tmp_path / "src.png"
    Image.new("RGBA", (4, 4), (255, 0, 255, 255)).save(path)
    step = ChromaKeyStep()
    out = tmp_path / "out.png"
    result = step.run({"key": "#ff00ff", "tolerance": 0}, {"image_path": str(path), "image_out": str(out)})
    assert result["changed_pixels"] == 16
    image = Image.open(out).convert("RGBA")
    assert image.getpixel((0, 0)) == (0, 0, 0, 0)


def test_chroma_key_invalid_key():
    step = ChromaKeyStep()
    with pytest.raises(MaLiangError, match="key"):
        step.run({"key": "green"}, {"image_path": None})


def test_chroma_key_invalid_tolerance(tmp_path: Path):
    path = tmp_path / "src.png"
    Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(path)
    step = ChromaKeyStep()
    with pytest.raises(MaLiangError, match="tolerance"):
        step.run({"key": "#ff00ff", "tolerance": 999}, {"image_path": str(path)})


def test_align_canvas_skipped_without_image():
    step = AlignCanvasStep()
    assert step.run({"canvas": [8, 8]}, {}) == {"skipped": True}


def test_align_canvas_centers_thumbnail(tmp_path: Path):
    path = tmp_path / "wide.png"
    Image.new("RGBA", (40, 10), (20, 20, 20, 255)).save(path)
    step = AlignCanvasStep()
    out = tmp_path / "aligned.png"
    result = step.run({"canvas": [20, 20]}, {"image_path": str(path), "image_out": str(out)})
    assert result["size"] == [20, 20]
    image = Image.open(out)
    assert image.size == (20, 20)
    # content is letterboxed; corner should remain transparent
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((10, 10))[3] == 255


def test_align_canvas_rejects_tuple():
    step = AlignCanvasStep()
    with pytest.raises(MaLiangError, match="canvas"):
        step.run({"canvas": (20, 20)}, {})


def test_align_canvas_invalid_canvas():
    step = AlignCanvasStep()
    with pytest.raises(MaLiangError, match="canvas"):
        step.run({"canvas": [10]}, {})


def test_duplicate_register_rejected():
    registry = StepRegistry.with_builtins()
    with pytest.raises(MaLiangError, match="already registered"):
        registry.register("chroma-key", ChromaKeyStep())


def test_unknown_action_get():
    registry = StepRegistry()
    with pytest.raises(MaLiangError, match="unknown step action"):
        registry.get("nope")
