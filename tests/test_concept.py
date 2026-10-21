import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from PIL import Image

from maliang_art import cli
from maliang_art.concept import (
    apply_decision, chain_findings, draft_identity_findings, markers_to_identity, palette_findings, review_sheet,
)
from maliang_art.records import RecordValidationError, check_tree, infer_schema, validate_record

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas" / "v1"


def style():
    return {
        "schemaVersion": 1, "styleId": "ink-v1", "track": "concept",
        "framing": {"subject": "single-character", "body": "full-body", "background": "plain paper"},
        "references": [{"title": "synthetic line study", "borrow": ["clean line"], "forbid": ["identity"]}],
        "rules": [{"id": "ink-line", "instruction": "Fine ink line first", "method": "human", "required": True}],
    }


def concept(status="approved", form="base"):
    value = {
        "schemaVersion": 1, "conceptId": f"hero-{form}", "characterId": "hero", "styleId": "ink-v1",
        "form": form, "species": "synthetic bear", "image": None, "imageSize": None,
        "approval": {"status": "pending"},
    }
    if status != "pending":
        value["image"] = {"path": f"concept/{form}.png", "sha256": "a" * 64}
        value["imageSize"] = [800, 1200]
        value["approval"] = {"status": status, "reviewer": "human-reviewer", "reviewedAt": "2026-10-20T00:00:00Z"}
    return value


def markers(status="frozen"):
    return {
        "schemaVersion": 1, "markersId": "hero-markers", "characterId": "hero", "status": status,
        "conceptIds": ["hero-base"],
        "markers": [
            {"id": "two-tone", "description": "black and white coat", "category": "species-silhouette",
             "required": True, "capsuleTranslation": "two-tone-coat"},
            {"id": "staff", "description": "wooden staff", "category": "weapon",
             "required": False, "capsuleTranslation": "staff-stub"},
        ],
        "palette": [{"role": "main", "hex": "#F2F0EA"}, {"role": "secondary", "hex": "#202020"}],
        "tolerance": 24,
    }


def usage(status="pending"):
    return {
        "schemaVersion": 1, "usageId": "hero-bust", "conceptId": "hero-base", "kind": "portrait-bust",
        "purpose": "dialogue portrait", "crop": {"x": 100, "y": 0, "width": 600, "height": 600},
        "approval": {"status": status} if status == "pending" else
        {"status": status, "reviewer": "human-reviewer", "reviewedAt": "2026-10-20T00:00:00Z"},
    }


@pytest.mark.parametrize("name,value", [
    ("concept-style-guide", style()), ("character-concept", concept()),
    ("character-concept", concept("pending")), ("identity-markers", markers()),
    ("derived-usage", usage()),
])
def test_schemas_and_runtime_accept_valid_records(name, value):
    schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)
    assert infer_schema(value) == name
    assert validate_record(value) == value


@pytest.mark.parametrize("mutate", [
    lambda v: v["approval"].update(status="approved"),
    lambda v: v["approval"].update(reviewer="someone"),
    lambda v: v.update(imageSize=[0, 10]),
    lambda v: v.update(form=""),
])
def test_concept_rejects_unbacked_approval_and_bad_fields(mutate):
    value = concept("pending")
    mutate(value)
    with pytest.raises(RecordValidationError):
        validate_record(value, "character-concept")


def test_approved_concept_requires_reviewer_and_image():
    value = concept()
    del value["approval"]["reviewer"]
    with pytest.raises(RecordValidationError):
        validate_record(value, "character-concept")
    value = concept()
    value["image"] = None
    with pytest.raises(RecordValidationError):
        validate_record(value, "character-concept")


