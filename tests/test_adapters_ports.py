from __future__ import annotations

import pytest
from PIL import Image

from maliang_art.core import PathContainmentError
from maliang_art.adapters import JsonFileAdapter, PillowImageAdapter
from maliang_art.ports import ImagePublisher, JsonRecordStore


def test_json_adapter_satisfies_protocol(tmp_path):
    adapter = JsonFileAdapter(tmp_path)
    assert isinstance(adapter, JsonRecordStore)
    adapter.publish("record.json", {"value": 1})
    assert adapter.load("record.json") == {"value": 1}
    with pytest.raises(PathContainmentError):
        adapter.load("../outside.json")


def test_pillow_adapter_satisfies_protocol(tmp_path):
    adapter = PillowImageAdapter()
    assert isinstance(adapter, ImagePublisher)
    path = adapter.publish_png(tmp_path, "image.png", Image.new("RGBA", (3, 4), "orange"))
    assert adapter.open_rgba(path).size == (3, 4)
