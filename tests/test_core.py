from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from maliang_art.core import CollisionError, MaLiangError, PathContainmentError, canonical_bytes, contained_path, stable_id, write_immutable_bytes, write_immutable_json


def test_canonical_bytes_are_sorted_utf8_and_newline():
    assert canonical_bytes({"z": 1, "é": "雪", "a": [True, None]}) == '{"a":[true,null],"z":1,"é":"雪"}\n'.encode()


def test_canonical_bytes_deterministic_across_key_order():
    assert canonical_bytes({"b": 2, "a": 1}) == canonical_bytes({"a": 1, "b": 2})

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {1: "bad"}, object(), (1, 2)])
def test_canonical_bytes_rejects_non_json(bad):
    with pytest.raises(MaLiangError):
        canonical_bytes(bad)


def test_stable_id_known_and_length():
    value = stable_id("pose-proof", {"x": 1}, 20)
    assert value.startswith("pose-proof-") and len(value.rsplit("-", 1)[1]) == 20

@pytest.mark.parametrize("prefix", ["", "Bad", "bad_slug", "-bad", "bad-"])
def test_stable_id_rejects_bad_prefix(prefix):
    with pytest.raises(MaLiangError): stable_id(prefix, {})

@pytest.mark.parametrize("relative", ["../x", "a/../../x", "/absolute", "C:/absolute", "a\\..\\x", "a//b", "./x", ""])
def test_contained_path_rejects_unsafe_paths(tmp_path, relative):
    with pytest.raises(PathContainmentError): contained_path(tmp_path, relative)


def test_contained_path_accepts_nested_posix_path(tmp_path):
    assert contained_path(tmp_path, "a/b.json") == (tmp_path / "a" / "b.json").resolve()


def test_immutable_json_is_idempotent_and_canonical(tmp_path):
    path = write_immutable_json(tmp_path, "records/a.json", {"b": 2, "a": 1})
    write_immutable_json(tmp_path, "records/a.json", {"a": 1, "b": 2})
    assert path.read_bytes() == b'{"a":1,"b":2}\n'


def test_immutable_json_collision_fails_closed(tmp_path):
    write_immutable_json(tmp_path, "a.json", {"value": 1})
    with pytest.raises(CollisionError): write_immutable_json(tmp_path, "a.json", {"value": 2})
    assert json.loads((tmp_path / "a.json").read_text()) == {"value": 1}


def test_concurrent_identical_immutable_publication(tmp_path):
    payload = {"items": list(range(100)), "name": "same"}
    with ThreadPoolExecutor(max_workers=16) as pool:
        paths = list(pool.map(lambda _: write_immutable_json(tmp_path, "shared/value.json", payload), range(64)))
    assert len(set(paths)) == 1
    assert paths[0].read_bytes() == canonical_bytes(payload)


def test_concurrent_conflicting_publication_never_overwrites(tmp_path):
    def publish(value):
        try:
            write_immutable_json(tmp_path, "shared.json", {"winner": value})
            return "ok"
        except CollisionError:
            return "collision"
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(publish, range(40)))
    assert results.count("ok") >= 1
    stored = json.loads((tmp_path / "shared.json").read_text())
    assert stored["winner"] in range(40)
    assert results.count("collision") >= 1


def test_immutable_bytes_require_bytes(tmp_path):
    with pytest.raises(MaLiangError): write_immutable_bytes(tmp_path, "a", "text")
