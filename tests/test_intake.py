import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from maliang_art import cli
from maliang_art.intake import (
    IntakeError, draft_from_intake, next_questions, validate_catalog, validate_intake,
)

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas" / "v1"


def option(option_id, *, maps=None, recommend=None, stop=None):
    value = {"id": option_id, "label": option_id.title(), "references": ["Synthetic Game"],
             "consequence": f"{option_id} consequence", "risk": f"{option_id} risk"}
    if maps is not None:
        value["maps"] = maps
    if recommend is not None:
        value["recommendWhen"] = recommend
    if stop is not None:
        value["stop"] = stop
    return value


def catalog():
    return {
        "schemaVersion": 1, "catalogId": "synthetic-catalog",
        "dimensions": [
            {"id": "purpose", "prompt": "Final use?", "priority": 1, "optionsMode": "fixed",
             "options": [option("game-assets"), option("concept-only")]},
            {"id": "dimension", "prompt": "2D or 3D?", "priority": 2, "optionsMode": "fixed",
             "when": {"purpose": ["game-assets"]},
             "options": [option("2d"), option("3d", stop="Only 2D is supported.")]},
            {"id": "genre", "prompt": "Genre?", "priority": 3, "optionsMode": "fixed",
             "when": {"dimension": ["2d"]},
             "options": [option("tactics"), option("platformer")]},
            {"id": "view", "prompt": "Camera?", "priority": 4, "optionsMode": "fixed",
             "when": {"genre": ["tactics", "platformer"]},
             "options": [option("isometric", maps={"target": "contract", "field": "camera.mode", "value": "isometric"},
                                recommend={"genre": ["tactics"]}),
                         option("side", maps={"target": "contract", "field": "camera.mode", "value": "side"},
                                recommend={"genre": ["platformer"]})]},
            {"id": "split", "prompt": "Separate concept style?", "priority": 5, "optionsMode": "fixed",
             "when": {"view": ["isometric", "side"]},
             "options": [option("dual"), option("single")]},
            {"id": "concept-style", "prompt": "Concept style?", "priority": 6, "optionsMode": "suggest",
             "when": {"purpose": ["concept-only"], "split": ["dual"]}, "whenMode": "any",
             "options": [option("ink", maps={"target": "styleGuide", "field": "rules[]",
                                             "value": {"id": "ink", "instruction": "Ink line", "method": "human", "required": True}}),
                         option("painterly")]},
            {"id": "theme", "prompt": "Theme notes?", "priority": 7, "optionsMode": "free",
             "when": {"purpose": ["game-assets", "concept-only"]}, "options": []},
        ],
    }


def intake(*answers):
    return {"schemaVersion": 1, "intakeId": "synthetic-intake", "catalogId": "synthetic-catalog",
            "request": "a cute animal game", "answers": list(answers)}


def presented(cat, dimension):
    dim = next(d for d in cat["dimensions"] if d["id"] == dimension)
    return [{"id": o["id"], "label": o["label"], "source": "catalog"} for o in dim["options"]]


def pick(cat, dimension, option_id, **extra):
    return {"dimension": dimension, "option": option_id, "source": "catalog-option",
            "presented": presented(cat, dimension), **extra}


def asked(result):
    return [q["id"] for q in result["questions"]]


def test_first_round_asks_only_purpose_and_free_text_waits_for_it():
    cat = catalog()
    result = next_questions(cat, intake())
    assert asked(result) == ["purpose"]
    assert result["freeText"] == [] and result["stopped"] is None and not result["done"]
    question = result["questions"][0]
    assert question["allow_multiple"] is False
    assert all("consequence" in o["label"] and "risk" in o["label"] for o in question["options"])


def test_concept_only_skips_game_branch_and_reaches_concept_style():
    cat = catalog()
    result = next_questions(cat, intake(pick(cat, "purpose", "concept-only")))
    assert asked(result) == ["concept-style"]
    assert result["freeText"] == [{"id": "theme", "prompt": "Theme notes?"}]
    assert result["suggestable"] == ["concept-style"]


