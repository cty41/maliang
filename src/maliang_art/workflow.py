"""Provider-neutral generation invocation, delivery, and failure records."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Mapping

from .core import MaLiangError, stable_id
from .records import validate_artifact


_INVOCATION_ID = re.compile(r"invocation-[0-9a-f]{16}")


class WorkflowValidationError(MaLiangError):
    pass


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkflowValidationError(f"{name} must be an object")
    return deepcopy(dict(value))


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowValidationError(f"{name} must be non-empty text")
    return value


def _timestamp(value: Any, name: str) -> str:
    value = _text(value, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkflowValidationError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise WorkflowValidationError(f"{name} must include a timezone")
    return value


def _schema_version(record: Mapping[str, Any], name: str) -> None:
    version = record.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise WorkflowValidationError(f"unsupported {name} schemaVersion")


def _invocation_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _INVOCATION_ID.fullmatch(value):
        raise WorkflowValidationError(f"{name} must be a canonical invocationId")
    return value


def _validate_id(record: dict[str, Any], field: str, prefix: str) -> dict[str, Any]:
    payload = {key: value for key, value in record.items() if key not in {field, "schemaVersion"}}
    expected = stable_id(prefix, payload)
    if field in record and not isinstance(record[field], str):
        raise WorkflowValidationError(f"{field} must be text")
    if field in record and record[field] != expected:
        raise WorkflowValidationError(f"{field} does not match canonical payload")
    return {"schemaVersion": 1, field: expected, **payload}


def validate_invocation(value: Any) -> dict[str, Any]:
    record = _object(value, "invocation")
    allowed = {"schemaVersion", "invocationId", "attemptId", "provider", "model", "request", "requestedAt"}
    if set(record) - allowed or allowed - {"invocationId"} - set(record):
        raise WorkflowValidationError("invocation fields are invalid")
    _schema_version(record, "invocation")
    for field in ("attemptId", "provider", "model"):
        _text(record.get(field), f"invocation.{field}")
    if not isinstance(record.get("request"), Mapping):
        raise WorkflowValidationError("invocation.request must be an object")
    _timestamp(record.get("requestedAt"), "invocation.requestedAt")
    return _validate_id(record, "invocationId", "invocation")


def validate_delivery(value: Any, *, root: str | Path | None = None, verify: bool = False) -> dict[str, Any]:
    record = _object(value, "delivery")
    allowed = {"schemaVersion", "deliveryId", "invocationId", "artifact", "deliveredAt", "metadata"}
    if set(record) - allowed or allowed - {"deliveryId", "metadata"} - set(record):
        raise WorkflowValidationError("delivery fields are invalid")
    _schema_version(record, "delivery")
    _invocation_id(record.get("invocationId"), "delivery.invocationId")
    record["artifact"] = validate_artifact(record.get("artifact"), root=root, verify=verify)
    _timestamp(record.get("deliveredAt"), "delivery.deliveredAt")
    if "metadata" in record and not isinstance(record["metadata"], Mapping):
        raise WorkflowValidationError("delivery.metadata must be an object")
    return _validate_id(record, "deliveryId", "delivery")


def validate_failure(value: Any) -> dict[str, Any]:
    record = _object(value, "failure")
    allowed = {"schemaVersion", "failureId", "invocationId", "failedAt", "category", "message", "retryable", "details"}
    if set(record) - allowed or allowed - {"failureId", "details"} - set(record):
        raise WorkflowValidationError("failure fields are invalid")
    _schema_version(record, "failure")
    _invocation_id(record.get("invocationId"), "failure.invocationId")
    for field in ("category", "message"):
        _text(record.get(field), f"failure.{field}")
    _timestamp(record.get("failedAt"), "failure.failedAt")
    if not isinstance(record.get("retryable"), bool):
        raise WorkflowValidationError("failure.retryable must be boolean")
    if "details" in record and not isinstance(record["details"], Mapping):
        raise WorkflowValidationError("failure.details must be an object")
    return _validate_id(record, "failureId", "generation-failure")