@pytest.mark.parametrize("mutate", [
    lambda v: v["markers"][0].update(category="mood"),
    lambda v: v["markers"].append(copy.deepcopy(v["markers"][0])),
    lambda v: v["palette"][0].update(hex="white"),
    lambda v: v.update(conceptIds=[]),
    lambda v: v.update(status="final"),
])
def test_markers_reject_invalid_shapes(mutate):
    value = markers()
    mutate(value)
    with pytest.raises(RecordValidationError):
        validate_record(value, "identity-markers")


def test_frozen_markers_must_reference_approved_concepts():
    assert chain_findings([concept(), markers()]) == []
    findings = chain_findings([concept("pending"), markers()])
    assert any("not approved" in f for f in findings)
    assert any("unknown concept" in f for f in chain_findings([markers()]))
    assert chain_findings([concept("pending"), markers("draft")]) == []


def test_portrait_crop_must_fit_concept_image():
    assert chain_findings([concept(), usage()]) == []
    wide = usage()
    wide["crop"]["width"] = 900
    assert any("outside" in f for f in chain_findings([concept(), wide]))
    assert any("no approved image" in f for f in chain_findings([concept("pending"), usage()]))


def test_promo_has_no_crop_and_bust_requires_one():
    promo = usage()
    promo.update(kind="promo")
    del promo["crop"]
    validate_record(promo, "derived-usage")
    bust = usage()
    del bust["crop"]
    with pytest.raises(RecordValidationError):
        validate_record(bust, "derived-usage")


def test_markers_become_capsule_identity_and_missing_required_is_reported():
    identity = markers_to_identity(markers(), species="synthetic bear")
    assert identity == {"species": "synthetic bear", "features": ["two-tone-coat", "staff-stub"],
                        "priority": ["two-tone-coat"], "forbiddenMirror": []}
    assert draft_identity_findings({"identity": identity}, markers()) == []
    missing = {"identity": {**identity, "features": ["staff-stub"]}}
    assert draft_identity_findings(missing, markers()) == ["required marker two-tone is missing from draft identity: two-tone-coat"]


def test_palette_findings_compare_dominant_colors_with_tolerance():
    counts = {(240, 240, 236): 700, (30, 30, 30): 250, (255, 0, 0): 50}
    assert palette_findings(counts, markers()) == []
    off = {(120, 60, 200): 900, (30, 30, 30): 100}
    findings = palette_findings(off, markers())
    assert findings and "#783CC8" in findings[0]


def test_check_tree_reports_unapproved_concept_reference(tmp_path):
    (tmp_path / "concept.json").write_text(json.dumps(concept("pending")), encoding="utf-8")
    (tmp_path / "markers.json").write_text(json.dumps(markers()), encoding="utf-8")
    count, errors = check_tree(tmp_path)
    assert count == 2
    assert any("not approved" in e for e in errors)


def test_review_sheet_lists_every_human_check_marker_and_decision():
    approved_image = concept()
    sheet = review_sheet(style(), approved_image, markers())
    assert sheet == review_sheet(copy.deepcopy(style()), copy.deepcopy(approved_image), copy.deepcopy(markers()))
    assert "concept/base.png" in sheet and "800x1200" in sheet
    assert "Fine ink line first" in sheet
    assert "black and white coat" in sheet and "wooden staff" in sheet
    assert sheet.count("(required)") == 1
    assert sheet.count("- [ ] Other issues:") == 2
    for option in ("approved", "rejected", "revise"):
        assert option in sheet
    assert "no image bound yet" in review_sheet(style(), concept("pending"), markers())