def test_3d_stops_with_reason():
    cat = catalog()
    result = next_questions(cat, intake(pick(cat, "purpose", "game-assets"), pick(cat, "dimension", "3d")))
    assert result["stopped"] == {"dimension": "dimension", "option": "3d", "reason": "Only 2D is supported."}
    assert result["questions"] == [] and result["done"]
    with pytest.raises(IntakeError):
        validate_intake(intake(pick(cat, "purpose", "game-assets"), pick(cat, "dimension", "3d"),
                               pick(cat, "genre", "tactics")), cat)


def test_genre_marks_recommended_view_and_single_track_skips_concept_style():
    cat = catalog()
    base = [pick(cat, "purpose", "game-assets"), pick(cat, "dimension", "2d")]
    platformer = next_questions(cat, intake(*base, pick(cat, "genre", "platformer")))
    labels = {o["id"]: o["label"] for o in platformer["questions"][0]["options"]}
    assert labels["side"].startswith("[推荐]") and not labels["isometric"].startswith("[推荐]")
    single = intake(*base, pick(cat, "genre", "tactics"), pick(cat, "view", "isometric"), pick(cat, "split", "single"))
    result = next_questions(cat, single)
    assert result["questions"] == [] and [f["id"] for f in result["freeText"]] == ["theme"]


def test_round_limit_order_and_stability():
    cat = catalog()
    for dim in cat["dimensions"]:
        dim.pop("when", None)
        dim.pop("whenMode", None)
    result = next_questions(cat, intake(), limit=3)
    assert asked(result) == ["purpose", "dimension", "genre"]
    assert result == next_questions(copy.deepcopy(cat), intake(), limit=3)


@pytest.mark.parametrize("field", ["consequence", "risk"])
def test_catalog_requires_consequence_and_risk(field):
    cat = catalog()
    cat["dimensions"][0]["options"][0][field] = ""
    with pytest.raises(IntakeError):
        validate_catalog(cat)


def test_catalog_rejects_unknown_when_reference_and_single_option_question():
    cat = catalog()
    cat["dimensions"][2]["when"] = {"missing": ["x"]}
    with pytest.raises(IntakeError):
        validate_catalog(cat)
    cat = catalog()
    cat["dimensions"][0]["options"].pop()
    with pytest.raises(IntakeError):
        validate_catalog(cat)


def test_answer_sources_are_enforced():
    cat = catalog()
    ai = {"dimension": "purpose", "option": "ai-x", "source": "ai-suggested-option",
          "presented": presented(cat, "purpose") + [{"id": "ai-x", "label": "AI X", "source": "ai"}]}
    with pytest.raises(IntakeError, match="fixed"):
        validate_intake(intake(ai), cat)
    missing = pick(cat, "purpose", "game-assets")
    del missing["presented"]
    with pytest.raises(IntakeError, match="presented"):
        validate_intake(intake(missing), cat)
    inferred = pick(cat, "purpose", "game-assets", source="ai-inferred-confirmed")
    with pytest.raises(IntakeError, match="confirmation"):
        validate_intake(intake(inferred), cat)
    inferred["confirmation"] = "user: yes, game assets"
    validate_intake(intake(inferred), cat)
    not_shown = pick(cat, "purpose", "game-assets", presented=[])
    with pytest.raises(IntakeError):
        validate_intake(intake(not_shown), cat)
    hidden = pick(cat, "genre", "tactics")
    with pytest.raises(IntakeError, match="not available"):
        validate_intake(intake(hidden), cat)


def test_ai_suggested_and_follow_up_answers_are_recorded():
    cat = catalog()
    suggestion = {"dimension": "concept-style", "option": "ai-woodblock", "source": "ai-suggested-option",
                  "presented": presented(cat, "concept-style") + [{"id": "ai-woodblock", "label": "Woodblock print", "source": "ai"}]}
    follow = {"dimension": "concept-style-detail", "followUpOf": "concept-style", "prompt": "Which era?",
              "text": "Song dynasty", "source": "user-text", "presented": []}
    record = intake(pick(cat, "purpose", "concept-only"), suggestion, follow)
    validate_intake(record, cat)
    draft = draft_from_intake(cat, record)
    assert {"dimension": "concept-style", "label": "Woodblock print", "source": "ai-suggested-option"} in draft["needsTranslation"]
    assert {"dimension": "concept-style-detail", "text": "Song dynasty", "source": "user-text"} in draft["needsTranslation"]


