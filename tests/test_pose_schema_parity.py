from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from maliang_art.pose import PoseProofError, select_option, validate_card, validate_draft

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas" / "v1"


def _schema(name: str):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref":
                yield item
            yield from _refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _refs(item)


def _artifact_shape(schema):
    return {
        key: schema[key]
        for key in ("type", "additionalProperties", "required", "properties")
    }


def test_pose_schemas_are_self_contained_and_share_runtime_shapes():
    artifact = _schema("artifact.schema.json")
    draft = _schema("pose-draft.schema.json")
    card = _schema("pose-card.schema.json")

    for schema in (artifact, draft, card):
        assert schema["$id"].startswith(
            "https://raw.githubusercontent.com/cty41/maliang/v0.1.0/schemas/v1/"
        )
    assert all(ref.startswith("#/") for ref in _refs(draft))
    assert all(ref.startswith("#/") for ref in _refs(card))
    assert draft["$defs"]["artifact"] == _artifact_shape(artifact)
    assert card["$defs"]["artifact"] == _artifact_shape(artifact)
    assert card["$defs"]["option"] == draft["$defs"]["option"]
    assert card["$defs"]["visualMoment"] == draft["$defs"]["visualMoment"]


def test_schema_encodes_runtime_constraints_that_json_schema_can_express():
    draft = _schema("pose-draft.schema.json")
    card = _schema("pose-card.schema.json")

    point = draft["$defs"]["point"]
    assert point["minItems"] == point["maxItems"] == 2
    assert point["items"] is False
    assert draft["$defs"]["nonBlank"]["pattern"] == r"\S"
    assert card["properties"]["selectedOption"]["$ref"] == "#/$defs/option"
    assert card["properties"]["visualMoment"]["$ref"] == "#/$defs/visualMoment"
    assert card["properties"]["selection"]["properties"]["selectedAt"]["format"] == "date-time"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.update(assetId="   "),
        lambda value: value["options"][0].update(title="\t"),
        lambda value: value.update(historicalEvidence=None),
    ],
)
def test_runtime_rejects_schema_parity_cases(mutator, draft):
    mutator(draft)
    with pytest.raises(PoseProofError):
        validate_draft(draft)


def test_standalone_schemas_validate_pose_records_when_jsonschema_is_available(draft):
    jsonschema = pytest.importorskip("jsonschema")
    format_checker = jsonschema.FormatChecker()
    jsonschema.Draft202012Validator(
        _schema("pose-draft.schema.json"), format_checker=format_checker
    ).validate(draft)

    card = select_option(
        draft, "a", "reviewer", "reason", {"b": "reason"},
        "2026-01-02T03:04:05Z",
    )
    jsonschema.Draft202012Validator(
        _schema("pose-card.schema.json"), format_checker=format_checker
    ).validate(card)

    malformed = copy.deepcopy(card)
    malformed["visualMoment"]["extra"] = "not allowed"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema("pose-card.schema.json")).validate(malformed)
    with pytest.raises(PoseProofError):
        validate_card(malformed)
