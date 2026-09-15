from __future__ import annotations

import json
from pathlib import Path

from maliang_art.records import validate_artifact
from maliang_art.workflow import validate_delivery, validate_failure, validate_invocation

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "synthetic"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_synthetic_success_lifecycle_ids_and_artifact_hash():
    invocation = validate_invocation(_json(EXAMPLE / "success" / "invocation.json"))
    delivery = validate_delivery(_json(EXAMPLE / "success" / "delivery.json"))

    assert invocation["invocationId"] == "invocation-ea52a0dad3845016"
    assert delivery["deliveryId"] == "delivery-c3b1a05d44ce0c02"
    assert delivery["invocationId"] == invocation["invocationId"]
    assert validate_artifact(delivery["artifact"], root=ROOT, verify=True) == delivery["artifact"]


def test_synthetic_failure_lifecycle_ids_and_binding():
    invocation = validate_invocation(_json(EXAMPLE / "failure" / "invocation.json"))
    failure = validate_failure(_json(EXAMPLE / "failure" / "failure.json"))

    assert invocation["invocationId"] == "invocation-6b74715870869572"
    assert failure["failureId"] == "generation-failure-f9bcfc19b9c8d916"
    assert failure["invocationId"] == invocation["invocationId"]
    assert failure["retryable"] is True
