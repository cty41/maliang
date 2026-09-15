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


def test_workflow_schema_inference_and_schema_marker():
    inv = invocation()
    assert infer_schema(inv) == "invocation"
    assert infer_schema({"schemaVersion": 1, "deliveryId": "x", "invocationId": "x", "artifact": {}, "deliveredAt": "x"}) == "delivery"
    assert infer_schema({"schemaVersion": 1, "failureId": "x", "invocationId": "x", "failedAt": "x", "category": "x", "message": "x", "retryable": False}) == "failure"

    marked = {"$schema": "https://example.invalid/schemas/v1/invocation.schema.json", **inv}
    assert infer_schema(marked) == "invocation"
    assert validate_record(marked) == validate_invocation(inv)


def test_validate_record_rejects_boolean_schema_version(draft):
    invalid = copy.deepcopy(draft); invalid["schemaVersion"] = True
    with pytest.raises(RecordValidationError, match="must be an integer"):
        validate_record(invalid)


def test_check_tree_reports_malformed(tmp_path, draft):
    import json
    (tmp_path / "ok.json").write_text(json.dumps(draft), encoding="utf-8")
    (tmp_path / "bad.json").write_text("[]", encoding="utf-8")
    invalid_pose = copy.deepcopy(draft); invalid_pose["options"] = []
    (tmp_path / "bad-pose.json").write_text(json.dumps(invalid_pose), encoding="utf-8")
    count, errors = check_tree(tmp_path)
    assert count == 3
    assert len(errors) == 2
    assert any(error.startswith("bad.json:") for error in errors)
    assert any(error.startswith("bad-pose.json:") for error in errors)


def test_check_tree_rejects_invalid_roots(tmp_path):
    with pytest.raises(RecordValidationError, match="does not exist"):
        check_tree(tmp_path / "missing")
    file_root = tmp_path / "record.json"; file_root.write_text("{}", encoding="utf-8")
    with pytest.raises(RecordValidationError, match="not a directory"):
        check_tree(file_root)


def test_check_tree_rejects_symlinked_records(tmp_path):
    import json

    target = tmp_path / "target.txt"
    target.write_text(json.dumps(invocation()), encoding="utf-8")
    alias = tmp_path / "outside.json"
    try:
        alias.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    count, errors = check_tree(tmp_path)
    assert count == 1
    assert len(errors) == 1 and "symlink or reparse point" in errors[0]


def test_check_tree_validates_workflow_linkage(tmp_path):
    import json
    inv = validate_invocation(invocation())
    (tmp_path / "invocation.json").write_text(json.dumps(inv), encoding="utf-8")
    delivery = validate_delivery({"schemaVersion": 1, "invocationId": inv["invocationId"], "artifact": {"path": "art/synthetic.png", "sha256": SHA}, "deliveredAt": "2026-01-01T00:01:00Z"})
    (tmp_path / "delivery.json").write_text(json.dumps(delivery), encoding="utf-8")
    assert check_tree(tmp_path) == (2, [])

    (tmp_path / "invocation.json").unlink()
    count, errors = check_tree(tmp_path)
    assert count == 1
    assert len(errors) == 1 and "does not reference an invocation" in errors[0]


def invocation():
    return {"schemaVersion": 1, "attemptId": "job-a001", "provider": "example-provider", "model": "image-model", "request": {"prompt": "synthetic"}, "requestedAt": "2026-01-01T00:00:00Z"}


def test_invocation_is_provider_neutral_and_stable():
    first = validate_invocation(invocation())
    second = validate_invocation(invocation())
    assert first == second and first["invocationId"].startswith("invocation-")
    assert validate_invocation(first) == first

@pytest.mark.parametrize("change", [
    {"provider": ""}, {"model": ""}, {"request": []}, {"requestedAt": "today"}, {"extra": True},
    {"schemaVersion": 2}, {"schemaVersion": True}, {"schemaVersion": 1.0}, {"invocationId": {"not": "text"}},
])
def test_bad_invocations(change):
    value = invocation(); value.update(change)
    with pytest.raises(WorkflowValidationError): validate_invocation(value)


def test_workflow_schema_version_is_required_and_strict():
    value = invocation(); value.pop("schemaVersion")
    with pytest.raises(WorkflowValidationError):
        validate_invocation(value)
    for validator, record in (
        (validate_delivery, {"schemaVersion": True, "invocationId": "invocation-" + "a" * 16, "artifact": {"path": "x", "sha256": SHA}, "deliveredAt": "2026-01-01T00:00:00Z"}),
        (validate_failure, {"schemaVersion": 1.0, "invocationId": "invocation-" + "a" * 16, "failedAt": "2026-01-01T00:00:00Z", "category": "x", "message": "x", "retryable": False}),
    ):
        with pytest.raises(WorkflowValidationError):
            validator(record)


def test_delivery_artifact_verification(tmp_path):
    inv = validate_invocation(invocation())
    artifact_path = tmp_path / "art" / "synthetic.png"
    artifact_path.parent.mkdir()
    artifact_path.write_bytes(b"synthetic")
    record = {
        "schemaVersion": 1,
        "invocationId": inv["invocationId"],
        "artifact": {"path": "art/synthetic.png", "sha256": hashlib.sha256(b"synthetic").hexdigest()},
        "deliveredAt": "2026-01-01T00:01:00Z",
    }
    assert validate_record(record, "delivery", root=tmp_path, verify=True)["artifact"] == record["artifact"]
    record["artifact"]["sha256"] = SHA
    with pytest.raises(RecordValidationError, match="hash mismatch"):
        validate_record(record, "delivery", root=tmp_path, verify=True)


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
