import json
from pathlib import Path

import pytest

from maliang_art.authoring.validation import CAMERA_MODES, PROFILE
from maliang_art.intake import draft_from_intake, next_questions, presented_options, validate_catalog

CATALOG = Path(__file__).resolve().parents[1] / "intake" / "art-direction-catalog.json"
pytestmark = pytest.mark.skipif(not CATALOG.is_file(), reason="art-pilot intake catalog is repository-only")


def _answer(catalog, dimension, option):
    return {"dimension": dimension, "option": option, "source": "catalog-option",
            "presented": presented_options(catalog, dimension)}


def _intake(catalog, *pairs):
    return {"schemaVersion": 1, "intakeId": "walk", "catalogId": catalog["catalogId"], "request": "可爱的动物战棋",
            "answers": [_answer(catalog, d, o) for d, o in pairs]}


def test_catalog_is_valid_and_starts_with_purpose():
    catalog = validate_catalog(json.loads(CATALOG.read_text(encoding="utf-8")))
    assert [q["id"] for q in next_questions(catalog, _intake(catalog))["questions"]] == ["purpose"]


def test_tactics_walk_recommends_isometric_and_ends_with_open_free_choices():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    steps = [("purpose", "game-assets"), ("dimension", "2d"), ("genre", "tactics")]
    view = next_questions(catalog, _intake(catalog, *steps))["questions"][0]
    assert view["id"] == "view"
    assert next(o for o in view["options"] if o["id"] == "isometric")["label"].startswith("[推荐]")
    steps += [("view", "isometric"), ("ratio", "capsule"), ("render", "line-flat"), ("split", "dual")]
    draft = draft_from_intake(catalog, _intake(catalog, *steps))
    assert draft["contractHints"] == {"camera": {"mode": "isometric", "profile": PROFILE, "mirrorAccepted": True}, "silhouettes": ["capsule"]}
    assert draft["open"] == ["concept-style", "derived-use", "palette", "theme"]


def test_3d_stops_and_concept_only_skips_game_questions():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    stopped = next_questions(catalog, _intake(catalog, ("purpose", "game-assets"), ("dimension", "3d")))
    assert stopped["done"] and "2D" in stopped["stopped"]["reason"]
    concept = next_questions(catalog, _intake(catalog, ("purpose", "concept-only")))
    assert [q["id"] for q in concept["questions"]] == ["concept-style", "derived-use", "palette"]


def test_view_options_map_supported_camera_profiles():
    catalog = validate_catalog(json.loads(CATALOG.read_text(encoding="utf-8")))
    view = next(d for d in catalog["dimensions"] if d["id"] == "view")
    for option in view["options"]:
        camera = option["maps"]["value"]
        assert option["maps"]["field"] == "camera"
        assert camera["profile"] == CAMERA_MODES[camera["mode"]]["profile"]
        assert "只支持 isometric" not in option["risk"]