def test_apply_decision_records_identity_source_without_mutating_input():
    original = concept("pending")
    image = {"path": "concept/base.png", "sha256": "b" * 64}
    result = apply_decision(original, "approved", reviewer="Ada <ada@example.invalid>", source="git-config",
                            at="2026-10-20T07:00:00Z", image=image, image_size=[640, 960], note="ok")
    assert original["approval"] == {"status": "pending"}
    assert result["image"] == image and result["imageSize"] == [640, 960]
    assert result["approval"] == {"status": "approved", "reviewer": "Ada <ada@example.invalid>",
                                  "reviewerSource": "git-config", "reviewedAt": "2026-10-20T07:00:00Z", "note": "ok"}
    assert list(result) == list(original)
    validate_record(result, "character-concept")
    for name, value in (("character-concept", result),
                        ("derived-usage", apply_decision(usage(), "approved", reviewer="Ada", source="manual", at="2026-10-20T07:00:00Z"))):
        Draft202012Validator(json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))).validate(value)
    with pytest.raises(RecordValidationError):
        apply_decision(original, "approved", reviewer="Ada", source="git-config", at="2026-10-20T07:00:00Z")
    with pytest.raises(RecordValidationError):
        apply_decision(original, "maybe", reviewer="Ada", source="git-config", at="2026-10-20T07:00:00Z")
    with pytest.raises(RecordValidationError):
        apply_decision(original, "rejected", reviewer="Ada", source="guess", at="2026-10-20T07:00:00Z")


def _cli_project(tmp_path):
    (tmp_path / "concept").mkdir()
    Image.new("RGBA", (40, 60), (240, 240, 236, 255)).save(tmp_path / "concept" / "base.png")
    records = tmp_path / "records"
    records.mkdir()
    for name, value in (("style.json", style()), ("concept.json", concept("pending")), ("markers.json", markers("draft"))):
        (records / name).write_text(json.dumps(value), encoding="utf-8")
    return records


def test_cli_approve_binds_image_and_uses_git_identity(tmp_path, monkeypatch, capsys):
    records = _cli_project(tmp_path)
    monkeypatch.setattr(cli, "_git_config", lambda key: {"user.name": "Ada", "user.email": "ada@example.invalid"}[key])
    assert cli.main(["concept", "approve", str(records / "concept.json"), "--decision", "approved",
                     "--root", str(tmp_path), "--image", "concept/base.png"]) == 0
    saved = json.loads((records / "concept.json").read_text(encoding="utf-8"))
    data = (tmp_path / "concept" / "base.png").read_bytes()
    import hashlib
    assert saved["image"] == {"path": "concept/base.png", "sha256": hashlib.sha256(data).hexdigest()}
    assert saved["imageSize"] == [40, 60]
    assert saved["approval"]["reviewer"] == "Ada <ada@example.invalid>"
    assert saved["approval"]["reviewerSource"] == "git-config"
    validate_record(saved, "character-concept", root=tmp_path, verify=True)
    capsys.readouterr()
    assert cli.main(["concept", "review", str(records), "--concept", "hero-base"]) == 0
    assert "40x60" in capsys.readouterr().out


def test_cli_approve_falls_back_to_os_user(tmp_path, monkeypatch):
    records = _cli_project(tmp_path)
    monkeypatch.setattr(cli, "_git_config", lambda key: None)
    monkeypatch.setattr(cli.getpass, "getuser", lambda: "localuser")
    assert cli.main(["concept", "approve", str(records / "concept.json"), "--decision", "rejected", "--note", "redo staff"]) == 0
    approval = json.loads((records / "concept.json").read_text(encoding="utf-8"))["approval"]
    assert (approval["status"], approval["reviewer"], approval["reviewerSource"], approval["note"]) == (
        "rejected", "localuser", "os-user", "redo staff")


def test_cli_approve_requires_explicit_decision(tmp_path):
    records = _cli_project(tmp_path)
    with pytest.raises(SystemExit):
        cli.main(["concept", "approve", str(records / "concept.json")])
    assert json.loads((records / "concept.json").read_text(encoding="utf-8"))["approval"] == {"status": "pending"}


