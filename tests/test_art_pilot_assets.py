from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

import pytest
from PIL import Image

from maliang_art.core import PathContainmentError, contained_path

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "art-pilot"


def _check_asset(root: Path, item: dict) -> None:
    path = contained_path(root, item["path"])
    data = path.read_bytes()
    derivative = item["derivative"]
    assert hashlib.sha256(data).hexdigest() == derivative["sha256"]
    assert len(data) == derivative["bytes"]
    with Image.open(path) as image:
        image.load()
        assert image.format == "PNG"
        assert list(image.size) == derivative["dimensions"]
        assert image.mode == derivative["mode"]
        assert list(image.convert("RGBA").getchannel("A").getextrema()) == derivative["alphaExtrema"]


@pytest.fixture
def synthetic_asset(tmp_path):
    image = Image.new("RGBA", (2, 2), (200, 100, 50, 255))
    image.putpixel((0, 0), (0, 0, 0, 0))
    path = tmp_path / "fixture.png"
    image.save(path)
    return tmp_path, {
        "path": "fixture.png",
        "derivative": {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
            "dimensions": [2, 2],
            "mode": "RGBA",
            "alphaExtrema": [0, 255],
        },
    }


def test_asset_check_accepts_synthetic_rgba(synthetic_asset):
    _check_asset(*synthetic_asset)


@pytest.mark.parametrize("field,value", [
    ("sha256", "0" * 64), ("bytes", 0), ("dimensions", [3, 3]),
    ("mode", "RGB"), ("alphaExtrema", [255, 255]),
])
def test_asset_check_rejects_changed_binding(synthetic_asset, field, value):
    root, item = synthetic_asset
    item["derivative"][field] = value
    with pytest.raises(AssertionError):
        _check_asset(root, item)


@pytest.mark.parametrize("path", ["../fixture.png", "/fixture.png", "C:/fixture.png"])
def test_asset_check_rejects_external_paths(synthetic_asset, path):
    root, item = synthetic_asset
    item["path"] = path
    with pytest.raises(PathContainmentError):
        _check_asset(root, item)


@pytest.fixture
def repository_example():
    if not EXAMPLE.is_dir():
        pytest.skip("Curated images are repository-only and excluded from source distributions")
    assert (EXAMPLE / "assets.json").is_file()
    return EXAMPLE


def test_curated_manifest_binds_exactly_three_licensed_images(repository_example):
    root = repository_example
    manifest = json.loads((root / "assets.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert manifest["license"] == "CC-BY-4.0"
    assert manifest["attribution"] == "cty41"
    assert manifest["status"] == "curated-visual-examples-not-production-approvals"
    expected = {
        "characters/falcon-idle/raw/codex-idle.png",
        "characters/crested-goshawk-idle/raw/v01-a001.png",
        "characters/shared/poet-idle-dr-style.png",
    }
    assert len(manifest["assets"]) == 3
    assert {item["path"] for item in manifest["assets"]} == expected
    assert {path.relative_to(root).as_posix() for path in root.rglob("*.png")} == expected
    for item in manifest["assets"]:
        assert item["license"] == "CC-BY-4.0"
        assert item["copyright"] == "cty41"
        assert item["selection"]["status"] == "user-selected-visual"
        assert re.fullmatch(r"[a-f0-9]{64}", item["source"]["sha256"])
        assert item["source"]["bytes"] > 0
        assert item["processing"]["tool"] == "Pillow"
        assert item["processing"]["version"]
        assert not item["processing"]["cropped"]
        assert not item["processing"]["chromaKeyApplied"]
        _check_asset(root, item)
        if item["id"] == "poet":
            assert item["source"]["sha256"] == item["derivative"]["sha256"]
            assert item["derivative"]["alphaExtrema"] == [0, 255]
        else:
            assert item["source"]["sha256"] != item["derivative"]["sha256"]
            assert item["derivative"]["alphaExtrema"] == [255, 255]
            assert item["processing"]["metadataChunksPreserved"] == ["caBX", "eXIf", "iTXt"]
            data = (root / item["path"]).read_bytes()
            position = 8
            metadata = {}
            while position < len(data):
                length = struct.unpack(">I", data[position:position + 4])[0]
                kind = data[position + 4:position + 8].decode("ascii")
                chunk = data[position:position + length + 12]
                if kind not in {"IHDR", "IDAT", "IEND"}:
                    metadata[kind] = hashlib.sha256(chunk).hexdigest()
                position += length + 12
            assert metadata == item["processing"]["metadataChunkSha256"]
            with Image.open(root / item["path"]) as image:
                assert image.info["exif"]
                assert image.info["XML:com.adobe.xmp"]


def test_new_brief_references_current_shared_image(repository_example):
    root = repository_example
    draft = json.loads((root / "characters/falcon-idle/draft-example.json").read_text(encoding="utf-8"))
    assert len(draft["references"]) == 1
    ref = draft["references"][0]
    assert ref["path"] == "characters/shared/poet-idle-dr-style.png"
    assert ref["sha256"] == hashlib.sha256(contained_path(root, ref["path"]).read_bytes()).hexdigest()


def test_curated_inputs_exclude_stale_production_evidence(repository_example):
    root = repository_example
    assert not list((root / "production").rglob("*.*"))
    assert not (root / "maliang.lock.json").exists()
    assert not list((root / "characters").rglob("*.bin"))
    assert not (root / "characters/falcon-idle/records").exists()
    assert not (root / "characters/falcon-idle/draft-v03.json").exists()
    for path in (root / "characters").rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"[A-Za-z]:[/\\]", text)
        assert "receipt" not in path.name
