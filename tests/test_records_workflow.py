from __future__ import annotations

import copy
import hashlib

import pytest

from maliang_art.records import RecordValidationError, check_tree, infer_schema, validate_artifact, validate_record
from maliang_art.workflow import WorkflowValidationError, validate_delivery, validate_failure, validate_invocation

SHA = "a" * 64


def test_artifact_validation_and_hash_verification(tmp_path):
    target = tmp_path / "assets" / "synthetic.bin"; target.parent.mkdir(); target.write_bytes(b"synthetic")
    artifact = {"path": "assets/synthetic.bin", "sha256": hashlib.sha256(b"synthetic").hexdigest()}
    assert validate_artifact(artifact, root=tmp_path, verify=True) == artifact

@pytest.mark.parametrize("artifact", [
    {}, {"path": "x", "sha256": SHA, "extra": 1}, {"path": "../x", "sha256": SHA},
    {"path": "C:/x", "sha256": SHA}, {"path": "a\\b", "sha256": SHA},
    {"path": "x", "sha256": "A" * 64}, {"path": "x", "sha256": "short"},
])
def test_bad_artifacts_rejected(artifact):
    with pytest.raises(RecordValidationError): validate_artifact(artifact)


def test_artifact_missing_or_hash_mismatch(tmp_path):
    with pytest.raises(RecordValidationError): validate_artifact({"path": "missing", "sha256": SHA}, root=tmp_path, verify=True)
    (tmp_path / "file").write_bytes(b"x")
    with pytest.raises(RecordValidationError): validate_artifact({"path": "file", "sha256": SHA}, root=tmp_path, verify=True)


def test_schema_inference(draft):
    assert infer_schema({"path": "x", "sha256": SHA}) == "artifact"
    assert infer_schema(draft) == "pose-draft"
    assert validate_record(draft, "auto") == draft


def test_check_tree_reports_malformed(tmp_path, draft):
    import json
    (tmp_path / "ok.json").write_text(json.dumps(draft), encoding="utf-8")
    (tmp_path / "bad.json").write_text("[]", encoding="utf-8")
    count, errors = check_tree(tmp_path)
    assert count == 2 and len(errors) == 1 and errors[0].startswith("bad.json:")


def invocation():
    return {"schemaVersion": 1, "attemptId": "job-a001", "provider": "example-provider", "model": "image-model", "request": {"prompt": "synthetic"}, "requestedAt": "2026-01-01T00:00:00Z"}


def test_invocation_is_provider_neutral_and_stable():
    first = validate_invocation(invocation())
    second = validate_invocation(invocation())
    assert first == second and first["invocationId"].startswith("invocation-")
    assert validate_invocation(first) == first

@pytest.mark.parametrize("change", [
    {"provider": ""}, {"model": ""}, {"request": []}, {"requestedAt": "today"}, {"extra": True}, {"schemaVersion": 2},
])
def test_bad_invocations(change):
    value = invocation(); value.update(change)
    with pytest.raises(WorkflowValidationError): validate_invocation(value)


def test_delivery_and_failure_bindings():
    inv = validate_invocation(invocation())
    delivery = validate_delivery({"schemaVersion": 1, "invocationId": inv["invocationId"], "artifact": {"path": "art/synthetic.png", "sha256": SHA}, "deliveredAt": "2026-01-01T00:01:00+00:00", "metadata": {"seed": 7}})
    failure = validate_failure({"schemaVersion": 1, "invocationId": inv["invocationId"], "failedAt": "2026-01-01T00:01:00Z", "category": "timeout", "message": "provider timed out", "retryable": True})
    assert validate_delivery(delivery) == delivery
    assert validate_failure(failure) == failure

@pytest.mark.parametrize("record,validator", [
    ({"schemaVersion": 1, "invocationId": "x", "artifact": {"path": "../x", "sha256": SHA}, "deliveredAt": "2026-01-01T00:00:00Z"}, validate_delivery),
    ({"schemaVersion": 1, "invocationId": "x", "failedAt": "2026-01-01T00:00:00Z", "category": "x", "message": "x", "retryable": "yes"}, validate_failure),
])
def test_bad_outcomes(record, validator):
    with pytest.raises((WorkflowValidationError, RecordValidationError)): validator(record)


def test_tampered_workflow_identity_rejected():
    value = validate_invocation(invocation()); value["model"] = "tampered"
    with pytest.raises(WorkflowValidationError): validate_invocation(value)
