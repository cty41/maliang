"""Deterministic JSON identities and safe immutable publication."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
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


def _is_link_or_reparse(path: Path) -> bool:
    """Recognize symlinks and Windows reparse points without following them."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(attributes & reparse_flag)


def _assert_plain_path(root: Path, destination: Path, *, include_destination: bool = False) -> None:
    """Reject existing namespace components that can redirect path operations."""
    try:
        relative = destination.relative_to(root)
    except ValueError as exc:
        raise PathContainmentError("path escapes root") from exc
    current = root
    parts = relative.parts if include_destination else relative.parts[:-1]
    for part in parts:
        current /= part
        if _is_link_or_reparse(current):
            raise PathContainmentError(f"path contains a symlink or reparse point: {current}")


def _publish_immutable(data: bytes, destination: Path, root: Path) -> bool:
    _assert_plain_path(root, destination)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MaLiangError(f"cannot prepare immutable destination: {destination}") from exc
    # Recheck after creating parents. This rejects ordinary symlink/junction
    # redirection, although hostile namespace mutation remains a documented
    # limitation of portable pathname APIs.
    _assert_plain_path(root, destination)
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
    except OSError as exc:
        raise MaLiangError(f"cannot create immutable publication temporary: {destination}") from exc
    temporary = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _assert_plain_path(root, destination)
        try:
            os.link(temporary, destination)
            return True
        except FileExistsError:
            try:
                destination_info = destination.lstat()
                if _is_link_or_reparse(destination):
                    raise CollisionError(f"immutable destination is a link: {destination}")
                if destination_info.st_nlink != 1:
                    raise CollisionError(f"immutable destination has hard-link aliases: {destination}")
                existing = destination.read_bytes()
            except CollisionError:
                raise
            except OSError as exc:
                raise CollisionError(f"cannot inspect immutable destination: {destination}") from exc
            if existing != data:
                raise CollisionError(f"immutable publication collision: {destination}")
            return False
        except OSError as exc:
            raise MaLiangError(f"cannot publish immutable destination: {destination}") from exc
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def read_contained_bytes(root: str | os.PathLike[str], relative: str | os.PathLike[str]) -> bytes:
    """Read a regular path beneath a root while rejecting visible link indirection."""
    root_path = Path(root).resolve()
    target = contained_path(root_path, relative)
    _assert_plain_path(root_path, target, include_destination=True)
    data = target.read_bytes()
    _assert_plain_path(root_path, target, include_destination=True)
    return data


def write_immutable_json(root: str | os.PathLike[str], relative: str | os.PathLike[str], value: Any) -> Path:
    """Atomically publish canonical JSON, accepting idempotent concurrent writers."""
    root_path = Path(root).resolve()
    destination = contained_path(root_path, relative)
    _publish_immutable(canonical_bytes(value), destination, root_path)
    return destination


def write_immutable_bytes(root: str | os.PathLike[str], relative: str | os.PathLike[str], data: bytes) -> Path:
    """Atomically publish immutable bytes beneath a root."""
    if not isinstance(data, bytes):
        raise MaLiangError("data must be bytes")
    root_path = Path(root).resolve()
    destination = contained_path(root_path, relative)
    _publish_immutable(data, destination, root_path)
    return destination
