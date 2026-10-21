import json
from pathlib import Path

import pytest

from maliang_art.authoring import compile_design, validate_design
from maliang_art.concept import draft_identity_findings, markers_to_identity, review_questions
from maliang_art.records import check_tree

CHARACTER = Path(__file__).resolve().parents[1] / "characters" / "concept-demo"
pytestmark = pytest.mark.skipif(not CHARACTER.is_dir(), reason="art-pilot characters are repository-only and excluded from source distributions")


def _load(name):
    return json.loads((CHARACTER / name).read_text(encoding="utf-8"))


def test_records_are_valid_and_blocked_only_on_human_concept_approval():
    count, errors = check_tree(CHARACTER / "records")
    assert count == 5
    assert errors == ["concept-demo-portrait-bust: concept concept-demo-base has no approved image"]
    for name in ("concept-base.json", "concept-alt.json"):
        record = _load(f"records/{name}")
        assert record["approval"] == {"status": "pending"}
        assert record["image"] is None
    assert _load("records/identity-markers.json")["status"] == "draft"


def test_review_questions_filter_markers_by_form():
    style, markers = _load("records/concept-style-guide.json"), _load("records/identity-markers.json")
    ids = lambda name: [o["id"] for o in review_questions(style, _load(f"records/{name}"), markers)["questions"][1]["options"]]
    assert "wing-span" not in ids("concept-base.json")
    assert "wing-span" in ids("concept-alt.json")


def test_capsule_draft_carries_every_required_marker_and_no_concept_image():
    markers = _load("records/identity-markers.json")
    draft = _load("draft-example.json")
    assert draft_identity_findings(draft, markers) == []
    assert draft["identity"] == markers_to_identity(markers, species="synthetic-heron")
    contract = _load("family-contract.json")
    assert validate_design(contract, draft) == []
    packet = compile_design(contract, draft).document
    assert all("concept" not in item["path"] for item in packet["imageInputs"])
    assert packet["artDecision"]["status"] == "pending"