def test_draft_has_only_chosen_values_and_lists_open_dimensions():
    cat = catalog()
    record = intake(pick(cat, "purpose", "game-assets"), pick(cat, "dimension", "2d"),
                    pick(cat, "genre", "tactics"), pick(cat, "view", "isometric"), pick(cat, "split", "dual"))
    draft = draft_from_intake(cat, record)
    assert draft["contractHints"] == {"camera": {"mode": "isometric"}}
    assert draft["styleGuide"] == {}
    assert draft["open"] == ["concept-style", "theme"]
    assert draft["stopped"] is None
    record["answers"].append(pick(cat, "concept-style", "ink"))
    styled = draft_from_intake(cat, record)
    assert styled["styleGuide"] == {"rules": [{"id": "ink", "instruction": "Ink line", "method": "human", "required": True}]}
    assert styled["open"] == ["theme"]


def test_schemas_accept_synthetic_documents():
    cat = catalog()
    record = intake(pick(cat, "purpose", "game-assets"))
    for name, value in (("art-direction-catalog", cat), ("art-direction-intake", record)):
        schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)


def test_cli_start_answer_next_and_draft(tmp_path, capsys):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog()), encoding="utf-8")
    record = tmp_path / "intake.json"
    assert cli.main(["intake", "start", str(catalog_path), str(record), "--request", "cute tactics"]) == 0
    capsys.readouterr()
    assert cli.main(["intake", "next", str(catalog_path), str(record)]) == 0
    assert [q["id"] for q in json.loads(capsys.readouterr().out)["questions"]] == ["purpose"]
    assert cli.main(["intake", "answer", str(catalog_path), str(record), "--dimension", "purpose", "--option", "concept-only"]) == 0
    saved = json.loads(record.read_text(encoding="utf-8"))["answers"][0]
    assert saved["source"] == "catalog-option" and saved["presented"] == presented(catalog(), "purpose")
    assert cli.main(["intake", "answer", str(catalog_path), str(record), "--dimension", "theme", "--text", "forest spirits"]) == 0
    capsys.readouterr()
    assert cli.main(["intake", "draft", str(catalog_path), str(record)]) == 0
    draft = json.loads(capsys.readouterr().out)
    assert draft["open"] == ["concept-style"]
    with pytest.raises(SystemExit):
        cli.main(["intake", "answer", str(catalog_path), str(record), "--dimension", "genre", "--option", "tactics"])


def test_gate_questions_need_a_confirmed_option_instead_of_raw_text():
    cat = catalog()
    raw = {"dimension": "purpose", "source": "user-text", "text": "game sprites", "presented": presented(cat, "purpose")}
    with pytest.raises(IntakeError, match="gate question"):
        validate_intake(intake(raw), cat)
    purpose = pick(cat, "purpose", "game-assets")
    mapped = {"dimension": "dimension", "source": "ai-inferred-confirmed", "option": "3d",
              "confirmation": "yes, I meant 3D", "presented": presented(cat, "dimension")}
    assert next_questions(cat, intake(purpose, mapped))["stopped"]["option"] == "3d"
    first = next_questions(cat, intake())["questions"][0]
    assert first["id"] == "purpose" and first["gate"] is True


def test_only_gate_questions_reject_user_text():
    cat = catalog()
    steps = [pick(cat, "purpose", "game-assets"), pick(cat, "dimension", "2d"), pick(cat, "genre", "tactics"),
             pick(cat, "view", "isometric")]
    split_free = {"dimension": "split", "source": "user-text", "text": "not sure yet", "presented": presented(cat, "split")}
    with pytest.raises(IntakeError, match="gate question"):
        validate_intake(intake(*steps, split_free), cat)
    theme = {"dimension": "theme", "source": "user-text", "text": "forest clans", "presented": []}
    validate_intake(intake(pick(cat, "purpose", "concept-only"), theme), cat)
