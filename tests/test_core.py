from __future__ import annotations

import json
import multiprocessing
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event

import pytest

import maliang_art.core as core
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


def test_immutable_publication_rejects_existing_symlink(tmp_path):
    target = tmp_path / "target.json"
    target.write_bytes(canonical_bytes({"value": 1}))
    alias = tmp_path / "alias.json"
    try:
        alias.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises((PathContainmentError, CollisionError)):
        write_immutable_json(tmp_path, "alias.json", {"value": 1})


def test_immutable_publication_rejects_existing_hardlink_alias(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.json"
    destination = tmp_path / "published.json"
    outside.write_bytes(canonical_bytes({"value": 1}))
    try:
        os.link(outside, destination)
        with pytest.raises(CollisionError, match="hard-link aliases"):
            write_immutable_json(tmp_path, "published.json", {"value": 1})
    finally:
        outside.unlink(missing_ok=True)


@pytest.mark.parametrize("alias_name", [".record.bin.preexisting.tmp", "user-alias.bin"])
def test_immutable_publication_rejects_preexisting_sibling_alias(tmp_path, alias_name):
    destination = tmp_path / "record.bin"
    alias = tmp_path / alias_name
    destination.write_bytes(b"original")
    os.link(destination, alias)
    with pytest.raises(CollisionError, match="hard-link aliases"):
        write_immutable_bytes(tmp_path, "record.bin", b"original")
    assert destination.read_bytes() == alias.read_bytes() == b"original"
    assert destination.stat().st_nlink == 2


@pytest.mark.parametrize("payload", [b"winner", b"conflict"])
def test_thread_publication_waits_for_temporary_alias(tmp_path, monkeypatch, payload):
    linked, release, inspecting = Event(), Event(), Event()
    real_link = os.link
    real_check = core._assert_no_external_hardlinks

    def paused_link(source, destination):
        real_link(source, destination)
        linked.set()
        assert release.wait(10)

    def observed_check(destination):
        inspecting.set()
        return real_check(destination)

    monkeypatch.setattr(core.os, "link", paused_link)
    monkeypatch.setattr(core, "_assert_no_external_hardlinks", observed_check)
    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(write_immutable_bytes, tmp_path, "record.bin", b"winner")
        try:
            assert linked.wait(10)
            contender = pool.submit(write_immutable_bytes, tmp_path, "record.bin", payload)
            assert inspecting.wait(10)
            with pytest.raises(TimeoutError):
                contender.result(timeout=0.1)
        finally:
            release.set()
        assert winner.result().read_bytes() == b"winner"
        if payload == b"winner":
            assert contender.result() == tmp_path / "record.bin"
        else:
            with pytest.raises(CollisionError, match="publication collision"):
                contender.result()
    assert (tmp_path / "record.bin").stat().st_nlink == 1
    assert list(tmp_path.iterdir()) == [tmp_path / "record.bin"]


def _process_publish(root, payload, events, results, pause):
    linked, release, inspecting = events
    real_link = core.os.link
    real_check = core._assert_no_external_hardlinks

    def paused_link(source, destination):
        real_link(source, destination)
        linked.set()
        if not release.wait(15):
            raise RuntimeError("publication was not released")

    def observed_check(destination):
        inspecting.set()
        return real_check(destination)

    if pause:
        core.os.link = paused_link
    else:
        core._assert_no_external_hardlinks = observed_check
    try:
        write_immutable_bytes(root, "record.bin", payload)
        results.put("ok")
    except CollisionError as exc:
        results.put(str(exc))
    except Exception as exc:
        results.put(f"unexpected: {exc!r}")
    finally:
        core.os.link = real_link
        core._assert_no_external_hardlinks = real_check


@pytest.mark.parametrize("payload", [b"winner", b"conflict"])
def test_process_publication_waits_for_temporary_alias(tmp_path, payload):
    context = multiprocessing.get_context("spawn")
    events = tuple(context.Event() for _ in range(3))
    linked, release, inspecting = events
    winner_results, contender_results = context.Queue(), context.Queue()
    winner = context.Process(target=_process_publish, args=(str(tmp_path), b"winner", events, winner_results, True))
    contender = context.Process(target=_process_publish, args=(str(tmp_path), payload, events, contender_results, False))
    winner.start()
    try:
        assert linked.wait(10)
        contender.start()
        assert inspecting.wait(10)
        contender.join(0.1)
        assert contender.is_alive()
    finally:
        release.set()
        winner.join(10)
        if contender.pid is not None:
            contender.join(10)
        for process in (winner, contender):
            if process.pid is not None and process.is_alive():
                process.terminate()
                process.join(5)
    assert winner.exitcode == contender.exitcode == 0
    assert winner_results.get(timeout=5) == "ok"
    result = contender_results.get(timeout=5)
    if payload == b"winner":
        assert result == "ok"
    else:
        assert "immutable publication collision:" in result
    assert (tmp_path / "record.bin").read_bytes() == b"winner"
    assert (tmp_path / "record.bin").stat().st_nlink == 1
    assert list(tmp_path.iterdir()) == [tmp_path / "record.bin"]
    winner_results.close()
    contender_results.close()


@pytest.mark.parametrize("preexisting", [False, True])
def test_cleanup_failure_cannot_report_success(tmp_path, monkeypatch, preexisting):
    destination = tmp_path / "record.bin"
    if preexisting:
        destination.write_bytes(b"payload")
    cleanup_error = PermissionError("temporary cleanup denied")
    attempted = []

    def deny_unlink(path, **kwargs):
        attempted.append(path)
        raise cleanup_error

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", deny_unlink)
        with pytest.raises(MaLiangError, match="cannot remove immutable publication temporary") as caught:
            write_immutable_bytes(tmp_path, "record.bin", b"payload")
    assert caught.value.__cause__ is cleanup_error
    assert len(attempted) == 1
    assert attempted[0] != destination
    assert attempted[0].read_bytes() == destination.read_bytes() == b"payload"
    assert destination.stat().st_nlink == (1 if preexisting else 2)
    if not preexisting:
        with pytest.raises(CollisionError, match="hard-link aliases"):
            write_immutable_bytes(tmp_path, "record.bin", b"payload")
        assert attempted[0].exists()


@pytest.mark.parametrize("failure", ["collision", "link"])
def test_cleanup_failure_preserves_publication_error(tmp_path, monkeypatch, failure):
    destination = tmp_path / "record.bin"
    destination.write_bytes(b"original")
    publication_error = PermissionError("publication denied")
    attempted = []

    def deny_link(source, target):
        raise publication_error

    def deny_unlink(path, **kwargs):
        attempted.append(path)
        raise PermissionError("temporary cleanup denied")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", deny_unlink)
        if failure == "link":
            patch.setattr(core.os, "link", deny_link)
        expected = CollisionError if failure == "collision" else MaLiangError
        message = "immutable publication collision" if failure == "collision" else "cannot publish immutable destination"
        with pytest.raises(expected, match=message) as caught:
            write_immutable_bytes(tmp_path, "record.bin", b"different")
    if failure == "link":
        assert caught.value.__cause__ is publication_error
    assert destination.read_bytes() == b"original"
    assert destination.stat().st_nlink == 1
    assert len(attempted) == 1
    assert attempted[0] != destination
    assert attempted[0].read_bytes() == b"different"
