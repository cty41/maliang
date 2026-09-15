"""Deterministic JSON identities and safe immutable publication."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any


class MaLiangError(ValueError):
    """Base error for invalid MaLiang input."""


class PathContainmentError(MaLiangError):
    """A requested repository-relative path escapes its root."""


class CollisionError(MaLiangError):
    """An immutable destination already contains different bytes."""


def _assert_json(value: Any, path: str = "value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MaLiangError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise MaLiangError(f"{path} contains a non-string key")
            _assert_json(item, f"{path}.{key}")
        return
    raise MaLiangError(f"{path} is not a JSON value")


def canonical_bytes(value: Any) -> bytes:
    """Encode a JSON value with stable UTF-8 bytes and one trailing newline."""
    _assert_json(value)
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def stable_id(prefix: str, payload: Any, length: int = 16) -> str:
    """Derive a content identity from canonical JSON bytes."""
    if not isinstance(prefix, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", prefix):
        raise MaLiangError("prefix must be lower kebab case")
    if isinstance(length, bool) or not isinstance(length, int) or not 8 <= length <= 64:
        raise MaLiangError("length must be an integer from 8 through 64")
    digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    return f"{prefix}-{digest[:length]}"


def contained_path(root: str | os.PathLike[str], relative: str | os.PathLike[str]) -> Path:
    """Resolve a portable relative path beneath *root*, rejecting traversal."""
    root_path = Path(root).resolve()
    raw = os.fspath(relative)
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise PathContainmentError("path must be non-empty text")
    portable = raw.replace("\\", "/")
    if portable.startswith("/") or re.match(r"^[A-Za-z]:", portable):
        raise PathContainmentError("path must be repository-relative")
    if any(part in {"", ".", ".."} for part in portable.split("/")):
        raise PathContainmentError("path contains an unsafe segment")
    target = root_path / Path(*portable.split("/"))

    # realpath closes the symlink/junction escape route. Windows may add the
    # extended-path prefix while another publisher creates a parent directory,
    # so normalize that representation before comparing roots.
    def normalized_real(path: Path) -> str:
        value = os.path.normcase(os.path.abspath(os.path.realpath(path)))
        return value[4:] if value.startswith("\\\\?\\") else value

    root_real = normalized_real(root_path)
    target_real = normalized_real(target)
    try:
        if os.path.commonpath((root_real, target_real)) != root_real:
            raise PathContainmentError("path escapes root")
    except ValueError as exc:
        raise PathContainmentError("path escapes root") from exc
    return target


def _publish_immutable(data: bytes, destination: Path) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    temporary = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
            return True
        except FileExistsError:
            try:
                existing = destination.read_bytes()
            except OSError as exc:
                raise CollisionError(f"cannot inspect immutable destination: {destination}") from exc
            if existing != data:
                raise CollisionError(f"immutable publication collision: {destination}")
            return False
    finally:
        temporary.unlink(missing_ok=True)


def write_immutable_json(root: str | os.PathLike[str], relative: str | os.PathLike[str], value: Any) -> Path:
    """Atomically publish canonical JSON, accepting idempotent concurrent writers."""
    destination = contained_path(root, relative)
    _publish_immutable(canonical_bytes(value), destination)
    return destination


def write_immutable_bytes(root: str | os.PathLike[str], relative: str | os.PathLike[str], data: bytes) -> Path:
    """Atomically publish immutable bytes beneath a root."""
    if not isinstance(data, bytes):
        raise MaLiangError("data must be bytes")
    destination = contained_path(root, relative)
    _publish_immutable(data, destination)
    return destination