def test_review_questions_have_fixed_shape_and_all_ok_options():
    from maliang_art.concept import review_questions
    form = review_questions(style(), concept(), markers())
    assert [q["id"] for q in form["questions"]] == ["style", "markers", "decision"]
    assert [q["allow_multiple"] for q in form["questions"]] == [True, True, False]
    for q in form["questions"][:2]:
        assert [o["id"] for o in q["options"][-2:]] == ["all-ok", "other"]
    assert [o["id"] for o in form["questions"][2]["options"]] == ["approved", "rejected", "revise"]
    assert review_questions(style(), concept(), markers()) == form


def test_review_questions_filter_markers_by_form():
    from maliang_art.concept import review_questions
    value = markers()
    value["markers"][1]["forms"] = ["alt-form"]
    validate_record(value)
    ids = lambda c: [o["id"] for o in review_questions(style(), c, value)["questions"][1]["options"]]
    assert ids(concept()) == ["two-tone", "all-ok", "other"]
    assert ids(concept(form="alt-form")) == ["two-tone", "staff", "all-ok", "other"]


def test_decision_from_answers_maps_three_conclusions():
    from maliang_art.concept import decision_from_answers
    ok = {"style": ["all-ok"], "markers": ["all-ok"], "decision": ["approved"]}
    assert decision_from_answers(ok) == ("approved", None)
    assert decision_from_answers({**ok, "decision": ["rejected"]}) == ("rejected", None)
    decision, note = decision_from_answers({"style": ["ink-line"], "markers": ["staff"], "decision": ["revise"]})
    assert decision == "rejected" and "ink-line" in note and "staff" in note
    with pytest.raises(RecordValidationError):
        decision_from_answers({"style": ["ink-line"], "markers": ["all-ok"], "decision": ["approved"]})


def test_cli_concept_review_questions_format(tmp_path, capsys):
    for name, value in [("style", style()), ("concept", concept()), ("markers", markers())]:
        (tmp_path / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    assert cli.main(["concept", "review", str(tmp_path), "--concept", "hero-base", "--format", "questions"]) == 0
    assert [q["id"] for q in json.loads(capsys.readouterr().out)["questions"]] == ["style", "markers", "decision"]


def test_review_questions_keep_two_options_when_nothing_is_listed():
    from maliang_art.concept import review_questions
    value = style()
    value["rules"] = []
    marks = markers()
    for marker in marks["markers"]:
        marker["forms"] = ["alt-form"]
    form = review_questions(value, concept(), marks)
    for q in form["questions"][:2]:
        assert [o["id"] for o in q["options"]] == ["all-ok", "other"]


def test_decision_from_answers_records_free_text_and_rejects_contradictions():
    from maliang_art.concept import decision_from_answers, review_questions
    ok = {"style": ["all-ok"], "markers": ["all-ok"], "decision": ["approved"]}
    assert decision_from_answers({**ok, "other": {"decision": "looks good"}}) == ("approved", "looks good")
    for bad in ({**ok, "style": ["other"]}, {**ok, "other": {"markers": "tail rings too faint"}}):
        with pytest.raises(RecordValidationError):
            decision_from_answers(bad)
    decision, note = decision_from_answers({"style": ["ink-line"], "markers": ["other"], "decision": ["rejected"],
                                            "other": {"markers": "tail rings too faint"}})
    assert decision == "rejected" and note == "rejected: ink-line; other: tail rings too faint"
    decision, note = decision_from_answers({"style": ["all-ok"], "markers": ["all-ok"], "decision": ["revise"],
                                            "other": {"style": "paper too yellow"}})
    assert decision == "rejected" and "paper too yellow" in note
    with pytest.raises(RecordValidationError):
        decision_from_answers({"style": ["all-ok"], "markers": ["all-ok"], "decision": [], "other": {"decision": "hmm"}})
    form = review_questions(style(), concept(), markers())
    with pytest.raises(RecordValidationError):
        decision_from_answers({**ok, "style": ["typo"], "decision": ["rejected"]}, form)
    assert decision_from_answers({**ok, "style": ["ink-line"], "decision": ["rejected"]}, form)[0] == "rejected"
