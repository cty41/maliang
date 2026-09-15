"""Strict validation for portable artifact and JSON records."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .core import MaLiangError, read_contained_bytes

_SHA256 = re.compile(r"[0-9a-f]{64}")
_SCHEMA_ALIASES = {
    "artifact": "artifact",
    "pose-draft": "pose-draft",
    "pose-card": "pose-card",
    "invocation": "invocation",
    "delivery": "delivery",
    "failure": "failure",
}


class RecordValidationError(MaLiangError):
    """A record is malformed or fails its declared binding."""


def validate_artifact(value: Any, *, root: str | Path | None = None, verify: bool = False) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256"}:
        raise RecordValidationError("artifact must contain exactly path and sha256")
    path = value.get("path")
    digest = value.get("sha256")
    if not isinstance(path, str) or not path:
        raise RecordValidationError("artifact.path must be non-empty text")
    normalized = path.replace("\\", "/")
    if normalized != path or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise RecordValidationError("artifact.path must use a repository-relative POSIX path")
    if any(part in {"", ".", ".."} for part in normalized.split("/")):
        raise RecordValidationError("artifact.path contains an unsafe segment")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise RecordValidationError("artifact.sha256 must be lowercase SHA-256")
    if verify:
        if root is None:
            raise RecordValidationError("root is required when verifying bytes")
        try:
            actual = hashlib.sha256(read_contained_bytes(root, normalized)).hexdigest()
        except OSError as exc:
            raise RecordValidationError(f"cannot read artifact: {normalized}") from exc
        if actual != digest:
            raise RecordValidationError(f"artifact hash mismatch: {normalized}")
    return {"path": normalized, "sha256": digest}


def load_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecordValidationError(f"cannot load JSON record: {exc}") from exc


def _load_contained_json(root: Path, relative: str) -> Any:
    try:
        return json.loads(read_contained_bytes(root, relative).decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecordValidationError(f"cannot load JSON record: {exc}") from exc


def infer_schema(record: Any) -> str:
    if not isinstance(record, Mapping):
        raise RecordValidationError("record must be an object")
    marker = record.get("$schema")
    if isinstance(marker, str):
        for name in _SCHEMA_ALIASES:
            if f"/{name}.schema.json" in marker or marker.endswith(f"/{name}.json"):
                return name
    if set(record) - {"$schema"} == {"path", "sha256"}:
        return "artifact"
    if "options" in record and "visualMoment" in record:
        return "pose-draft"
    if "poseProofId" in record and "selectedOption" in record:
        return "pose-card"
    if "attemptId" in record and "request" in record and "requestedAt" in record:
        return "invocation"
    if "deliveryId" in record or ("artifact" in record and "deliveredAt" in record):
        return "delivery"
    if "failureId" in record or ("failedAt" in record and "retryable" in record):
        return "failure"
    raise RecordValidationError("cannot infer record schema; pass --schema")


def validate_record(record: Any, schema: str = "auto", *, root: str | Path | None = None, verify: bool = False) -> dict[str, Any]:
    kind = infer_schema(record) if schema == "auto" else schema
    if not isinstance(record, Mapping):
        raise RecordValidationError("record must be an object")
    value = dict(record)
    if "$schema" in value:
        if not isinstance(value["$schema"], str):
            raise RecordValidationError("$schema must be text")
        value.pop("$schema")
    if "schemaVersion" in value and (isinstance(value["schemaVersion"], bool) or not isinstance(value["schemaVersion"], int)):
        raise RecordValidationError("schemaVersion must be an integer")
    if kind == "artifact":
        return validate_artifact(value, root=root, verify=verify)
    if kind in {"pose-draft", "pose-card"}:
        from .pose import validate_card, validate_draft
        return (validate_draft(value, root=root, verify=verify) if kind == "pose-draft"
                else validate_card(value, root=root, verify=verify))
    if kind in {"invocation", "delivery", "failure"}:
        from .workflow import validate_delivery, validate_failure, validate_invocation
        if kind == "delivery":
            return validate_delivery(value, root=root, verify=verify)
        return validate_invocation(value) if kind == "invocation" else validate_failure(value)
    raise RecordValidationError(f"unknown schema: {kind}")


def check_tree(root: str | Path, *, verify: bool = False) -> tuple[int, list[str]]:
    base = Path(root)
    if not base.exists():
        raise RecordValidationError(f"record root does not exist: {base}")
    if not base.is_dir():
        raise RecordValidationError(f"record root is not a directory: {base}")
    base = base.resolve()
    errors: list[str] = []
    count = 0
    invocation_ids: set[str] = set()
    outcomes: list[tuple[str, str]] = []
    for path in sorted(base.rglob("*.json")):
        count += 1
        relative = path.relative_to(base).as_posix()
        try:
            record = _load_contained_json(base, relative)
            kind = infer_schema(record)
            validated = validate_record(record, kind, root=base, verify=verify)
            if kind == "invocation":
                invocation_ids.add(validated["invocationId"])
            elif kind in {"delivery", "failure"}:
                outcomes.append((relative, validated["invocationId"]))
        except MaLiangError as exc:
            errors.append(f"{relative}: {exc}")
    for relative, invocation_id in outcomes:
        if invocation_id not in invocation_ids:
            errors.append(f"{relative}: invocationId does not reference an invocation in this tree: {invocation_id}")
    return count, errors
